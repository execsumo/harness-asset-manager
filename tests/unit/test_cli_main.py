from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from harness_asset_manager.cli.main import runtime_env
from harness_asset_manager.env_names import CLAUDE_ROOT_ENV, STATE_DIR_ENV, legacy_name
from harness_asset_manager.paths import resolve_app_paths
from tests.unit.test_paths import isolated_env


class CliMainTests(unittest.TestCase):
    def test_explicit_state_dir_flag_beats_both_env_spellings(self) -> None:
        with isolated_env("darwin"), TemporaryDirectory() as temp:
            flag_dir = Path(temp) / "flag_state"
            new_env_dir = Path(temp) / "new_env_state"
            legacy_env_dir = Path(temp) / "legacy_env_state"

            # Set BOTH env vars in the environment
            env_with_vars = {
                "HOME": str(Path(temp) / "home"),
                STATE_DIR_ENV: str(new_env_dir),
                legacy_name(STATE_DIR_ENV): str(legacy_env_dir),
            }

            with mock.patch.dict("os.environ", env_with_vars):
                env = runtime_env(str(flag_dir))
                paths = resolve_app_paths(env)

            # The explicit flag isolates config_dir and data_dir too, not just state_dir.
            self.assertEqual(paths.config_dir, flag_dir)
            self.assertEqual(paths.data_dir, flag_dir)
            self.assertEqual(paths.state_dir, flag_dir)
            self.assertEqual(env["HOME"], str(flag_dir))
            self.assertEqual(env["XDG_CONFIG_HOME"], str(flag_dir))
            self.assertEqual(env["XDG_DATA_HOME"], str(flag_dir))
            self.assertEqual(env["XDG_STATE_HOME"], str(flag_dir))

    def test_state_dir_flag_clears_explicit_harness_root_overrides(self) -> None:
        with TemporaryDirectory() as temp:
            flag_dir = Path(temp) / "isolated"
            with mock.patch.dict(
                "os.environ",
                {
                    "HOME": str(Path(temp) / "home"),
                    CLAUDE_ROOT_ENV: str(Path(temp) / "real-claude"),
                },
                clear=True,
            ):
                env = runtime_env(str(flag_dir))

            self.assertNotIn(CLAUDE_ROOT_ENV, env)
            self.assertEqual(env["HOME"], str(flag_dir))


if __name__ == "__main__":
    unittest.main()
