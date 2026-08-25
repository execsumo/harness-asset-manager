from __future__ import annotations

import json
import tomllib
import unittest

from tests.support.app_harness import AppTestHarness
from tests.support.fake_home import FakeHomeSpec


def _seed_unmanaged_claude_agent(spec: FakeHomeSpec, slug: str = "stray") -> None:
    agents_dir = spec.home / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / f"{slug}.md").write_text(
        f"---\nname: {slug.title()}\ndescription: found in claude\n---\n\nharness body\n",
        encoding="utf-8",
    )


def _seed_unmanaged_codex_agent(spec: FakeHomeSpec, slug: str = "auditor") -> None:
    agents_dir = spec.home / ".codex" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / f"{slug}.toml").write_text(
        f'name = "{slug}"\ndescription = "found in codex"\ndeveloper_instructions = "codex instructions"\n',
        encoding="utf-8",
    )


class AgentRoutesTests(unittest.TestCase):
    def test_agent_columns_match_the_skills_columns(self) -> None:
        """The two pages must never disagree about which harnesses exist.

        Both derive columns from `enabled_harness_ids_for_family`, so a harness the
        user disables in settings drops out of both at once. This is the regression
        that shipped once: agents used a hand-curated harness list.
        """
        with AppTestHarness() as harness:
            agents = [c["harness"] for c in harness.get_json("/api/agents")["columns"]]
            skills = [
                c["harness"] for c in harness.get_json("/api/skills")["harnessColumns"]
            ]
            # Subset, not equality: every harness declaring agents also declares skills,
            # but not the reverse — a harness can have a skills root and no agent-file
            # format. (OpenClaw was the standing example until it was retired 2026-08-09.)
            self.assertTrue(set(agents) <= set(skills), f"{agents} not within {skills}")
            # Same relative order, so the two matrices read the same left to right.
            self.assertEqual(agents, [h for h in skills if h in set(agents)])
            for expected in ("claude", "codex", "cursor", "hermes", "agy"):
                self.assertIn(expected, agents)

    def test_disabling_a_harness_drops_its_agents_column(self) -> None:
        with AppTestHarness() as harness:
            before = [c["harness"] for c in harness.get_json("/api/agents")["columns"]]
            self.assertIn("cursor", before)

            harness.put_json("/api/settings/harnesses/cursor/support", {"enabled": False})

            after = [c["harness"] for c in harness.get_json("/api/agents")["columns"]]
            self.assertNotIn("cursor", after)

    def test_hermes_keeps_a_column_and_supports_best_effort_files(self) -> None:
        with AppTestHarness() as harness:
            harness.post_json(
                "/api/agents", {"name": "Red Team", "description": "d", "prompt": "p"}
            )
            entry = self._entry(harness, "red-team")
            hermes = next(b for b in entry["bindings"] if b["harness"] == "hermes")
            self.assertEqual(hermes["state"], "disabled")
            self.assertIsNone(hermes["detail"])

            harness.post_json("/api/agents/red-team/enable", {"harness": "hermes"})
            link = harness.spec.home / ".hermes" / "agents" / "red-team.md"
            self.assertTrue(link.is_symlink())
            self.assertEqual(self._state(self._entry(harness, "red-team"), "hermes"), "enabled")

    def test_codex_gets_a_rendered_toml_not_a_symlink(self) -> None:
        with AppTestHarness() as harness:
            harness.post_json(
                "/api/agents",
                {"name": "PR Reviewer", "description": "reviews", "prompt": "Be strict."},
            )
            harness.post_json("/api/agents/pr-reviewer/enable", {"harness": "codex"})

            rendered = harness.spec.home / ".codex" / "agents" / "pr-reviewer.toml"
            self.assertTrue(rendered.is_file())
            self.assertFalse(rendered.is_symlink())
            body = rendered.read_text(encoding="utf-8")
            self.assertIn('name = "pr_reviewer"', body)
            self.assertIn("harness-asset-manager:generated", body)

            # And it must not come back as an unmanaged row.
            refs = [e["ref"] for e in harness.get_json("/api/agents")["entries"]]
            self.assertEqual(refs, ["pr-reviewer"])

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

    def test_unmanaged_detail_inspects_the_harness_file(self) -> None:
        """GET /api/agents/<harness>/<slug> serves unmanaged detail."""
        def seed(spec: FakeHomeSpec) -> None:
            _seed_unmanaged_claude_agent(spec, "stray")
            _seed_unmanaged_codex_agent(spec, "auditor")

        with AppTestHarness(fixture_factory=seed) as harness:
            # Markdown unmanaged agent is editable in place
            detail = harness.get_json("/api/agents/claude/stray")
            self.assertEqual(detail["ref"], "claude/stray")
            self.assertEqual(detail["name"], "Stray")
            self.assertEqual(detail["description"], "found in claude")
            self.assertIn("harness body", detail["document"])
            self.assertTrue(detail["canEdit"])
            self.assertFalse(detail["canDelete"])
            self.assertIsNone(detail["storePath"])
            owner = next(h for h in detail["harnesses"] if h["harness"] == "claude")
            self.assertTrue(owner["path"].endswith("/.claude/agents/stray.md"))

            # Rendered (Codex TOML) unmanaged agent is not editable in place
            codex_detail = harness.get_json("/api/agents/codex/auditor")
            self.assertEqual(codex_detail["ref"], "codex/auditor")
            self.assertEqual(codex_detail["name"], "auditor")
            self.assertFalse(codex_detail["canEdit"])
            self.assertFalse(codex_detail["canDelete"])
            self.assertIsNone(codex_detail["storePath"])

    def test_unmanaged_edit_succeeds_and_preserves_custom_frontmatter_in_order(self) -> None:
        """PUT /api/agents/<harness>/<slug> rewrites the harness file in place."""
        def seed(spec: FakeHomeSpec) -> None:
            agents_dir = spec.home / ".claude" / "agents"
            agents_dir.mkdir(parents=True, exist_ok=True)
            (agents_dir / "stray.md").write_text(
                "---\n"
                "name: Stray\n"
                "description: found in claude\n"
                "model: claude-3-5-sonnet\n"
                "tools: Read, Grep\n"
                "customKey: customVal\n"
                "---\n\n"
                "harness body\n",
                encoding="utf-8",
            )

        with AppTestHarness(fixture_factory=seed) as harness:
            updated = harness.put_json(
                "/api/agents/claude/stray",
                {
                    "name": "Stray Agent",
                    "description": "updated description",
                    "prompt": "new harness prompt body",
                    "tools": ["Read", "Bash"],
                    "model": "claude-3-7-sonnet",
                    "metadata": [
                        {"key": "permissionMode", "value": "acceptEdits"},
                        {"key": "customKey", "value": "customVal2"},
                    ],
                },
            )
            self.assertEqual(updated["ref"], "claude/stray")
            self.assertEqual(updated["name"], "Stray Agent")
            self.assertEqual(updated["description"], "updated description")
            self.assertEqual(updated["prompt"], "new harness prompt body")
            self.assertEqual(updated["tools"], ["Read", "Bash"])
            self.assertEqual(updated["model"], "claude-3-7-sonnet")
            self.assertIsNone(updated["storePath"])

            config_dict = {c["key"]: c["value"] for c in updated["configuration"]}
            self.assertNotIn("model", config_dict)
            self.assertEqual(config_dict["permissionMode"], "acceptEdits")
            self.assertEqual(config_dict["customKey"], "customVal2")

            # File on disk was rewritten in place and remains a regular file, not a symlink
            harness_file = harness.spec.home / ".claude" / "agents" / "stray.md"
            self.assertTrue(harness_file.is_file())
            self.assertFalse(harness_file.is_symlink())
            self.assertFalse((harness.spec.agents_root / "stray.md").exists())

            content = harness_file.read_text(encoding="utf-8")
            self.assertIn("name: Stray Agent", content)
            self.assertIn("description: updated description", content)
            self.assertIn("model: claude-3-7-sonnet", content)
            self.assertIn("permissionMode: acceptEdits", content)
            self.assertIn("customKey: customVal2", content)
            self.assertIn("new harness prompt body", content)

            # Re-read detail via GET
            detail = harness.get_json("/api/agents/claude/stray")
            self.assertEqual(detail["name"], "Stray Agent")
            self.assertEqual(detail["description"], "updated description")

    def test_unmanaged_edit_without_metadata_preserves_custom_frontmatter(self) -> None:
        def seed(spec: FakeHomeSpec) -> None:
            agents_dir = spec.home / ".claude" / "agents"
            agents_dir.mkdir(parents=True, exist_ok=True)
            (agents_dir / "stray.md").write_text(
                "---\n"
                "name: Stray\n"
                "description: found in claude\n"
                "model: claude-3-5-sonnet\n"
                "tools: Read, Grep\n"
                "customKey: customVal\n"
                "---\n\n"
                "harness body\n",
                encoding="utf-8",
            )

        with AppTestHarness(fixture_factory=seed) as harness:
            updated = harness.put_json(
                "/api/agents/claude/stray",
                {
                    "name": "Stray Renamed",
                    "description": "new desc",
                },
            )
            self.assertEqual(updated["name"], "Stray Renamed")
            self.assertEqual(updated["description"], "new desc")
            self.assertEqual(updated["prompt"], "harness body")
            self.assertEqual(updated["tools"], ["Read", "Grep"])
            self.assertEqual(updated["model"], "claude-3-5-sonnet")

            config_dict = {c["key"]: c["value"] for c in updated["configuration"]}
            self.assertNotIn("model", config_dict)
            self.assertEqual(config_dict["customKey"], "customVal")

    def test_unmanaged_edit_model_and_effort_are_contract_fields(self) -> None:
        """model/effort ride their dedicated request fields: set, carried forward when
        omitted, and cleared by an explicit empty string — never via metadata rows."""

        def seed(spec: FakeHomeSpec) -> None:
            agents_dir = spec.home / ".claude" / "agents"
            agents_dir.mkdir(parents=True, exist_ok=True)
            (agents_dir / "stray.md").write_text(
                "---\n"
                "name: Stray\n"
                "description: found in claude\n"
                "customKey: customVal\n"
                "---\n\n"
                "harness body\n",
                encoding="utf-8",
            )

        with AppTestHarness(fixture_factory=seed) as harness:
            updated = harness.put_json(
                "/api/agents/claude/stray",
                {"name": "Stray", "description": "d", "prompt": "harness body", "model": "opus", "effort": "high"},
            )
            self.assertEqual(updated["model"], "opus")
            self.assertEqual(updated["effort"], "high")
            content = (harness.spec.home / ".claude" / "agents" / "stray.md").read_text(encoding="utf-8")
            self.assertIn("name: Stray\ndescription: d\nmodel: opus\neffort: high\n", content)

            # Omitted model/effort carry the current values forward.
            carried = harness.put_json(
                "/api/agents/claude/stray",
                {"name": "Stray", "description": "d2", "prompt": "harness body"},
            )
            self.assertEqual(carried["model"], "opus")
            self.assertEqual(carried["effort"], "high")

            # Explicit empty string clears the key.
            cleared = harness.put_json(
                "/api/agents/claude/stray",
                {"name": "Stray", "description": "d2", "prompt": "harness body", "effort": ""},
            )
            self.assertIsNone(cleared["effort"])
            self.assertEqual(cleared["model"], "opus")
            content = (harness.spec.home / ".claude" / "agents" / "stray.md").read_text(encoding="utf-8")
            self.assertNotIn("effort", content.split("---")[1])

    def test_unmanaged_edit_rendered_adapter_returns_400_and_leaves_file_untouched(self) -> None:
        with AppTestHarness(fixture_factory=_seed_unmanaged_codex_agent) as harness:
            codex_file = harness.spec.home / ".codex" / "agents" / "auditor.toml"
            before_content = codex_file.read_text(encoding="utf-8")

            resp = harness.put_json(
                "/api/agents/codex/auditor",
                {"name": "auditor", "description": "new desc"},
                expected_status=409,
            )
            self.assertIn("adopt it before editing", resp.get("error", resp.get("detail", "")))
            self.assertEqual(codex_file.read_text(encoding="utf-8"), before_content)

    def test_unmanaged_edit_rejects_missing_and_unsafe_slug(self) -> None:
        with AppTestHarness(fixture_factory=_seed_unmanaged_claude_agent) as harness:
            harness.put_json(
                "/api/agents/claude/missing",
                {"name": "Missing", "description": "d"},
                expected_status=404,
            )
            harness.put_json(
                "/api/agents/claude/../escape",
                {"name": "Escape", "description": "d"},
                expected_status=404,
            )
            harness.put_json(
                "/api/agents/claude/.",
                {"name": "Dot", "description": "d"},
                expected_status=404,
            )

    def test_unmanaged_edit_requires_name_and_description(self) -> None:
        with AppTestHarness(fixture_factory=_seed_unmanaged_claude_agent) as harness:
            harness_file = harness.spec.home / ".claude" / "agents" / "stray.md"
            before_content = harness_file.read_text(encoding="utf-8")

            # Missing both
            harness.put_json(
                "/api/agents/claude/stray",
                {"prompt": "new prompt"},
                expected_status=409,
            )
            # Missing description
            harness.put_json(
                "/api/agents/claude/stray",
                {"name": "New Name"},
                expected_status=409,
            )
            # Missing name
            harness.put_json(
                "/api/agents/claude/stray",
                {"description": "New Desc"},
                expected_status=409,
            )
            self.assertEqual(harness_file.read_text(encoding="utf-8"), before_content)

    def test_unmanaged_detail_rejects_unsafe_refs_and_missing_files(self) -> None:
        with AppTestHarness(fixture_factory=_seed_unmanaged_claude_agent) as harness:
            harness.get_json("/api/agents/claude/../escape", expected_status=404)
            harness.get_json("/api/agents/claude/missing", expected_status=404)

    def test_unmanaged_agent_lifecycle_edit_then_adopt_and_manage(self) -> None:
        """Complete lifecycle: unmanaged -> in-place edit -> list -> adopt -> managed edit."""
        with AppTestHarness(fixture_factory=_seed_unmanaged_claude_agent) as harness:
            # 1. Start with unmanaged agent
            entry = self._entry(harness, "claude/stray")
            self.assertEqual(entry["kind"], "unmanaged")
            self.assertTrue(entry["actions"]["canAdopt"])

            # 2. In-place edit while unmanaged
            updated = harness.put_json(
                "/api/agents/claude/stray",
                {
                    "name": "Stray Master",
                    "description": "edited in harness",
                    "prompt": "harness prompt v2",
                    "tools": ["Read", "Edit"],
                    "metadata": [{"key": "customKey", "value": "customVal"}],
                },
            )
            self.assertEqual(updated["name"], "Stray Master")
            self.assertEqual(updated["description"], "edited in harness")

            # 3. List agents: inventory reflects the in-place edit
            entry = self._entry(harness, "claude/stray")
            self.assertEqual(entry["name"], "Stray Master")
            self.assertEqual(entry["description"], "edited in harness")

            # 4. Adopt the edited unmanaged agent
            adopt_res = harness.post_json("/api/agents/claude/stray/adopt", {})
            self.assertTrue(adopt_res["ok"])
            self.assertEqual(adopt_res["ref"], "stray")

            # 5. Now it is managed in the store
            managed_detail = harness.get_json("/api/agents/stray")
            self.assertEqual(managed_detail["name"], "Stray Master")
            self.assertEqual(managed_detail["prompt"], "harness prompt v2")
            self.assertEqual(managed_detail["tools"], ["Read", "Edit"])
            self.assertIsNotNone(managed_detail["storePath"])
            self.assertTrue(managed_detail["canDelete"])

            config_dict = {c["key"]: c["value"] for c in managed_detail["configuration"]}
            self.assertEqual(config_dict["customKey"], "customVal")

            # 6. Subsequent managed edit updates the store and linked harness
            managed_updated = harness.put_json(
                "/api/agents/stray",
                {
                    "name": "Stray Final",
                    "description": "final description",
                    "prompt": "final prompt",
                    "tools": ["Bash"],
                },
            )
            self.assertEqual(managed_updated["name"], "Stray Final")
            harness_file = harness.spec.home / ".claude" / "agents" / "stray.md"
            self.assertTrue(harness_file.is_symlink())
            self.assertIn("name: Stray Final", harness_file.read_text(encoding="utf-8"))

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

            self.assertEqual(conflict["code"], "agent_conflict")
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

    def test_detail_carries_everything_the_detail_view_needs(self) -> None:
        with AppTestHarness() as harness:
            harness.post_json(
                "/api/agents",
                {
                    "name": "Red Team",
                    "description": "probes systems",
                    "prompt": "Be adversarial.",
                    "tools": ["Read", "Bash"],
                },
            )
            harness.post_json("/api/agents/red-team/enable", {"harness": "claude"})
            harness.post_json("/api/agents/red-team/enable", {"harness": "codex"})

            detail = harness.get_json("/api/agents/red-team")

            self.assertEqual(detail["name"], "Red Team")
            self.assertEqual(detail["description"], "probes systems")
            self.assertEqual(detail["prompt"], "Be adversarial.")
            self.assertEqual(detail["tools"], ["Read", "Bash"])
            self.assertTrue(detail["document"].startswith("---"))
            self.assertTrue(detail["storePath"].endswith("/agents/red-team.md"))

            by_harness = {h["harness"]: h for h in detail["harnesses"]}
            # Every column from the matrix is present, so the two agree.
            columns = [c["harness"] for c in harness.get_json("/api/agents")["columns"]]
            self.assertEqual(list(by_harness), columns)

            self.assertEqual(by_harness["claude"]["state"], "enabled")
            self.assertEqual(by_harness["claude"]["installMethod"], "symlink")
            self.assertTrue(by_harness["claude"]["path"].endswith(".claude/agents/red-team.md"))

            # Codex is rendered, not linked — the detail view says so.
            self.assertEqual(by_harness["codex"]["installMethod"], "rendered")
            self.assertTrue(by_harness["codex"]["path"].endswith(".codex/agents/red-team.toml"))

            self.assertEqual(by_harness["hermes"]["state"], "disabled")
            self.assertEqual(by_harness["hermes"]["installMethod"], "symlink")
            self.assertTrue(by_harness["hermes"]["path"].endswith(".hermes/agents/red-team.md"))

    def test_detail_surfaces_frontmatter_and_an_edit_preserves_it(self) -> None:
        """Adopt a real-shaped Claude agent, read its config, edit, config survives."""

        def seed(spec: FakeHomeSpec) -> None:
            agents = spec.home / ".claude" / "agents"
            agents.mkdir(parents=True, exist_ok=True)
            (agents / "bookman.md").write_text(
                "---\n"
                "name: Bookman\n"
                "description: Vault librarian.\n"
                "model: sonnet\n"
                "tools: Read, Grep\n"
                'permissionMode: "acceptEdits"\n'
                "maxTurns: 50\n"
                "disallowedTools: []\n"
                "hooks:\n"
                "  PreToolUse:\n"
                "    - matcher: Bash\n"
                "---\n\nIndex the vault.\n",
                encoding="utf-8",
            )

        with AppTestHarness(fixture_factory=seed) as harness:
            harness.post_json("/api/agents/claude/bookman/adopt", {})

            detail = harness.get_json("/api/agents/bookman")
            config = {row["key"]: row["value"] for row in detail["configuration"]}
            self.assertEqual(detail["description"], "Vault librarian.")
            self.assertEqual(detail["model"], "sonnet")
            self.assertEqual(detail["effort"], None)
            self.assertNotIn("model", config)
            self.assertEqual(config["permissionMode"], "acceptEdits")
            self.assertEqual(config["maxTurns"], "50")
            self.assertEqual(config["disallowedTools"], "[]")
            self.assertEqual(config["hooks"], "(1 entry)")
            # name/description have their own places in the view.
            self.assertNotIn("name", config)
            self.assertNotIn("description", config)

            harness.put_json("/api/agents/bookman", {"description": "Updated."})

            after = harness.get_json("/api/agents/bookman")
            after_config = {row["key"]: row["value"] for row in after["configuration"]}
            self.assertEqual(after["description"], "Updated.")
            self.assertEqual(after_config, config)

    def test_detail_of_a_missing_agent_is_404(self) -> None:
        with AppTestHarness() as harness:
            payload = harness.get_json("/api/agents/nope", expected_status=404)
            self.assertIn("nope", payload["error"])

    def test_update_preserves_fields_the_client_omits(self) -> None:
        """The edit form must not be able to blank a field by leaving it out.

        The first cut of EditAgentDialog opened with empty inputs and submitted them,
        renaming the agent to its slug and wiping description/prompt/tools.
        """
        with AppTestHarness() as harness:
            harness.post_json(
                "/api/agents",
                {
                    "name": "Red Team",
                    "description": "probes systems",
                    "prompt": "Be adversarial.",
                    "tools": ["Read"],
                },
            )

            updated = harness.put_json("/api/agents/red-team", {"description": "new blurb"})

            self.assertEqual(updated["description"], "new blurb")
            self.assertEqual(updated["name"], "Red Team")
            self.assertEqual(updated["prompt"], "Be adversarial.")
            self.assertEqual(updated["tools"], ["Read"])

    def test_unknown_harness_is_refused(self) -> None:
        with AppTestHarness() as harness:
            harness.post_json(
                "/api/agents", {"name": "Red Team", "description": "d", "prompt": "p"}
            )
            payload = harness.post_json(
                "/api/agents/red-team/enable", {"harness": "nope"}, expected_status=409
            )
            self.assertIn("nope", payload["error"])

    def test_binding_ledger_lands_in_the_data_dir_and_follows_the_binding(self) -> None:
        """Proves the container wiring, not just the service: the ledger path is
        resolved from the data dir (so it moves with the pending rename) and the
        routers' mutations reach it."""
        with AppTestHarness() as harness:
            ledger_path = harness.container.paths.bindings_ledger_path
            self.assertEqual(ledger_path.parent, harness.container.paths.data_dir)

            harness.post_json(
                "/api/agents", {"name": "Red Team", "description": "d", "prompt": "p"}
            )
            harness.post_json("/api/agents/red-team/enable", {"harness": "claude"})
            self.assertIn(
                "claude", json.loads(ledger_path.read_text("utf-8"))["agents"]["red-team"]
            )

            harness.post_json("/api/agents/red-team/disable", {"harness": "claude"})
            self.assertEqual(json.loads(ledger_path.read_text("utf-8"))["agents"], {})

    def test_a_one_sided_clobber_is_repaired_automatically(self) -> None:
        """The end-to-end case the whole ledger exists for: a harness replaces our
        symlink with its own edited copy, exactly as an atomic editor would. The store
        has not moved since we linked, so that copy holds the only edit — folding it
        back in discards nothing, and Stage 3 does it without asking."""
        with AppTestHarness() as harness:
            harness.put_json(
                "/api/settings/auto-adopt/agents/harnesses", {"harnesses": ["claude"]}
            )
            harness.post_json(
                "/api/agents", {"name": "Red Team", "description": "d", "prompt": "p"}
            )
            harness.post_json("/api/agents/red-team/enable", {"harness": "claude"})

            binding = harness.spec.home / ".claude" / "agents" / "red-team.md"
            self.assertTrue(binding.is_symlink())
            binding.unlink()
            binding.write_text(
                "---\nname: Red Team\ndescription: d\n---\nedited by the harness\n",
                encoding="utf-8",
            )

            payload = harness.get_json("/api/agents")
            entry = next(e for e in payload["entries"] if e["ref"] == "red-team")
            claude = next(b for b in entry["bindings"] if b["harness"] == "claude")
            self.assertEqual(claude["state"], "enabled")
            self.assertTrue(binding.is_symlink())

            store_file = harness.spec.agents_root / "red-team.md"
            self.assertIn("edited by the harness", store_file.read_text(encoding="utf-8"))

            # Invariant 5: nothing is repaired silently.
            actions = [a for a in harness.container.agents_audit.recent() if a.ref == "red-team"]
            self.assertEqual([a.action for a in actions], ["adopted"])
            self.assertEqual(actions[0].ref, "red-team")

    def test_auto_adopt_off_leaves_the_drift_diagnosed_but_untouched(self) -> None:
        """The kill switch, over the wire. Stage 2's diagnosis is what remains."""
        with AppTestHarness() as harness:
            harness.put_json("/api/settings/auto-adopt/agents", {"enabled": False})
            harness.post_json(
                "/api/agents", {"name": "Red Team", "description": "d", "prompt": "p"}
            )
            harness.post_json("/api/agents/red-team/enable", {"harness": "claude"})

            binding = harness.spec.home / ".claude" / "agents" / "red-team.md"
            binding.unlink()
            binding.write_text(
                "---\nname: Red Team\ndescription: d\n---\nedited by the harness\n",
                encoding="utf-8",
            )

            payload = harness.get_json("/api/agents")
            entry = next(e for e in payload["entries"] if e["ref"] == "red-team")
            claude = next(b for b in entry["bindings"] if b["harness"] == "claude")
            self.assertEqual(claude["state"], "disabled")
            self.assertEqual(claude["detail"], "the link was replaced by an edited file")
            self.assertFalse(binding.is_symlink())
            self.assertEqual(harness.container.agents_audit.recent(), ())

    def test_auto_adopt_defaults_enable_additional_harnesses(self) -> None:
        with AppTestHarness() as harness:
            harness.put_json(
                "/api/settings/auto-adopt/agents/harnesses",
                {"harnesses": ["claude", "codex"]},
            )
            harness.post_json(
                "/api/agents", {"name": "Red Team", "description": "d", "prompt": "p"}
            )
            harness.post_json("/api/agents/red-team/enable", {"harness": "claude"})

            binding = harness.spec.home / ".claude" / "agents" / "red-team.md"
            binding.unlink()
            binding.write_text(
                "---\nname: Red Team\ndescription: d\n---\nedited by the harness\n",
                encoding="utf-8",
            )

            harness.get_json("/api/agents")

            codex_path = harness.spec.home / ".codex" / "agents" / "red-team.toml"
            self.assertTrue(codex_path.is_file())
            self.assertEqual(
                tomllib.loads(codex_path.read_text(encoding="utf-8"))["description"],
                "d",
            )

    def test_a_two_sided_conflict_is_never_resolved_automatically(self) -> None:
        """Both sides hold edits, so no choice can be made without discarding one."""
        with AppTestHarness() as harness:
            harness.post_json(
                "/api/agents", {"name": "Red Team", "description": "d", "prompt": "p"}
            )
            harness.post_json("/api/agents/red-team/enable", {"harness": "claude"})

            binding = harness.spec.home / ".claude" / "agents" / "red-team.md"
            binding.unlink()
            binding.write_text(
                "---\nname: Red Team\ndescription: d\n---\nharness edit\n",
                encoding="utf-8",
            )
            harness.put_json("/api/agents/red-team", {"prompt": "store edit"})

            payload = harness.get_json("/api/agents")
            entry = next(e for e in payload["entries"] if e["ref"] == "red-team")
            claude = next(b for b in entry["bindings"] if b["harness"] == "claude")
            self.assertEqual(claude["state"], "disabled")
            self.assertEqual(
                claude["detail"], "the link was replaced and both copies have changed"
            )
            # Neither side moved, and nothing was recorded as done.
            self.assertIn("harness edit", binding.read_text(encoding="utf-8"))
            self.assertIn("store edit", (harness.spec.agents_root / "red-team.md").read_text("utf-8"))
            self.assertEqual(harness.container.agents_audit.recent(), ())

    def test_two_harnesses_with_differing_edits_are_preserved_not_merged(self) -> None:
        """§4's multi-harness rule, the case that must never be guessed. Two harnesses
        each clobbered the link and each made a *different* edit. Picking either one
        discards the other's work, so nothing is adopted, nothing is deleted, and each
        divergent copy is preserved for the user to choose from."""
        with AppTestHarness() as harness:
            harness.put_json("/api/settings/auto-adopt/agents", {"enabled": True})
            harness.post_json(
                "/api/agents", {"name": "Red Team", "description": "d", "prompt": "p"}
            )
            for target in ("claude", "cursor"):
                harness.post_json("/api/agents/red-team/enable", {"harness": target})

            bindings = {
                "claude": harness.spec.home / ".claude" / "agents" / "red-team.md",
                "cursor": harness.spec.home / ".cursor" / "agents" / "red-team.md",
            }
            for target, path in bindings.items():
                self.assertTrue(path.is_symlink(), f"{target} was not linked")
                path.unlink()
                path.write_text(
                    f"---\nname: Red Team\ndescription: d\n---\n{target} made this edit\n",
                    encoding="utf-8",
                )

            store_file = harness.spec.agents_root / "red-team.md"
            store_before = store_file.read_text(encoding="utf-8")

            payload = harness.get_json("/api/agents")

            # Nothing adopted: the store is byte-for-byte what it was.
            self.assertEqual(store_file.read_text(encoding="utf-8"), store_before)
            # Nothing deleted: both harness copies are still exactly where they were.
            for target, path in bindings.items():
                self.assertFalse(path.is_symlink())
                self.assertIn(f"{target} made this edit", path.read_text(encoding="utf-8"))
            # Both sides preserved where the user can find them.
            conflicts = harness.container.paths.agents_conflicts_root
            for target in bindings:
                preserved = conflicts / f"red-team.{target}.md"
                self.assertTrue(preserved.is_file(), f"missing {preserved}")
                self.assertIn(f"{target} made this edit", preserved.read_text(encoding="utf-8"))
            # And the user is told, once, naming every side.
            reasons = [i["reason"] for i in payload["issues"] if "conflicting edits" in i["reason"]]
            self.assertEqual(len(reasons), 1, payload["issues"])
            self.assertIn("claude", reasons[0])
            self.assertIn("cursor", reasons[0])
            # A preserved copy must never be readable back as an agent.
            self.assertNotIn("red-team.claude", [e["ref"] for e in payload["entries"]])

    def test_reconcile_is_idempotent_across_list_requests(self) -> None:
        with AppTestHarness() as harness:
            harness.post_json(
                "/api/agents", {"name": "Red Team", "description": "d", "prompt": "p"}
            )
            harness.post_json("/api/agents/red-team/enable", {"harness": "claude"})
            binding = harness.spec.home / ".claude" / "agents" / "red-team.md"
            binding.unlink()
            binding.write_text(
                "---\nname: Red Team\ndescription: d\n---\nedited\n", encoding="utf-8"
            )

            harness.get_json("/api/agents")
            after_first = (harness.spec.agents_root / "red-team.md").read_text("utf-8")
            actions_first = len(harness.container.agents_audit.recent())

            harness.get_json("/api/agents")
            harness.get_json("/api/agents")
            self.assertEqual(
                (harness.spec.agents_root / "red-team.md").read_text("utf-8"), after_first
            )
            self.assertEqual(len(harness.container.agents_audit.recent()), actions_first)

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

    def test_inventory_excludes_disabled_and_undetected_harnesses(self) -> None:
        with AppTestHarness() as harness:
            # 1. Undetected harness (droid without CLI or root dir) excluded from columns
            payload = harness.get_json("/api/agents")
            cols = [col["harness"] for col in payload["columns"]]
            self.assertIn("claude", cols)
            self.assertIn("codex", cols)
            self.assertIn("hermes", cols)
            self.assertNotIn("droid", cols)

            # 2. Disabling claude in settings drops it from columns
            harness.put_json("/api/settings/harnesses/claude/support", {"enabled": False})

            payload_disabled = harness.get_json("/api/agents")
            cols_disabled = [col["harness"] for col in payload_disabled["columns"]]
            self.assertNotIn("claude", cols_disabled)
            self.assertIn("codex", cols_disabled)

            # 3. Entry bindings agree with filtered columns
            harness.post_json(
                "/api/agents",
                {
                    "name": "Red Team",
                    "description": "probes systems",
                    "prompt": "Be adversarial.",
                },
            )
            payload_with_agent = harness.get_json("/api/agents")
            entry = payload_with_agent["entries"][0]
            binding_harnesses = [b["harness"] for b in entry["bindings"]]
            self.assertNotIn("claude", binding_harnesses)
            self.assertNotIn("droid", binding_harnesses)
            self.assertIn("codex", binding_harnesses)

            # 4. Detail harnesses agree with filtered columns
            detail = harness.get_json("/api/agents/red-team")
            detail_harnesses = [h["harness"] for h in detail["harnesses"]]
            self.assertNotIn("claude", detail_harnesses)
            self.assertNotIn("droid", detail_harnesses)
            self.assertIn("codex", detail_harnesses)

    def test_agent_skills_creation_validation_and_resolution(self) -> None:
        with AppTestHarness(mixed=True) as harness:
            # 1. Unknown skill fails with 400
            err = harness.post_json(
                "/api/agents",
                {
                    "name": "Invalid Agent",
                    "description": "desc",
                    "prompt": "prompt",
                    "skills": ["nonexistent-skill"],
                },
                expected_status=400,
            )
            self.assertEqual(err.get("code"), "invalid_skill")

            # 2. Unmanaged skill fails with 400
            err_unmanaged = harness.post_json(
                "/api/agents",
                {
                    "name": "Invalid Agent 2",
                    "description": "desc",
                    "prompt": "prompt",
                    "skills": ["trace-lens"],
                },
                expected_status=400,
            )
            self.assertEqual(err_unmanaged.get("code"), "invalid_skill")

            # 3. Managed skill succeeds and resolves display name
            created = harness.post_json(
                "/api/agents",
                {
                    "name": "Audit Agent",
                    "description": "Performs audits",
                    "prompt": "Audit thoroughly.",
                    "skills": ["shared-audit"],
                },
            )
            self.assertEqual(
                created["skills"],
                [{"slug": "shared-audit", "name": "Shared Audit"}],
            )

            # 4. Inventory entry exposes parsed skills
            entry = self._entry(harness, "audit-agent")
            self.assertEqual(
                entry["skills"],
                [{"slug": "shared-audit", "name": "Shared Audit"}],
            )

            # 5. Detail exposes parsed skills
            detail = harness.get_json("/api/agents/audit-agent")
            self.assertEqual(
                detail["skills"],
                [{"slug": "shared-audit", "name": "Shared Audit"}],
            )

    def test_agent_skills_auto_enable_on_save(self) -> None:
        with AppTestHarness(mixed=True) as harness:
            # 1. Create agent without skills
            harness.post_json(
                "/api/agents",
                {
                    "name": "Reviewer",
                    "description": "Reviews code",
                    "prompt": "Review code.",
                },
            )

            # 2. Enable agent on claude
            harness.post_json("/api/agents/reviewer/enable", {"harness": "claude"})
            self.assertEqual(self._state(self._entry(harness, "reviewer"), "claude"), "enabled")

            # Verify skill is not yet enabled on claude
            claude_skill_link = harness.spec.claude_root / "shared-audit"
            self.assertFalse(claude_skill_link.exists())

            # 3. Update agent to attach shared-audit
            resp = harness.put_json(
                "/api/agents/reviewer",
                {
                    "skills": ["shared-audit"],
                },
            )
            self.assertTrue(resp.get("ok"))
            self.assertEqual(
                resp.get("autoEnabled"),
                [{"skillRef": "shared:shared-audit", "harness": "claude"}],
            )
            self.assertEqual(resp.get("failed"), [])

            # Skill is now auto-enabled on claude!
            self.assertTrue(claude_skill_link.is_symlink())

            # 4. Non-destructive removal: dropping skill does NOT disable it on claude
            resp_drop = harness.put_json(
                "/api/agents/reviewer",
                {
                    "skills": [],
                },
            )
            self.assertEqual(resp_drop["skills"], [])
            self.assertTrue(claude_skill_link.is_symlink())

    def test_a_failing_auto_enable_still_saves_the_agent_and_reports_the_failure(self) -> None:
        """A save that half-applies must say so rather than reporting success.

        Auto-enabling a skill touches other harnesses and can fail on any of them.
        The agent edit is the user's actual intent, so it is written first and kept;
        the auto-enable is best effort. What must never happen is the edit landing
        while the response claims every skill was enabled.
        """
        with AppTestHarness(mixed=True) as harness:
            harness.post_json(
                "/api/agents",
                {"name": "Reviewer", "description": "Reviews code", "prompt": "Review code."},
            )
            harness.post_json("/api/agents/reviewer/enable", {"harness": "claude"})

            container = harness.container
            original = container.skills_mutations.enable_skill

            def failing_enable(skill_ref: str, harness_id: str):
                raise RuntimeError("harness went away mid-save")

            container.skills_mutations.enable_skill = failing_enable
            try:
                resp = harness.put_json(
                    "/api/agents/reviewer",
                    {"description": "Reviews code carefully", "skills": ["shared-audit"]},
                )
            finally:
                container.skills_mutations.enable_skill = original

            # The failure is reported, not swallowed into a success.
            self.assertFalse(resp.get("ok"))
            self.assertEqual(resp.get("autoEnabled"), [])
            self.assertEqual(
                [(f["skillRef"], f["harness"]) for f in resp.get("failed", [])],
                [("shared:shared-audit", "claude")],
            )
            self.assertIn("harness went away mid-save", resp["failed"][0]["error"])

            # Nothing was half-linked on the harness side: the save reports exactly
            # the state on disk rather than a binding it did not manage to create.
            self.assertFalse((harness.spec.claude_root / "shared-audit").exists())

            # The agent edit itself survived, and is on disk -- not rolled back.
            self.assertEqual(resp["description"], "Reviews code carefully")
            self.assertEqual([s["slug"] for s in resp["skills"]], ["shared-audit"])
            stored = (harness.spec.agents_root / "reviewer.md").read_text(encoding="utf-8")
            self.assertIn("shared-audit", stored)
            self.assertIn("Reviews code carefully", stored)


if __name__ == "__main__":
    unittest.main()
