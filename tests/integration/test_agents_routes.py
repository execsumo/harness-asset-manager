from __future__ import annotations

import unittest
from pathlib import Path

from tests.support.app_harness import AppTestHarness
from tests.support.fake_home import FakeHomeSpec


def _seed_unmanaged_claude_agent(spec: FakeHomeSpec, slug: str = "stray") -> None:
    agents_dir = spec.home / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / f"{slug}.md").write_text(
        f"---\nname: {slug.title()}\ndescription: found in claude\n---\n\nharness body\n",
        encoding="utf-8",
    )


class AgentRoutesTests(unittest.TestCase):
    def test_inventory_lists_only_agent_capable_harnesses(self) -> None:
        with AppTestHarness() as harness:
            payload = harness.get_json("/api/agents")
            columns = {column["harness"] for column in payload["columns"]}
            self.assertEqual(columns, {"claude", "opencode"})
            # Cursor and Codex have no subagent-file format and must not be offered.
            self.assertNotIn("cursor", columns)
            self.assertNotIn("codex", columns)

    def test_create_enable_and_disable_round_trip(self) -> None:
        with AppTestHarness() as harness:
            created = harness.post_json(
                "/api/agents",
                {"name": "Red Team", "description": "probes", "prompt": "be adversarial"},
            )
            self.assertEqual(created["ref"], "red-team")

            harness.post_json("/api/agents/red-team/enable", {"harness": "claude"})
            link = harness.spec.home / ".claude" / "agents" / "red-team.md"
            self.assertTrue(link.is_symlink())

            entry = self._entry(harness, "red-team")
            self.assertEqual(entry["kind"], "managed")
            self.assertEqual(self._state(entry, "claude"), "enabled")

            harness.post_json("/api/agents/red-team/disable", {"harness": "claude"})
            self.assertFalse(link.exists())
            self.assertTrue((harness.spec.agents_root / "red-team.md").is_file())

    def test_unmanaged_ref_is_namespaced_and_routes_through_the_path_param(self) -> None:
        """The wire shape unit tests bypass: a ref containing '/' must reach the route."""
        with AppTestHarness(fixture_factory=_seed_unmanaged_claude_agent) as harness:
            entry = self._entry(harness, "claude/stray")
            self.assertEqual(entry["kind"], "unmanaged")
            self.assertTrue(entry["actions"]["canAdopt"])
            self.assertTrue(entry["harnessPath"].endswith("/.claude/agents/stray.md"))

            result = harness.post_json("/api/agents/claude/stray/adopt", {})
            self.assertTrue(result["ok"])
            self.assertEqual(result["ref"], "stray")

            self.assertTrue((harness.spec.agents_root / "stray.md").is_file())
            self.assertTrue((harness.spec.home / ".claude" / "agents" / "stray.md").is_symlink())
            self.assertEqual(self._entry(harness, "stray")["kind"], "managed")

    def test_adopt_collision_returns_409_with_both_paths_and_mutates_nothing(self) -> None:
        with AppTestHarness(fixture_factory=_seed_unmanaged_claude_agent) as harness:
            harness.post_json(
                "/api/agents",
                {"name": "Stray", "description": "ours", "prompt": "ours"},
            )
            store_file = harness.spec.agents_root / "stray.md"
            store_before = store_file.read_text(encoding="utf-8")

            conflict = harness.post_json(
                "/api/agents/claude/stray/adopt", {}, expected_status=409
            )

            self.assertEqual(conflict["conflict"], "store-name-exists")
            self.assertEqual(conflict["slug"], "stray")
            self.assertTrue(conflict["storePath"].endswith("/agents/stray.md"))
            self.assertTrue(conflict["harnessPath"].endswith("/.claude/agents/stray.md"))

            harness_file = harness.spec.home / ".claude" / "agents" / "stray.md"
            self.assertEqual(store_file.read_text(encoding="utf-8"), store_before)
            self.assertFalse(harness_file.is_symlink())

    def test_adopt_keep_store_resolves_the_conflict(self) -> None:
        with AppTestHarness(fixture_factory=_seed_unmanaged_claude_agent) as harness:
            harness.post_json(
                "/api/agents",
                {"name": "Stray", "description": "ours", "prompt": "ours"},
            )
            store_before = (harness.spec.agents_root / "stray.md").read_text(encoding="utf-8")

            result = harness.post_json(
                "/api/agents/claude/stray/adopt", {"onConflict": "keep_store"}
            )

            self.assertTrue(result["ok"])
            self.assertEqual(
                (harness.spec.agents_root / "stray.md").read_text(encoding="utf-8"), store_before
            )
            self.assertTrue((harness.spec.home / ".claude" / "agents" / "stray.md").is_symlink())

    def test_adopt_replace_store_takes_the_harness_version(self) -> None:
        with AppTestHarness(fixture_factory=_seed_unmanaged_claude_agent) as harness:
            harness.post_json(
                "/api/agents",
                {"name": "Stray", "description": "ours", "prompt": "ours"},
            )

            harness.post_json(
                "/api/agents/claude/stray/adopt", {"onConflict": "replace_store"}
            )

            content = (harness.spec.agents_root / "stray.md").read_text(encoding="utf-8")
            self.assertIn("harness body", content)
            self.assertNotIn("ours", content)

    def test_adopt_all_reports_skipped_conflicts(self) -> None:
        def seed(spec: FakeHomeSpec) -> None:
            _seed_unmanaged_claude_agent(spec, "stray")
            _seed_unmanaged_claude_agent(spec, "fresh")

        with AppTestHarness(fixture_factory=seed) as harness:
            harness.post_json(
                "/api/agents", {"name": "Stray", "description": "ours", "prompt": "ours"}
            )

            result = harness.post_json("/api/agents/adopt-all")

            self.assertEqual(result["adopted"], ["fresh"])
            self.assertEqual([row["ref"] for row in result["skipped"]], ["claude/stray"])

    def test_set_harnesses_and_delete(self) -> None:
        with AppTestHarness() as harness:
            harness.post_json(
                "/api/agents", {"name": "Red Team", "description": "d", "prompt": "p"}
            )
            result = harness.post_json(
                "/api/agents/red-team/set-harnesses", {"harnesses": ["claude"]}
            )
            self.assertTrue(result["ok"])
            self.assertIn("claude", result["succeeded"])
            self.assertTrue((harness.spec.home / ".claude" / "agents" / "red-team.md").is_symlink())

            harness.delete_json("/api/agents/red-team")
            self.assertFalse((harness.spec.home / ".claude" / "agents" / "red-team.md").exists())
            self.assertFalse((harness.spec.agents_root / "red-team.md").exists())

    def test_update_agent_drops_legacy_frontmatter(self) -> None:
        def seed(spec: FakeHomeSpec) -> None:
            root = spec.agents_root
            root.mkdir(parents=True, exist_ok=True)
            (root / "legacy.md").write_text(
                "---\nname: Legacy\ndescription: old\n"
                "capabilities:\n  skills:\n    - a\n  mcps:\n    - b\n"
                "harnesses:\n  claude: {}\n---\n\nbody\n",
                encoding="utf-8",
            )

        with AppTestHarness(fixture_factory=seed) as harness:
            updated = harness.put_json("/api/agents/legacy", {"description": "new"})
            self.assertEqual(updated["description"], "new")
            self.assertEqual(updated["prompt"], "body")

            content = (harness.spec.agents_root / "legacy.md").read_text(encoding="utf-8")
            self.assertNotIn("capabilities", content)
            self.assertNotIn("harnesses", content)

    def test_error_body_uses_the_shared_error_field(self) -> None:
        with AppTestHarness() as harness:
            payload = harness.post_json(
                "/api/agents/does-not-exist/enable", {"harness": "claude"}, expected_status=409
            )
            self.assertIn("error", payload)
            self.assertIn("does-not-exist", payload["error"])

    def test_unsupported_harness_is_refused(self) -> None:
        with AppTestHarness() as harness:
            harness.post_json(
                "/api/agents", {"name": "Red Team", "description": "d", "prompt": "p"}
            )
            payload = harness.post_json(
                "/api/agents/red-team/enable", {"harness": "cursor"}, expected_status=409
            )
            self.assertIn("cursor", payload["error"])

    def _entry(self, harness: AppTestHarness, ref: str) -> dict:
        payload = harness.get_json("/api/agents")
        matches = [entry for entry in payload["entries"] if entry["ref"] == ref]
        if not matches:
            raise AssertionError(
                f"no entry {ref!r}; got {[e['ref'] for e in payload['entries']]}"
            )
        return matches[0]

    @staticmethod
    def _state(entry: dict, harness_id: str) -> str:
        return next(b["state"] for b in entry["bindings"] if b["harness"] == harness_id)


if __name__ == "__main__":
    unittest.main()
