from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from harness_asset_manager.env_names import CLAUDE_ROOT_ENV, legacy_name
from harness_asset_manager.harness.contracts import FileTreeBindingProfile
from harness_asset_manager.harness.resolution import resolve_context


class ManagedRootFallbackTests(unittest.TestCase):
    def test_resolve_managed_root_legacy_fallback_stands_for_all_six_harness_roots(self) -> None:
        # resolve_platform_context merges os.environ, so clear it: an ambient
        # SKILL_MANAGER_CLAUDE_ROOT would otherwise decide these assertions.
        with mock.patch.dict("os.environ", {}, clear=True):
            profile = FileTreeBindingProfile(
                managed_env=CLAUDE_ROOT_ENV,
                managed_default=lambda ctx: ctx.home / ".claude",
            )

            new_val = "/tmp/new-claude-root"
            legacy_val = "/tmp/legacy-claude-root"
            legacy_env_key = legacy_name(CLAUDE_ROOT_ENV)

            # Case 1: new name alone -> honored
            ctx_new = resolve_context({CLAUDE_ROOT_ENV: new_val})
            self.assertEqual(profile.resolve_managed_root(ctx_new), Path(new_val))

            # Case 2: legacy name alone -> honored (stands for all 6 managed root vars)
            ctx_legacy = resolve_context({legacy_env_key: legacy_val})
            self.assertEqual(profile.resolve_managed_root(ctx_legacy), Path(legacy_val))

            # Case 3: both set -> new name wins
            ctx_both = resolve_context({
                CLAUDE_ROOT_ENV: new_val,
                legacy_env_key: legacy_val,
            })
            self.assertEqual(profile.resolve_managed_root(ctx_both), Path(new_val))


if __name__ == "__main__":
    unittest.main()
