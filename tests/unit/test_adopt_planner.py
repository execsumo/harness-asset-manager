from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness_asset_manager.application.adopt import AdoptionPlanner
from harness_asset_manager.application.container import build_backend_container
from harness_asset_manager.application.hooks.store import HookSpec
from harness_asset_manager.application.mcp.store import McpServerSpec, McpSource
from harness_asset_manager.application.permissions.store import PermissionSpec
from harness_asset_manager.application.slash_commands.models import SlashCommand
from harness_asset_manager.paths import APP_NAME
from tests.support.fake_home import (
    FakeHomeSpec,
    seed_skill_package,
    write_cli_stub,
)


class AdoptPlannerDecisionTableTests(unittest.TestCase):
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

    def test_empty_store_yields_empty_plan(self) -> None:
        planner = AdoptionPlanner.from_container(self.container)
        plan = planner.plan()
        self.assertEqual(plan.actions, ())
        self.assertEqual(plan.linkable, ())

    def test_corrupt_manifests_and_ledgers_degrade_to_empty_plan(self) -> None:
        # Corrupt skill manifest
        manifest_path = self.container.skills_store.manifest_path
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text("{corrupt json", encoding="utf-8")

        # Corrupt agents ledger
        ledger_path = self.container.paths.bindings_ledger_path
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.write_text("invalid json content", encoding="utf-8")

        # Corrupt slash commands sync-state
        sync_path = self.container.paths.slash_command_sync_state_path
        sync_path.parent.mkdir(parents=True, exist_ok=True)
        sync_path.write_text("[not a dict", encoding="utf-8")

        # Corrupt MCP manifest
        mcp_manifest = self.container.paths.mcp_store_manifest
        mcp_manifest.parent.mkdir(parents=True, exist_ok=True)
        mcp_manifest.write_text("{corrupt mcp json", encoding="utf-8")

        # Corrupt hooks manifest
        hooks_manifest = self.container.paths.hooks_store_manifest
        hooks_manifest.parent.mkdir(parents=True, exist_ok=True)
        hooks_manifest.write_text("{corrupt hooks json", encoding="utf-8")

        # Corrupt permissions manifest
        perms_manifest = self.container.paths.permissions_store_manifest
        perms_manifest.parent.mkdir(parents=True, exist_ok=True)
        perms_manifest.write_text("{corrupt permissions json", encoding="utf-8")

        planner = AdoptionPlanner.from_container(self.container)
        plan = planner.plan()
        self.assertEqual(plan.actions, ())

    def test_decision_table_skills(self) -> None:
        # Seed skill in store and record intent for claude
        skill_src = seed_skill_package(self.spec.home / "downloads", "my-skill", "My Skill")
        dest = self.container.skills_store.ingest(
            source_path=skill_src,
            declared_name="My Skill",
            source_kind="github",
            source_locator="github:org/my-skill",
            source_ref="main",
        )
        # Enable on machine A (records enabled_harnesses=["claude", "cursor"])
        self.container.skills_mutations.enable_managed_package(dest, "claude")
        self.container.skills_mutations.enable_managed_package(dest, "cursor")

        planner = AdoptionPlanner.from_container(self.container)

        # 1. Target already the correct binding -> skip, reason: already-linked
        plan = planner.plan()
        claude_action = next(a for a in plan.actions if a.family == "skills" and a.harness == "claude")
        self.assertEqual(claude_action.action, "skip")
        self.assertEqual(claude_action.reason, "already-linked")

        # Remove the symlink for cursor so it becomes "link"
        cursor_link = self.spec.cursor_root / "my-skill"
        if cursor_link.is_symlink():
            cursor_link.unlink()

        # 2. Link action when target doesn't exist
        plan = planner.plan()
        cursor_action = next(a for a in plan.actions if a.family == "skills" and a.harness == "cursor")
        self.assertEqual(cursor_action.action, "link")
        self.assertIsNone(cursor_action.reason)

        # 3. Target exists, foreign content -> conflict, reason: target-occupied
        cursor_link.mkdir(parents=True, exist_ok=True)
        (cursor_link / "foreign.txt").write_text("hello", encoding="utf-8")
        plan = planner.plan()
        cursor_action = next(a for a in plan.actions if a.family == "skills" and a.harness == "cursor")
        self.assertEqual(cursor_action.action, "conflict")
        self.assertEqual(cursor_action.reason, "target-occupied")
        self.assertIn("collision", cursor_action.detail or "")
        import shutil
        shutil.rmtree(cursor_link)

        # 4. Harness support disabled in settings -> skip, reason: harness-support-disabled
        self.container.harness_kernel.support_store.set_enabled("cursor", False)
        plan = planner.plan()
        cursor_action = next(a for a in plan.actions if a.family == "skills" and a.harness == "cursor")
        self.assertEqual(cursor_action.action, "skip")
        self.assertEqual(cursor_action.reason, "harness-support-disabled")
        self.container.harness_kernel.support_store.set_enabled("cursor", True)

        # 5. Harness not installed -> skip, reason: harness-not-installed
        # Remove cursor-agent binary
        cursor_bin = self.spec.bin_dir / "cursor-agent"
        if cursor_bin.exists():
            cursor_bin.unlink()
        # Also remove cursor config root so it's not detected as installed
        if self.spec.cursor_root.exists():
            import shutil
            shutil.rmtree(self.spec.cursor_root)
        plan = planner.plan()
        cursor_action = next(a for a in plan.actions if a.family == "skills" and a.harness == "cursor")
        self.assertEqual(cursor_action.action, "skip")
        self.assertEqual(cursor_action.reason, "harness-not-installed")

        # 6. Store no longer holds the asset -> skip, reason: asset-missing-from-store
        # Restore cursor-agent executable
        write_cli_stub(self.spec.bin_dir / "cursor-agent", "cursor-agent")
        self.spec.cursor_root.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(dest)
        plan = planner.plan()
        cursor_action = next(a for a in plan.actions if a.family == "skills" and a.harness == "cursor")
        self.assertEqual(cursor_action.action, "skip")
        self.assertEqual(cursor_action.reason, "asset-missing-from-store")

    def test_decision_table_agents(self) -> None:
        self.container.agents_store.create(name="Reviewer", description="reviews", prompt="review code")
        self.container.agents_mutations.enable("reviewer", "claude")
        self.container.agents_mutations.enable("reviewer", "codex")

        planner = AdoptionPlanner.from_container(self.container)

        # 1. Target already correct binding (claude symlink, codex rendered) -> skip, reason: already-linked
        plan = planner.plan()
        claude_action = next(a for a in plan.actions if a.family == "agents" and a.harness == "claude")
        self.assertEqual(claude_action.action, "skip")
        self.assertEqual(claude_action.reason, "already-linked")

        codex_action = next(a for a in plan.actions if a.family == "agents" and a.harness == "codex")
        self.assertEqual(codex_action.action, "skip")
        self.assertEqual(codex_action.reason, "already-linked")

        # Unlink claude so it becomes linkable
        claude_link = self.spec.home / ".claude" / "agents" / "reviewer.md"
        claude_link.unlink()

        # 2. Linkable
        plan = planner.plan()
        claude_action = next(a for a in plan.actions if a.family == "agents" and a.harness == "claude")
        self.assertEqual(claude_action.action, "link")
        self.assertIsNone(claude_action.reason)

        # 3. Target exists, foreign content -> conflict, reason: target-occupied
        claude_link.write_text("foreign agent", encoding="utf-8")
        plan = planner.plan()
        claude_action = next(a for a in plan.actions if a.family == "agents" and a.harness == "claude")
        self.assertEqual(claude_action.action, "conflict")
        self.assertEqual(claude_action.reason, "target-occupied")
        self.assertIn("clobber", claude_action.detail or "")
        claude_link.unlink()

        # 4. Harness support disabled in settings -> skip, reason: harness-support-disabled
        self.container.harness_kernel.support_store.set_enabled("claude", False)
        plan = planner.plan()
        claude_action = next(a for a in plan.actions if a.family == "agents" and a.harness == "claude")
        self.assertEqual(claude_action.action, "skip")
        self.assertEqual(claude_action.reason, "harness-support-disabled")
        self.container.harness_kernel.support_store.set_enabled("claude", True)

        # 5. Harness not installed -> skip, reason: harness-not-installed
        claude_bin = self.spec.bin_dir / "claude"
        claude_bin.unlink()
        import shutil
        shutil.rmtree(self.spec.claude_root)
        shutil.rmtree(self.spec.home / ".claude")
        plan = planner.plan()
        claude_action = next(a for a in plan.actions if a.family == "agents" and a.harness == "claude")
        self.assertEqual(claude_action.action, "skip")
        self.assertEqual(claude_action.reason, "harness-not-installed")

        # 6. Store no longer holds the asset -> skip, reason: asset-missing-from-store
        write_cli_stub(self.spec.bin_dir / "claude", "claude")
        (self.spec.home / ".claude" / "agents").mkdir(parents=True, exist_ok=True)
        (self.spec.agents_root / "reviewer.md").unlink()
        plan = planner.plan()
        claude_action = next(a for a in plan.actions if a.family == "agents" and a.harness == "claude")
        self.assertEqual(claude_action.action, "skip")
        self.assertEqual(claude_action.reason, "asset-missing-from-store")

    def test_decision_table_slash_commands(self) -> None:
        self.container.slash_command_store.create_command(
            SlashCommand(name="lint", description="lint code", prompt="lint prompt")
        )
        self.container.slash_command_mutations.sync_command("lint", targets=["codex"])

        planner = AdoptionPlanner.from_container(self.container)

        # 1. Target already correct binding -> skip, reason: already-linked
        plan = planner.plan()
        codex_action = next(a for a in plan.actions if a.family == "slash_commands" and a.harness == "codex")
        self.assertEqual(codex_action.action, "skip")
        self.assertEqual(codex_action.reason, "already-linked")

        # Delete file so it becomes linkable
        codex_file = self.spec.home / ".codex" / "prompts" / "lint.md"
        codex_file.unlink()

        # 2. Linkable
        plan = planner.plan()
        codex_action = next(a for a in plan.actions if a.family == "slash_commands" and a.harness == "codex")
        self.assertEqual(codex_action.action, "link")
        self.assertIsNone(codex_action.reason)

        # 3. Target exists, foreign content -> conflict, reason: target-occupied
        codex_file.write_text("foreign command", encoding="utf-8")
        plan = planner.plan()
        codex_action = next(a for a in plan.actions if a.family == "slash_commands" and a.harness == "codex")
        self.assertEqual(codex_action.action, "conflict")
        self.assertEqual(codex_action.reason, "target-occupied")
        self.assertIn("clobber", codex_action.detail or "")
        codex_file.unlink()

        # 4. Harness support disabled in settings -> skip, reason: harness-support-disabled
        self.container.harness_kernel.support_store.set_enabled("codex", False)
        plan = planner.plan()
        codex_action = next(a for a in plan.actions if a.family == "slash_commands" and a.harness == "codex")
        self.assertEqual(codex_action.action, "skip")
        self.assertEqual(codex_action.reason, "harness-support-disabled")
        self.container.harness_kernel.support_store.set_enabled("codex", True)

        # 5. Store missing asset -> skip, reason: asset-missing-from-store
        self.container.slash_command_store.command_path("lint").unlink()
        plan = planner.plan()
        codex_action = next(a for a in plan.actions if a.family == "slash_commands" and a.harness == "codex")
        self.assertEqual(codex_action.action, "skip")
        self.assertEqual(codex_action.reason, "asset-missing-from-store")

    def test_legacy_foreign_absolute_path_degrades_to_skip(self) -> None:
        # Seed an agent in store
        (self.spec.agents_root / "legacy-agent.md").write_text(
            "---\nname: Legacy\ndescription: test\n---\nPrompt", encoding="utf-8"
        )
        # Write ledger with non-portable path from foreign machine
        foreign_ledger = {
            "version": 1,
            "agents": {
                "legacy-agent": {
                    "claude": {
                        "target": "/Users/foreign_user/.local/share/harnessam/agents/legacy-agent.md",
                        "linkedAt": 100.0,
                    }
                }
            },
        }
        self.container.paths.bindings_ledger_path.write_text(
            json.dumps(foreign_ledger, indent=2), encoding="utf-8"
        )

        planner = AdoptionPlanner.from_container(self.container)
        plan = planner.plan()
        legacy_action = next((a for a in plan.actions if a.ref == "legacy-agent"), None)
        self.assertIsNotNone(legacy_action)
        self.assertEqual(legacy_action.action, "skip")
        self.assertEqual(legacy_action.reason, "asset-missing-from-store")

    def test_decision_table_mcp(self) -> None:
        spec = McpServerSpec(
            name="exa",
            display_name="Exa",
            source=McpSource.manual("exa"),
            transport="stdio",
            command="npx",
            args=("-y", "exa-mcp-server"),
            enabled_harnesses=("claude", "cursor"),
        )
        self.container.mcp_store.upsert_managed(spec)
        self.container.mcp_mutations.enable_server("exa", "claude")

        planner = AdoptionPlanner.from_container(self.container)

        # 1. Claude already configured -> skip, reason: already-linked
        plan = planner.plan()
        claude_action = next(a for a in plan.actions if a.family == "mcp" and a.harness == "claude")
        self.assertEqual(claude_action.action, "skip")
        self.assertEqual(claude_action.reason, "already-linked")

        # 2. Cursor vacant -> link
        cursor_action = next(a for a in plan.actions if a.family == "mcp" and a.harness == "cursor")
        self.assertEqual(cursor_action.action, "link")

        # 3. Cursor occupied key with different config -> conflict, reason: target-occupied
        cursor_adapter = self.container.mcp_read_models.require_enabled_adapter("cursor")
        foreign_spec = McpServerSpec(
            name="exa",
            display_name="Exa",
            source=McpSource.manual("exa"),
            transport="stdio",
            command="different-cmd",
        )
        cursor_adapter.enable_server(foreign_spec)
        plan = planner.plan()
        cursor_action = next(a for a in plan.actions if a.family == "mcp" and a.harness == "cursor")
        self.assertEqual(cursor_action.action, "conflict")
        self.assertEqual(cursor_action.reason, "target-occupied")

        # Remove key from cursor config
        cursor_adapter.disable_server("exa")

        # 4. Harness support disabled in settings -> skip, reason: harness-support-disabled
        self.container.harness_kernel.support_store.set_enabled("cursor", False)
        plan = planner.plan()
        cursor_action = next(a for a in plan.actions if a.family == "mcp" and a.harness == "cursor")
        self.assertEqual(cursor_action.action, "skip")
        self.assertEqual(cursor_action.reason, "harness-support-disabled")
        self.container.harness_kernel.support_store.set_enabled("cursor", True)

        # 5. Harness not installed -> skip, reason: harness-not-installed
        cursor_bin = self.spec.bin_dir / "cursor-agent"
        if cursor_bin.exists():
            cursor_bin.unlink()
        plan = planner.plan()
        cursor_action = next(a for a in plan.actions if a.family == "mcp" and a.harness == "cursor")
        self.assertEqual(cursor_action.action, "skip")
        self.assertEqual(cursor_action.reason, "harness-not-installed")
        write_cli_stub(cursor_bin, "cursor-agent")

        # 6. Asset missing from store
        self.container.mcp_store.remove("exa")
        plan = planner.plan()
        mcp_actions = [a for a in plan.actions if a.family == "mcp"]
        self.assertEqual(mcp_actions, [])

    def test_decision_table_hooks(self) -> None:
        spec = HookSpec(
            id="lint-hook",
            event="pre_tool_use",
            command="flake8",
            match="file_write",
            enabled_harnesses=("claude",),
        )
        self.container.hooks_store.upsert_managed(spec)
        self.container.hooks_mutations.enable_hook("lint-hook", "claude")

        planner = AdoptionPlanner.from_container(self.container)

        # 1. Claude already configured -> skip, reason: already-linked
        plan = planner.plan()
        claude_action = next(a for a in plan.actions if a.family == "hooks" and a.harness == "claude")
        self.assertEqual(claude_action.action, "skip")
        self.assertEqual(claude_action.reason, "already-linked")

        # Disable on claude -> key becomes vacant -> link
        claude_adapter = self.container.hooks_read_models.require_enabled_adapter("claude")
        claude_adapter.disable_hook("lint-hook")
        plan = planner.plan()
        claude_action = next(a for a in plan.actions if a.family == "hooks" and a.harness == "claude")
        self.assertEqual(claude_action.action, "link")

        # Occupied key with different command -> conflict, reason: target-occupied
        diff_spec = HookSpec(
            id="lint-hook",
            event="pre_tool_use",
            command="pylint",
            match="file_write",
        )
        claude_adapter.enable_hook(diff_spec)
        plan = planner.plan()
        claude_action = next(a for a in plan.actions if a.family == "hooks" and a.harness == "claude")
        self.assertEqual(claude_action.action, "conflict")
        self.assertEqual(claude_action.reason, "target-occupied")

        # Harness disabled in settings -> skip, reason: harness-support-disabled
        self.container.harness_kernel.support_store.set_enabled("claude", False)
        plan = planner.plan()
        claude_action = next(a for a in plan.actions if a.family == "hooks" and a.harness == "claude")
        self.assertEqual(claude_action.action, "skip")
        self.assertEqual(claude_action.reason, "harness-support-disabled")
        self.container.harness_kernel.support_store.set_enabled("claude", True)

    def test_decision_table_permissions(self) -> None:
        spec = PermissionSpec(
            id="block-secrets",
            decision="deny",
            scope="file_write",
            pattern="/secrets/**",
            enabled_harnesses=("claude",),
        )
        self.container.permissions_store.upsert_managed(spec)
        self.container.permissions_mutations.enable_permission("block-secrets", "claude")

        planner = AdoptionPlanner.from_container(self.container)

        # 1. Claude already configured -> skip, reason: already-linked
        plan = planner.plan()
        claude_action = next(a for a in plan.actions if a.family == "permissions" and a.harness == "claude")
        self.assertEqual(claude_action.action, "skip")
        self.assertEqual(claude_action.reason, "already-linked")

        # Disable on claude -> key becomes vacant -> link
        claude_adapter = self.container.permissions_read_models.require_enabled_adapter("claude")
        claude_adapter.disable_permission("block-secrets")
        plan = planner.plan()
        claude_action = next(a for a in plan.actions if a.family == "permissions" and a.harness == "claude")
        self.assertEqual(claude_action.action, "link")

        # Partial rules (only Edit, missing Write) -> drifted state -> conflict, reason: target-occupied
        claude_adapter.config_path.write_text(
            json.dumps({"permissions": {"deny": ["Edit(/secrets/**)"]}}, indent=2),
            encoding="utf-8",
        )
        plan = planner.plan()
        claude_action = next(a for a in plan.actions if a.family == "permissions" and a.harness == "claude")
        self.assertEqual(claude_action.action, "conflict")
        self.assertEqual(claude_action.reason, "target-occupied")


if __name__ == "__main__":
    unittest.main()
