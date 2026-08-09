"""Guards on the support-tier commitment declared in ``catalog.py``.

The tier split exists because effort had drifted away from the harnesses this tool is
actually built for: at the time it was introduced Antigravity — a core harness — was
referenced by fewer test files than either OpenCode or Hermes, and had no slash-command
binding at all, while nothing in the repo said the four were different from the seven.

These tests make both halves of that failure loud:

1. the core set is pinned, so a harness cannot be quietly promoted or demoted, and
2. each core harness's family coverage is pinned, so a gap has to be declared in
   ``KNOWN_CORE_GAPS`` — which is a list somebody has to justify in review — rather than
   going unnoticed for months.

This is a *declaration* ratchet, not a coverage ratchet. It cannot tell you whether a
family is well tested, only whether it is claimed. Measuring exercise is
``RECOMMENDATIONS.md`` §2.2's job.
"""

from __future__ import annotations

import unittest

from harness_asset_manager.harness.catalog import (
    SUPPORTED_HARNESS_DEFINITIONS,
    core_harness_ids,
    supported_harness_ids,
)
from harness_asset_manager.harness.contracts import FamilyKey

ALL_FAMILIES: frozenset[FamilyKey] = frozenset(
    {"skills", "mcp", "slash_commands", "hooks", "permissions", "agents"}
)

#: The harnesses this tool is built for. Changing this set is a product decision, not a
#: refactor — it moves what blocks a release.
EXPECTED_CORE: frozenset[str] = frozenset({"claude", "codex", "agy", "cursor"})

#: Families a core harness does **not** bind today, each with the reason it is still open.
#: Empty is the goal. An entry here is a commitment to close it or to prove it impossible,
#: not a permanent excuse — see RECOMMENDATIONS.md §1.5 and §1.6.
KNOWN_CORE_GAPS: dict[str, dict[FamilyKey, str]] = {
    "agy": {
        "slash_commands": (
            "No slash-command binding declared. Needs the Antigravity command surface "
            "verified against a live CLI before it can be implemented."
        )
    },
    "cursor": {
        "permissions": (
            "No permissions binding declared, so denylists do not reach Cursor. Needs "
            "Cursor's current permission surface verified before it can be implemented."
        )
    },
}


def _definition(harness_id: str):
    return next(d for d in SUPPORTED_HARNESS_DEFINITIONS if d.harness == harness_id)


class SupportTierTests(unittest.TestCase):
    def test_core_set_is_pinned(self) -> None:
        self.assertEqual(set(core_harness_ids()), set(EXPECTED_CORE))

    def test_core_ids_are_a_subset_of_supported_ids(self) -> None:
        self.assertTrue(set(core_harness_ids()) <= set(supported_harness_ids()))

    def test_openclaw_is_retired(self) -> None:
        # Removed 2026-08-09: skills-only, MCP writes never implemented, and it carried a
        # column in every matrix. Reintroducing it should be a deliberate act.
        self.assertNotIn("openclaw", supported_harness_ids())

    def test_every_definition_declares_a_known_tier(self) -> None:
        for definition in SUPPORTED_HARNESS_DEFINITIONS:
            with self.subTest(harness=definition.harness):
                self.assertIn(definition.support_tier, {"core", "best_effort"})

    def test_is_core_agrees_with_the_tier_field(self) -> None:
        for definition in SUPPORTED_HARNESS_DEFINITIONS:
            with self.subTest(harness=definition.harness):
                self.assertEqual(definition.is_core, definition.support_tier == "core")


class CoreHarnessFamilyCoverageTests(unittest.TestCase):
    def test_core_harnesses_bind_every_family_except_declared_gaps(self) -> None:
        for harness_id in sorted(EXPECTED_CORE):
            definition = _definition(harness_id)
            declared = {family for family in ALL_FAMILIES if definition.supports_family(family)}
            expected_gaps = set(KNOWN_CORE_GAPS.get(harness_id, {}))
            with self.subTest(harness=harness_id):
                self.assertEqual(
                    ALL_FAMILIES - declared,
                    expected_gaps,
                    (
                        f"{harness_id} family coverage changed. If a gap was closed, remove it "
                        f"from KNOWN_CORE_GAPS. If a binding was dropped, that is a release "
                        f"blocker for a core harness."
                    ),
                )

    def test_known_gaps_only_name_core_harnesses_and_real_families(self) -> None:
        for harness_id, gaps in KNOWN_CORE_GAPS.items():
            with self.subTest(harness=harness_id):
                self.assertIn(harness_id, EXPECTED_CORE)
                self.assertTrue(set(gaps) <= ALL_FAMILIES)
                for family, reason in gaps.items():
                    self.assertTrue(reason.strip(), f"{harness_id}/{family} needs a reason")

    def test_claude_and_codex_have_complete_coverage(self) -> None:
        # The two reference harnesses. If either grows a gap, the family in question is
        # almost certainly modelled wrong rather than genuinely unsupportable.
        for harness_id in ("claude", "codex"):
            definition = _definition(harness_id)
            with self.subTest(harness=harness_id):
                for family in sorted(ALL_FAMILIES):
                    self.assertTrue(definition.supports_family(family), f"{harness_id}/{family}")


if __name__ == "__main__":
    unittest.main()
