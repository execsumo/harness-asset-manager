from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness_asset_manager.application.adopt import (
    AdoptionAction,
    AdoptionApplier,
    AdoptionPlanner,
)
from harness_asset_manager.application.container import build_backend_container
from harness_asset_manager.application.hooks.store import HookSpec
from harness_asset_manager.application.mcp.store import McpServerSpec, McpSource
from harness_asset_manager.application.permissions.store import PermissionSpec
from harness_asset_manager.application.slash_commands.models import SlashCommand
from tests.support.fake_home import (
    FakeHomeSpec,
    seed_skill_package,
    write_cli_stub,
)


class AdoptApplierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.spec = FakeHomeSpec(
            root=self.tmp_path,
            home=self.tmp_path / "Users" / "alice",
            xdg_config_home=self.tmp_path / "Users" / "alice" / ".config",
            xdg_data_home=self.tmp_path / "Users" / "alice" / ".local" / "share",
            xdg_state_home=self.tmp_path / "Users" / "alice" / ".local" / "state",
        )
        for p in (
            self.spec.skills_store_root,
            self.spec.agents_root,
            self.spec.codex_root,
            self.spec.claude_root,
            self.spec.cursor_root,
            self.spec.xdg_state_home,
            self.spec.bin_dir,
            self.spec.home / ".claude" / "agents",
            self.spec.home / ".codex" / "agents",
            self.spec.home / ".codex" / "prompts",
        ):
            p.mkdir(parents=True, exist_ok=True)
        for executable in ("codex", "claude", "cursor-agent", "opencode", "agy"):
            write_cli_stub(self.spec.bin_dir / executable, executable)

        self.container = build_backend_container(self.spec.env())

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_apply_creates_bindings_across_all_six_families(self) -> None:
        # 1. Skill
        skill_src = seed_skill_package(self.spec.home / "downloads", "my-skill", "My Skill")
        dest = self.container.skills_store.ingest(
            source_path=skill_src,
            declared_name="My Skill",
            source_kind="github",
            source_locator="github:org/my-skill",
            source_ref="main",
        )
        self.container.skills_mutations.enable_managed_package(dest, "claude")
        # Unlink local link so it is linkable
        (self.spec.claude_root / "my-skill").unlink()

        # 2. Agent
        self.container.agents_store.create(name="Reviewer", description="reviews", prompt="review code")
        self.container.agents_mutations.enable("reviewer", "claude")
        (self.spec.home / ".claude" / "agents" / "reviewer.md").unlink()

        # 3. Slash command
        self.container.slash_command_store.create_command(
            SlashCommand(name="lint", description="lint code", prompt="lint prompt")
        )
        self.container.slash_command_mutations.sync_command("lint", targets=["codex"])
        (self.spec.home / ".codex" / "prompts" / "lint.md").unlink()

        # 4. MCP server
        mcp_spec = McpServerSpec(
            name="exa",
            display_name="Exa",
            source=McpSource.manual("exa"),
            transport="stdio",
            command="npx",
            args=("-y", "exa-mcp-server"),
            enabled_harnesses=("claude",),
        )
        self.container.mcp_store.upsert_managed(mcp_spec)

        # 5. Hook
        hook_spec = HookSpec(
            id="my-hook",
            event="pre_tool_use",
            command="flake8",
            match="file_write",
            enabled_harnesses=("claude",),
        )
        self.container.hooks_store.upsert_managed(hook_spec)

        # 6. Permission
        perm_spec = PermissionSpec(
            id="block-secrets",
            decision="deny",
            scope="file_read",
            pattern="/secrets/**",
            enabled_harnesses=("claude",),
        )
        self.container.permissions_store.upsert_managed(perm_spec)

        # Plan
        planner = AdoptionPlanner.from_container(self.container)
        plan = planner.plan()
        self.assertEqual(len(plan.linkable), 6)

        # Apply
        applier = AdoptionApplier(self.container)
        results = applier.apply(plan.linkable)
        self.assertEqual(len(results), 6)
        self.assertTrue(all(r.status == "applied" for r in results))

        # Verify bindings live on disk
        self.assertTrue((self.spec.claude_root / "my-skill").is_symlink())
        self.assertTrue((self.spec.home / ".claude" / "agents" / "reviewer.md").is_symlink())
        self.assertTrue((self.spec.home / ".codex" / "prompts" / "lint.md").is_file())

        # Verify MCP live on disk
        claude_mcp_adapter = self.container.mcp_read_models.require_enabled_adapter("claude")
        self.assertTrue(claude_mcp_adapter.has_binding("exa"))

        # Verify Hook live on disk
        claude_hook_adapter = self.container.hooks_read_models.require_enabled_adapter("claude")
        self.assertTrue(claude_hook_adapter.has_binding("my-hook"))

        # Verify Permission live on disk
        claude_perm_adapter = self.container.permissions_read_models.require_enabled_adapter("claude")
        self.assertTrue(claude_perm_adapter.has_binding("block-secrets"))

        # Audit events recorded
        events = self.container.mutation_audit.read_recent(limit=20)
        adopt_events = [e for e in events if e.get("operation") == "adopt"]
        self.assertEqual(len(adopt_events), 6)
        self.assertTrue(all(e.get("outcome") == "succeeded" for e in adopt_events))

        # Idempotence: re-planning yields zero linkable actions; all are skipped
        re_plan = planner.plan()
        self.assertEqual(len(re_plan.linkable), 0)
        self.assertEqual(len(re_plan.skipped), 6)
        self.assertTrue(all(a.reason == "already-linked" for a in re_plan.skipped))

    def test_apply_rechecks_occupied_target_and_refuses_overwrite(self) -> None:
        self.container.agents_store.create(name="Reviewer", description="reviews", prompt="review code")
        self.container.agents_mutations.enable("reviewer", "claude")
        claude_link = self.spec.home / ".claude" / "agents" / "reviewer.md"
        claude_link.unlink()

        # Create action with action="link"
        action = AdoptionAction(
            family="agents",
            ref="reviewer",
            display_name="Reviewer",
            harness="claude",
            action="link",
            target=claude_link,
        )

        # Now before apply runs, target becomes occupied by a foreign file
        claude_link.write_text("pre-existing foreign file", encoding="utf-8")

        applier = AdoptionApplier(self.container)
        results = applier.apply([action], allow_conflicts=False)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "failed")
        self.assertIn("occupied", results[0].error or "")

        # Target file was left completely untouched
        self.assertEqual(claude_link.read_text(encoding="utf-8"), "pre-existing foreign file")

    def test_apply_aggregates_failures_without_aborting(self) -> None:
        # One valid agent and one missing agent
        self.container.agents_store.create(name="GoodAgent", description="good", prompt="prompt")
        self.container.agents_mutations.enable("goodagent", "claude")
        good_link = self.spec.home / ".claude" / "agents" / "goodagent.md"
        good_link.unlink()

        action_bad = AdoptionAction(
            family="agents",
            ref="non-existent",
            display_name="Bad",
            harness="claude",
            action="link",
            target=self.spec.home / ".claude" / "agents" / "non-existent.md",
        )
        action_good = AdoptionAction(
            family="agents",
            ref="goodagent",
            display_name="GoodAgent",
            harness="claude",
            action="link",
            target=good_link,
        )

        applier = AdoptionApplier(self.container)
        results = applier.apply([action_bad, action_good])

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].status, "failed")
        self.assertEqual(results[1].status, "applied")
        self.assertTrue(good_link.is_symlink())

    def test_apply_is_additive_and_preserves_unselected_slash_command_intent(self) -> None:
        self.container.slash_command_store.create_command(
            SlashCommand(name="lint", description="lint", prompt="prompt")
        )
        # machine A had lint synced to codex AND cursor
        self.container.slash_command_mutations.sync_command("lint", targets=["codex", "cursor"])
        codex_file = self.spec.home / ".codex" / "prompts" / "lint.md"
        codex_file.unlink()

        # Suppose user only applies codex
        action_codex = AdoptionAction(
            family="slash_commands",
            ref="lint",
            display_name="lint",
            harness="codex",
            action="link",
            target=codex_file,
        )

        applier = AdoptionApplier(self.container)
        results = applier.apply([action_codex])
        self.assertEqual(results[0].status, "applied")
        self.assertTrue(codex_file.is_file())

        # Verify cursor intent was preserved in sync-state.json
        state = self.container.slash_command_sync_state.load()
        self.assertIn("cursor", state.get("lint", {}))
        self.assertIn("codex", state.get("lint", {}))

    def test_apply_config_merge_key_conflict_and_allow_conflicts(self) -> None:
        spec = McpServerSpec(
            name="exa",
            display_name="Exa",
            source=McpSource.manual("exa"),
            transport="stdio",
            command="npx",
            args=("-y", "exa-mcp-server"),
            enabled_harnesses=("cursor",),
        )
        self.container.mcp_store.upsert_managed(spec)

        cursor_adapter = self.container.mcp_read_models.require_enabled_adapter("cursor")
        foreign_spec = McpServerSpec(
            name="exa",
            display_name="Exa",
            source=McpSource.manual("exa"),
            transport="stdio",
            command="foreign-command",
        )
        cursor_adapter.enable_server(foreign_spec)
        orig_content = cursor_adapter.config_path.read_text(encoding="utf-8")

        action = AdoptionAction(
            family="mcp",
            ref="exa",
            display_name="Exa",
            harness="cursor",
            action="conflict",
            target=cursor_adapter.config_path,
        )

        applier = AdoptionApplier(self.container)

        # 1. Applying without allow_conflicts -> fails, config untouched
        results = applier.apply([action], allow_conflicts=False)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "failed")
        self.assertIn("occupied", results[0].error or "")
        self.assertEqual(cursor_adapter.config_path.read_text(encoding="utf-8"), orig_content)

        # 2. Applying with allow_conflicts=True -> succeeds, config overwritten with store version
        results = applier.apply([action], allow_conflicts=True)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].status, "applied")
        doc = json.loads(cursor_adapter.config_path.read_text(encoding="utf-8"))
        self.assertEqual(doc["mcpServers"]["exa"]["command"], "npx")

    def test_apply_config_merge_is_additive(self) -> None:
        claude_adapter = self.container.mcp_read_models.require_enabled_adapter("claude")
        existing_spec = McpServerSpec(
            name="preexisting",
            display_name="PreExisting",
            source=McpSource.manual("preexisting"),
            transport="stdio",
            command="existing-cmd",
        )
        claude_adapter.enable_server(existing_spec)

        # Now adopt a new server
        spec = McpServerSpec(
            name="new-server",
            display_name="NewServer",
            source=McpSource.manual("new-server"),
            transport="stdio",
            command="new-cmd",
            enabled_harnesses=("claude",),
        )
        self.container.mcp_store.upsert_managed(spec)

        action = AdoptionAction(
            family="mcp",
            ref="new-server",
            display_name="NewServer",
            harness="claude",
            action="link",
            target=claude_adapter.config_path,
        )

        applier = AdoptionApplier(self.container)
        results = applier.apply([action])
        self.assertEqual(results[0].status, "applied")

        # Both pre-existing and new servers exist in the config
        doc = json.loads(claude_adapter.config_path.read_text(encoding="utf-8"))
        self.assertIn("preexisting", doc["mcpServers"])
        self.assertIn("new-server", doc["mcpServers"])


if __name__ == "__main__":
    unittest.main()
