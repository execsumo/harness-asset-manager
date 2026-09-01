from __future__ import annotations

import os
import socket
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from harness_asset_manager.runtime import process as runtime_process
from harness_asset_manager.runtime import server as server_module
from harness_asset_manager.runtime.assets import resolve_frontend_dist
from harness_asset_manager.runtime.server import (
    bind_socket,
    choose_port,
    serve_foreground,
)
from harness_asset_manager.runtime.startup import (
    PACKAGED_STARTUP_TIMEOUT_SECONDS,
    SOURCE_STARTUP_TIMEOUT_SECONDS,
    startup_timeout_seconds,
)
from harness_asset_manager.runtime.state import (
    RuntimeState,
    clear_runtime_state,
    load_runtime_state,
    write_runtime_state,
)


class RuntimeTests(unittest.TestCase):
    def test_startup_timeout_uses_source_timeout_by_default(self) -> None:
        self.assertEqual(startup_timeout_seconds(packaged=False), SOURCE_STARTUP_TIMEOUT_SECONDS)

    def test_startup_timeout_uses_packaged_timeout_when_frozen(self) -> None:
        self.assertEqual(startup_timeout_seconds(packaged=True), PACKAGED_STARTUP_TIMEOUT_SECONDS)

    def test_runtime_state_roundtrip_uses_override_directory(self) -> None:
        with TemporaryDirectory() as temp_dir:
            env = {"HARNESS_ASSET_MANAGER_STATE_DIR": temp_dir}
            state = RuntimeState(
                pid=1234,
                host="127.0.0.1",
                port=8123,
                base_url="http://127.0.0.1:8123",
                version="0.1.0",
                executable="/tmp/harness-asset-manager",
                started_at=1.23,
            )

            path = write_runtime_state(state, env)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            restored = load_runtime_state(env)

            self.assertEqual(restored, state)
            clear_runtime_state(env)
            self.assertIsNone(load_runtime_state(env))

    def test_resolve_and_rotate_api_token(self) -> None:
        from harness_asset_manager.paths import resolve_app_paths
        from harness_asset_manager.runtime.token import (
            resolve_api_token,
            rotate_api_token,
        )

        with TemporaryDirectory() as temp_dir:
            env = {"HARNESS_ASSET_MANAGER_STATE_DIR": temp_dir}
            paths = resolve_app_paths(env)

            # First resolve generates and writes token with 0600 mode
            token1 = resolve_api_token(paths, env)
            self.assertTrue(paths.api_token_path.is_file())
            self.assertEqual(paths.api_token_path.stat().st_mode & 0o777, 0o600)

            # Subsequent resolve returns the exact same token
            token2 = resolve_api_token(paths, env)
            self.assertEqual(token1, token2)

            # Rotation changes the token and persists with 0600 mode
            rotated = rotate_api_token(paths)
            self.assertNotEqual(token1, rotated)
            self.assertEqual(resolve_api_token(paths, env), rotated)

            # HARNESSAM_API_TOKEN environment variable overrides
            env_with_override = {**env, "HARNESSAM_API_TOKEN": "custom-override-token"}
            self.assertEqual(resolve_api_token(paths, env_with_override), "custom-override-token")

    def test_runtime_state_truncated_corrupt_json_returns_none(self) -> None:
        with TemporaryDirectory() as temp_dir:
            env = {"HARNESS_ASSET_MANAGER_STATE_DIR": temp_dir}
            state_file = Path(temp_dir) / "runtime.json"
            state_file.write_text('{"pid": 12', encoding="utf-8")
            self.assertIsNone(load_runtime_state(env))

    def test_runtime_state_non_dict_json_returns_none(self) -> None:
        with TemporaryDirectory() as temp_dir:
            env = {"HARNESS_ASSET_MANAGER_STATE_DIR": temp_dir}
            state_file = Path(temp_dir) / "runtime.json"
            state_file.write_text("[]", encoding="utf-8")
            self.assertIsNone(load_runtime_state(env))

    def test_explicit_missing_frontend_dist_does_not_fall_back(self) -> None:
        with TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing-dist"
            self.assertIsNone(resolve_frontend_dist(missing))

    def test_choose_port_returns_an_ephemeral_port_when_preferred_is_busy(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            busy_port = int(sock.getsockname()[1])
            chosen = choose_port("127.0.0.1", busy_port)

        self.assertNotEqual(chosen, busy_port)
        self.assertGreater(chosen, 0)

    def test_bind_socket_keeps_the_port_it_successfully_acquires(self) -> None:
        first, _, busy_port = bind_socket("127.0.0.1", 0)
        try:
            second, _, actual_port = bind_socket("127.0.0.1", busy_port)
            second.close()
            self.assertNotEqual(actual_port, busy_port)
        finally:
            first.close()

    def test_process_command_falls_back_to_system_ps_when_path_is_isolated(self) -> None:
        with patch.dict(os.environ, {"PATH": "/tmp/harness-asset-manager-fake-bin"}):
            with (
                patch.object(runtime_process.shutil, "which", side_effect=[None, "/bin/ps"]) as which_mock,
                patch.object(runtime_process.subprocess, "run") as run_mock,
            ):
                run_mock.return_value.stdout = "python -m harness_asset_manager"

                command = runtime_process.process_command(1234)

        self.assertEqual(command, "python -m harness_asset_manager")
        self.assertEqual(which_mock.call_count, 2)
        self.assertEqual(run_mock.call_args.args[0][0], "/bin/ps")

    def test_serve_foreground_applies_and_disables_tailnet_mapping(self) -> None:
        fake_server = MagicMock()
        fake_uvicorn = MagicMock()
        fake_uvicorn.Server.return_value = fake_server

        sock, host, port = bind_socket("127.0.0.1", 0)
        with (
            patch.object(server_module, "_uvicorn", return_value=fake_uvicorn),
            patch.object(server_module, "_create_app", return_value=lambda *a, **k: MagicMock()),
            patch.object(server_module, "maybe_open_browser"),
            patch(
                "harness_asset_manager.runtime.tailscale.apply_tailnet_serve", return_value=True
            ) as apply_mock,
            patch("harness_asset_manager.runtime.tailscale.disable_tailnet_serve") as disable_mock,
        ):
            result = serve_foreground(
                MagicMock(),
                host=host,
                port=port,
                open_browser=False,
                prebound_socket=sock,
                tailnet=True,
                tailnet_port=7443,
            )

        self.assertEqual(result, 0)
        apply_mock.assert_called_once_with(https_port=7443, backend_port=port)
        disable_mock.assert_called_once_with(https_port=7443)

    def test_serve_foreground_skips_tailnet_when_disabled(self) -> None:
        fake_server = MagicMock()
        fake_uvicorn = MagicMock()
        fake_uvicorn.Server.return_value = fake_server

        sock, host, port = bind_socket("127.0.0.1", 0)
        with (
            patch.object(server_module, "_uvicorn", return_value=fake_uvicorn),
            patch.object(server_module, "_create_app", return_value=lambda *a, **k: MagicMock()),
            patch.object(server_module, "maybe_open_browser"),
            patch("harness_asset_manager.runtime.tailscale.apply_tailnet_serve") as apply_mock,
            patch("harness_asset_manager.runtime.tailscale.disable_tailnet_serve") as disable_mock,
        ):
            serve_foreground(
                MagicMock(),
                host=host,
                port=port,
                open_browser=False,
                prebound_socket=sock,
                tailnet=False,
            )

        apply_mock.assert_not_called()
        disable_mock.assert_not_called()

    def test_serve_foreground_does_not_disable_when_apply_failed(self) -> None:
        fake_server = MagicMock()
        fake_uvicorn = MagicMock()
        fake_uvicorn.Server.return_value = fake_server

        sock, host, port = bind_socket("127.0.0.1", 0)
        with (
            patch.object(server_module, "_uvicorn", return_value=fake_uvicorn),
            patch.object(server_module, "_create_app", return_value=lambda *a, **k: MagicMock()),
            patch.object(server_module, "maybe_open_browser"),
            patch(
                "harness_asset_manager.runtime.tailscale.apply_tailnet_serve", return_value=False
            ),
            patch("harness_asset_manager.runtime.tailscale.disable_tailnet_serve") as disable_mock,
        ):
            serve_foreground(
                MagicMock(),
                host=host,
                port=port,
                open_browser=False,
                prebound_socket=sock,
                tailnet=True,
                tailnet_port=7443,
            )

        disable_mock.assert_not_called()

    def test_process_command_returns_empty_string_when_ps_is_unavailable(self) -> None:
        with (
            patch.object(runtime_process.shutil, "which", return_value=None),
            patch.object(runtime_process.Path, "is_file", return_value=False),
            patch.object(runtime_process.os, "access", return_value=False),
        ):
            self.assertEqual(runtime_process.process_command(1234), "")


if __name__ == "__main__":
    unittest.main()
