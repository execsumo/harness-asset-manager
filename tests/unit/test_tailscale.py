"""``detect_tailnet_dns_name`` must never raise and must fail toward "not detected"."""

from __future__ import annotations

import subprocess
import unittest
from unittest import mock

from harness_asset_manager.runtime.tailscale import (
    apply_tailnet_serve,
    detect_tailnet_dns_name,
    disable_tailnet_serve,
)


class DetectTailnetDnsNameTests(unittest.TestCase):
    def test_missing_cli_returns_none(self) -> None:
        with mock.patch("shutil.which", return_value=None):
            self.assertIsNone(detect_tailnet_dns_name())

    def test_happy_path_strips_trailing_dot(self) -> None:
        payload = '{"Self": {"DNSName": "my-mac.tailnet-name.ts.net."}}'
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout=payload, stderr="")
        with mock.patch("shutil.which", return_value="/usr/bin/tailscale"), mock.patch(
            "subprocess.run", return_value=completed
        ):
            self.assertEqual(detect_tailnet_dns_name(), "my-mac.tailnet-name.ts.net")

    def test_timeout_returns_none(self) -> None:
        with mock.patch("shutil.which", return_value="/usr/bin/tailscale"), mock.patch(
            "subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="tailscale", timeout=2.0)
        ):
            self.assertIsNone(detect_tailnet_dns_name())

    def test_daemon_not_running_returns_none(self) -> None:
        completed = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="not running")
        with mock.patch("shutil.which", return_value="/usr/bin/tailscale"), mock.patch(
            "subprocess.run", return_value=completed
        ):
            self.assertIsNone(detect_tailnet_dns_name())

    def test_malformed_json_returns_none(self) -> None:
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="not json", stderr="")
        with mock.patch("shutil.which", return_value="/usr/bin/tailscale"), mock.patch(
            "subprocess.run", return_value=completed
        ):
            self.assertIsNone(detect_tailnet_dns_name())

    def test_empty_dns_name_returns_none(self) -> None:
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout='{"Self": {"DNSName": ""}}', stderr="")
        with mock.patch("shutil.which", return_value="/usr/bin/tailscale"), mock.patch(
            "subprocess.run", return_value=completed
        ):
            self.assertIsNone(detect_tailnet_dns_name())

    def test_oserror_returns_none(self) -> None:
        with mock.patch("shutil.which", return_value="/usr/bin/tailscale"), mock.patch(
            "subprocess.run", side_effect=OSError("no such file")
        ):
            self.assertIsNone(detect_tailnet_dns_name())


class ApplyTailnetServeTests(unittest.TestCase):
    def test_missing_cli_returns_false(self) -> None:
        with mock.patch("shutil.which", return_value=None):
            self.assertFalse(apply_tailnet_serve(https_port=7443, backend_port=8000))

    def test_happy_path_invokes_serve_bg_with_backend_url(self) -> None:
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with mock.patch("shutil.which", return_value="/usr/bin/tailscale"), mock.patch(
            "subprocess.run", return_value=completed
        ) as run_mock:
            self.assertTrue(apply_tailnet_serve(https_port=7443, backend_port=8000))
        called_argv = run_mock.call_args.args[0]
        self.assertEqual(
            called_argv,
            ["/usr/bin/tailscale", "serve", "--bg", "--https=7443", "http://127.0.0.1:8000"],
        )

    def test_nonzero_exit_returns_false(self) -> None:
        completed = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="denied")
        with mock.patch("shutil.which", return_value="/usr/bin/tailscale"), mock.patch(
            "subprocess.run", return_value=completed
        ):
            self.assertFalse(apply_tailnet_serve(https_port=7443, backend_port=8000))

    def test_timeout_returns_false(self) -> None:
        with mock.patch("shutil.which", return_value="/usr/bin/tailscale"), mock.patch(
            "subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="tailscale", timeout=5.0)
        ):
            self.assertFalse(apply_tailnet_serve(https_port=7443, backend_port=8000))

    def test_oserror_returns_false(self) -> None:
        with mock.patch("shutil.which", return_value="/usr/bin/tailscale"), mock.patch(
            "subprocess.run", side_effect=OSError("no such file")
        ):
            self.assertFalse(apply_tailnet_serve(https_port=7443, backend_port=8000))


class DisableTailnetServeTests(unittest.TestCase):
    def test_missing_cli_returns_false(self) -> None:
        with mock.patch("shutil.which", return_value=None):
            self.assertFalse(disable_tailnet_serve(https_port=7443))

    def test_happy_path_turns_off_only_this_port(self) -> None:
        completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with mock.patch("shutil.which", return_value="/usr/bin/tailscale"), mock.patch(
            "subprocess.run", return_value=completed
        ) as run_mock:
            self.assertTrue(disable_tailnet_serve(https_port=7443))
        called_argv = run_mock.call_args.args[0]
        self.assertEqual(called_argv, ["/usr/bin/tailscale", "serve", "--https=7443", "off"])

    def test_timeout_returns_false(self) -> None:
        with mock.patch("shutil.which", return_value="/usr/bin/tailscale"), mock.patch(
            "subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="tailscale", timeout=5.0)
        ):
            self.assertFalse(disable_tailnet_serve(https_port=7443))


if __name__ == "__main__":
    unittest.main()
