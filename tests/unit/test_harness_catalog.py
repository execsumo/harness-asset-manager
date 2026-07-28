from __future__ import annotations

import unittest
from pathlib import Path

from harness_asset_manager.env_names import HERMES_HOME_ENV, legacy_name
from harness_asset_manager.harness.catalog import _hermes_home
from harness_asset_manager.harness.resolution import resolve_context


class HermesHomePrecedenceTests(unittest.TestCase):
    def test_hermes_home_three_way_precedence(self) -> None:
        new_val = "/tmp/new-hermes-home"
        legacy_val = "/tmp/legacy-hermes-home"
        plain_val = "/tmp/plain-hermes-home"
        legacy_env_key = legacy_name(HERMES_HOME_ENV)

        # Case 1: Default when no env vars set -> context.home / ".hermes"
        ctx_default = resolve_context({})
        self.assertEqual(_hermes_home(ctx_default), ctx_default.home / ".hermes")

        # Case 2: Plain HERMES_HOME set -> honored when our vars unset
        ctx_plain = resolve_context({"HERMES_HOME": plain_val})
        self.assertEqual(_hermes_home(ctx_plain), Path(plain_val))

        # Case 3: Legacy SKILL_MANAGER_HERMES_HOME set -> takes precedence over plain HERMES_HOME
        ctx_legacy = resolve_context({
            "HERMES_HOME": plain_val,
            legacy_env_key: legacy_val,
        })
        self.assertEqual(_hermes_home(ctx_legacy), Path(legacy_val))

        # Case 4: HARNESS_ASSET_MANAGER_HERMES_HOME set -> takes precedence over legacy and plain
        ctx_new = resolve_context({
            "HERMES_HOME": plain_val,
            legacy_env_key: legacy_val,
            HERMES_HOME_ENV: new_val,
        })
        self.assertEqual(_hermes_home(ctx_new), Path(new_val))


if __name__ == "__main__":
    unittest.main()
