import os
import sys
import unittest
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from harness_asset_manager.env_names import (
    ALL_ENV_NAMES,
    SETTINGS_PATH_ENV,
    STATE_DIR_ENV,
    legacy_name,
)
from harness_asset_manager.paths import APP_NAME, resolve_app_paths


@contextmanager
def isolated_env(platform: str):
    """Pin sys.platform and clear inherited XDG/HOME so tests fully control env.

    Clears **both** spellings of every name we own: while the legacy SKILL_MANAGER_*
    fallback exists, clearing only the new name would let an inherited legacy var leak
    into a test that means to assert the default.
    """
    env_copy = os.environ.copy()
    for key in (
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
        "HOME",
        *ALL_ENV_NAMES,
    ):
        env_copy.pop(key, None)
    with mock.patch.object(sys, "platform", platform), mock.patch.dict("os.environ", env_copy, clear=True):
        yield


class ResolveAppPathsTests(unittest.TestCase):
    def test_macos_default_layout_collapses_to_dot_dir(self) -> None:
        with isolated_env("darwin"), TemporaryDirectory() as temp:
            home = Path(temp) / "home"
            paths = resolve_app_paths({"HOME": str(home)})
            base = home / f".{APP_NAME}"
            self.assertEqual(paths.config_dir, base)
            self.assertEqual(paths.data_dir, base)
            self.assertEqual(paths.state_dir, base)
            self.assertEqual(paths.skills_store_root, base / "skills")
            self.assertEqual(paths.skills_store_manifest, base / "skills-manifest.json")
            self.assertEqual(paths.marketplace_cache_root, base / "marketplace")
            self.assertEqual(paths.mutation_audit_path, base / "audit.log")
            self.assertEqual(paths.settings_path, base / "settings.json")
            self.assertEqual(paths.slash_command_store_root, base / "slash-commands")
            self.assertEqual(paths.slash_command_commands_dir, base / "slash-commands" / "commands")
            self.assertEqual(paths.slash_command_sync_state_path, base / "slash-commands" / "sync-state.json")
            self.assertEqual(paths.runtime_state_path, base / "runtime.json")
            self.assertEqual(paths.server_log_path, base / "server.log")

    def test_macos_default_layout_falls_back_to_legacy_application_support_if_exists(self) -> None:
        with isolated_env("darwin"), TemporaryDirectory() as temp:
            home = Path(temp) / "home"
            legacy_dir = home / "Library" / "Application Support" / APP_NAME
            legacy_dir.mkdir(parents=True)
            paths = resolve_app_paths({"HOME": str(home)})
            self.assertEqual(paths.config_dir, legacy_dir)
            self.assertEqual(paths.data_dir, legacy_dir)
            self.assertEqual(paths.state_dir, legacy_dir)

    def test_xdg_overrides_each_dir_independently(self) -> None:
        with isolated_env("darwin"), TemporaryDirectory() as temp:
            root = Path(temp)
            env = {
                "HOME": str(root / "home"),
                "XDG_CONFIG_HOME": str(root / "cfg"),
                "XDG_DATA_HOME": str(root / "data"),
                "XDG_STATE_HOME": str(root / "state"),
            }
            paths = resolve_app_paths(env)
            self.assertEqual(paths.config_dir, root / "cfg" / APP_NAME)
            self.assertEqual(paths.data_dir, root / "data" / APP_NAME)
            self.assertEqual(paths.state_dir, root / "state" / APP_NAME)
            self.assertEqual(paths.skills_store_root, root / "data" / APP_NAME / "skills")
            self.assertEqual(paths.mutation_audit_path, root / "data" / APP_NAME / "audit.log")
            self.assertEqual(paths.slash_command_store_root, root / "data" / APP_NAME / "slash-commands")
            self.assertEqual(paths.settings_path, root / "cfg" / APP_NAME / "settings.json")

    def test_settings_path_env_overrides_settings_path(self) -> None:
        with isolated_env("darwin"), TemporaryDirectory() as temp:
            new_custom = Path(temp) / "new" / "settings.json"
            legacy_custom = Path(temp) / "legacy" / "settings.json"

            # Case 1: new name alone -> honored
            paths_new = resolve_app_paths({
                "HOME": str(Path(temp) / "home"),
                SETTINGS_PATH_ENV: str(new_custom),
            })
            self.assertEqual(paths_new.settings_path, new_custom)

            # Case 2: legacy name alone -> honored
            paths_legacy = resolve_app_paths({
                "HOME": str(Path(temp) / "home"),
                legacy_name(SETTINGS_PATH_ENV): str(legacy_custom),
            })
            self.assertEqual(paths_legacy.settings_path, legacy_custom)

            # Case 3: both set -> new name wins
            paths_both = resolve_app_paths({
                "HOME": str(Path(temp) / "home"),
                SETTINGS_PATH_ENV: str(new_custom),
                legacy_name(SETTINGS_PATH_ENV): str(legacy_custom),
            })
            self.assertEqual(paths_both.settings_path, new_custom)

    def test_state_dir_env_overrides_state_paths(self) -> None:
        with isolated_env("darwin"), TemporaryDirectory() as temp:
            new_state = Path(temp) / "new_runtime"
            legacy_state = Path(temp) / "legacy_runtime"

            # Case 1: new name alone -> honored
            paths_new = resolve_app_paths({
                "HOME": str(Path(temp) / "home"),
                STATE_DIR_ENV: str(new_state),
            })
            self.assertEqual(paths_new.state_dir, new_state)
            self.assertEqual(paths_new.runtime_state_path, new_state / "runtime.json")

            # Case 2: legacy name alone -> honored
            paths_legacy = resolve_app_paths({
                "HOME": str(Path(temp) / "home"),
                legacy_name(STATE_DIR_ENV): str(legacy_state),
            })
            self.assertEqual(paths_legacy.state_dir, legacy_state)
            self.assertEqual(paths_legacy.runtime_state_path, legacy_state / "runtime.json")

            # Case 3: both set -> new name wins
            paths_both = resolve_app_paths({
                "HOME": str(Path(temp) / "home"),
                STATE_DIR_ENV: str(new_state),
                legacy_name(STATE_DIR_ENV): str(legacy_state),
            })
            self.assertEqual(paths_both.state_dir, new_state)
            self.assertEqual(paths_both.runtime_state_path, new_state / "runtime.json")

    def test_linux_defaults_use_xdg_basedir_layout(self) -> None:
        with isolated_env("linux"), TemporaryDirectory() as temp:
            home = Path(temp) / "home"
            paths = resolve_app_paths({"HOME": str(home)})
            self.assertEqual(paths.config_dir, home / ".config" / APP_NAME)
            self.assertEqual(paths.data_dir, home / ".local" / "share" / APP_NAME)
            self.assertEqual(paths.state_dir, home / ".local" / "state" / APP_NAME)

    def test_unsupported_platform_fails_clearly(self) -> None:
        with isolated_env("win32"), TemporaryDirectory() as temp:
            with self.assertRaisesRegex(RuntimeError, "unsupported platform: win32"):
                resolve_app_paths({"HOME": str(Path(temp) / "home")})


if __name__ == "__main__":
    unittest.main()
