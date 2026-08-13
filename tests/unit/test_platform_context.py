from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness_asset_manager.env_names import (
    CLAUDE_ROOT_ENV,
    SETTINGS_PATH_ENV,
    STATE_DIR_ENV,
)
from harness_asset_manager.platform_context import resolve_platform_context


class PlatformContextTests(unittest.TestCase):
    def test_macos_platform_context_uses_xdg_fallbacks(self) -> None:
        with TemporaryDirectory() as temp:
            home = Path(temp) / "home"
            context = resolve_platform_context(
                {
                    "HOME": str(home),
                    "XDG_CONFIG_HOME": "",
                    "XDG_DATA_HOME": "",
                    "XDG_STATE_HOME": "",
                },
                sys_platform="darwin",
            )

            self.assertEqual(context.platform, "macos")
            self.assertEqual(context.sys_platform, "darwin")
            self.assertEqual(context.home, home)
            self.assertEqual(context.xdg_config_home, home / ".config")
            self.assertEqual(context.xdg_data_home, home / ".local" / "share")
            self.assertEqual(context.xdg_state_home, home / ".local" / "state")

    def test_linux_platform_context_honors_xdg_overrides(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            context = resolve_platform_context(
                {
                    "HOME": str(root / "home"),
                    "XDG_CONFIG_HOME": str(root / "cfg"),
                    "XDG_DATA_HOME": str(root / "data"),
                    "XDG_STATE_HOME": str(root / "state"),
                },
                sys_platform="linux",
            )

            self.assertEqual(context.platform, "linux")
            self.assertEqual(context.xdg_config_home, root / "cfg")
            self.assertEqual(context.xdg_data_home, root / "data")
            self.assertEqual(context.xdg_state_home, root / "state")

    def test_linux_variant_platform_names_are_supported(self) -> None:
        context = resolve_platform_context({"HOME": "/tmp/home"}, sys_platform="linux2")

        self.assertEqual(context.platform, "linux")

    def test_state_dir_isolates_home_xdg_and_explicit_harness_paths(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp)
            isolated = root / "isolated"
            context = resolve_platform_context(
                {
                    "HOME": str(root / "real-home"),
                    "XDG_CONFIG_HOME": str(root / "real-config"),
                    "XDG_DATA_HOME": str(root / "real-data"),
                    "XDG_STATE_HOME": str(root / "real-state"),
                    STATE_DIR_ENV: str(isolated),
                    SETTINGS_PATH_ENV: str(root / "real-settings.json"),
                    CLAUDE_ROOT_ENV: str(root / "real-claude"),
                },
                sys_platform="linux",
            )

            self.assertEqual(context.home, isolated)
            self.assertEqual(context.xdg_config_home, isolated)
            self.assertEqual(context.xdg_data_home, isolated)
            self.assertEqual(context.xdg_state_home, isolated)
            self.assertEqual(context.env["HOME"], str(isolated))
            self.assertNotIn(SETTINGS_PATH_ENV, context.env)
            self.assertNotIn(CLAUDE_ROOT_ENV, context.env)

    def test_unsupported_platform_fails_clearly(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "unsupported platform: win32"):
            resolve_platform_context({"HOME": "/tmp/home"}, sys_platform="win32")


if __name__ == "__main__":
    unittest.main()
