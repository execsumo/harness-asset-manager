from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness_asset_manager.application.container import build_backend_container
from harness_asset_manager.application.mcp.store import McpServerSpec, McpSource
from harness_asset_manager.application.slash_commands.models import SlashCommand
from harness_asset_manager.paths import APP_NAME
from tests.support.fake_home import (
    FakeHomeSpec,
    seed_skill_package,
    write_cli_stub,
)


class CrossDeviceArrivalTests(unittest.TestCase):
    def test_cross_device_store_migration_and_arrival(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            root_a = tmp_path / "machine-a"
            root_b = tmp_path / "machine-b"
            spec_a = FakeHomeSpec(
                root=root_a,
                home=root_a / "Users" / "alice",
                xdg_config_home=root_a / "Users" / "alice" / ".config",
                xdg_data_home=root_a / "Users" / "alice" / ".local" / "share",
                xdg_state_home=root_a / "Users" / "alice" / ".local" / "state",
            )
            spec_b = FakeHomeSpec(
                root=root_b,
                home=root_b / "home" / "bob",
                xdg_config_home=root_b / "home" / "bob" / ".config",
                xdg_data_home=root_b / "home" / "bob" / ".local" / "share",
                xdg_state_home=root_b / "home" / "bob" / ".local" / "state",
            )
            for spec in (spec_a, spec_b):
                for p in (
                    spec.skills_store_root,
                    spec.agents_root,
                    spec.codex_root,
                    spec.codex_legacy_root,
                    spec.claude_root,
                    spec.cursor_root,
                    spec.opencode_root,
                    spec.agy_root,
                    spec.hermes_skills_root,
                    spec.xdg_state_home,
                    spec.bin_dir,
                    spec.home / ".claude" / "agents",
                    spec.home / ".codex" / "agents",
                    spec.home / ".codex" / "prompts",
                ):
                    p.mkdir(parents=True, exist_ok=True)
                for executable in ("codex", "claude", "cursor-agent", "opencode", "agy", "hermes"):
                    write_cli_stub(spec.bin_dir / executable, executable)

            # === 1. Setup Machine A with assets across all domains ===
            container_a = build_backend_container(spec_a.env())

            # Skills
            skill_src = seed_skill_package(spec_a.home / "downloads", "shared-audit", "Shared Audit", body="Audit pkg")
            skill_dest = container_a.skills_store.ingest(
                source_path=skill_src,
                declared_name="Shared Audit",
                source_kind="github",
                source_locator="github:org/shared-audit",
                source_ref="main",
            )
            container_a.skills_mutations.enable_managed_package(skill_dest, "claude")
            container_a.skills_mutations.set_skill_tags("shared:shared-audit", ["starred", "devops", "core"])

            # Agents
            container_a.agents_store.create(name="Auditor", description="audits", prompt="audit prompt")
            container_a.agents_mutations.enable("auditor", "claude")
            container_a.agents_mutations.enable("auditor", "codex")

            # Slash Commands
            container_a.slash_command_store.create_command(
                SlashCommand(name="code-review", description="review code", prompt="$ARGUMENTS")
            )
            container_a.slash_command_mutations.sync_command("code-review", targets=["codex"])

            # MCP
            container_a.mcp_store.upsert_from_spec(
                McpServerSpec(
                    name="exa",
                    display_name="Exa",
                    source=McpSource.manual("exa"),
                    transport="stdio",
                    command="npx",
                    args=("-y", "exa-mcp-server"),
                )
            )

            # Verify Machine A state
            self.assertTrue((spec_a.claude_root / "shared-audit").is_symlink())
            self.assertTrue((spec_a.home / ".claude" / "agents" / "auditor.md").is_symlink())
            self.assertTrue((spec_a.home / ".codex" / "agents" / "auditor.toml").is_file())
            self.assertTrue((spec_a.home / ".codex" / "prompts" / "code-review.md").is_file())

            # === 2. Copy store from Machine A to Machine B ===
            store_a = spec_a.xdg_data_home / APP_NAME
            store_b = spec_b.xdg_data_home / APP_NAME
            if store_b.exists():
                shutil.rmtree(store_b)
            shutil.copytree(store_a, store_b)

            # === 3. Start HAM backend on Machine B ===
            container_b = build_backend_container(spec_b.env())

            # Assert 1: Store assets are visible and manageable on Machine B
            agents_b = container_b.agents_inventory.build()
            self.assertEqual([e.ref for e in agents_b.entries], ["auditor"])

            skills_b = container_b.skills_queries.inventory()
            self.assertIn("shared-audit", [e.package_dir for e in skills_b.entries if e.package_dir])

            # Assert 1b: Asset tags survive arrival on Machine B
            skills_page_b = container_b.skills_queries.list_skills()
            audit_row = next(r for r in skills_page_b["rows"] if r["skillRef"] == "shared:shared-audit")
            self.assertEqual(audit_row["tags"], ["starred", "core", "devops"])
            detail_b = container_b.skills_queries.get_skill_detail("shared:shared-audit")
            self.assertIsNotNone(detail_b)
            self.assertEqual(detail_b["tags"], ["starred", "core", "devops"])

            commands_b = container_b.slash_command_queries.list_commands()
            self.assertEqual([c["name"] for c in commands_b["commands"]], ["code-review"])

            mcp_b = container_b.mcp_store.list_managed()
            self.assertEqual([s.name for s in mcp_b], ["exa"])

            # Assert 2: Bindings on Machine B show up as disabled (links don't exist on B yet), not broken/error
            auditor_entry = next(e for e in agents_b.entries if e.ref == "auditor")
            for binding in auditor_entry.bindings:
                self.assertEqual(
                    binding.state,
                    "disabled",
                    f"Agent binding for {binding.harness} should be disabled on fresh machine, got {binding.state}",
                )

            # Assert 3: Adopt plan on Machine B identifies all 4 bindings from Machine A
            plan_b = container_b.adoption_planner.plan()
            self.assertEqual(
                len(plan_b.linkable),
                4,
                f"Expected 4 linkable actions on arrival, got {len(plan_b.linkable)}: {plan_b.linkable}",
            )
            # 1 skill (claude), 2 agents (claude, codex), 1 slash command (codex)
            self.assertEqual(
                {(a.family, a.ref, a.harness) for a in plan_b.linkable},
                {
                    ("skills", "shared:shared-audit", "claude"),
                    ("agents", "auditor", "claude"),
                    ("agents", "auditor", "codex"),
                    ("slash_commands", "code-review", "codex"),
                },
            )

            # Assert 4: Apply adoption on Machine B creates all valid bindings rooted under Bob's home
            results_b = container_b.adoption_applier.apply(plan_b.linkable)
            self.assertEqual(len(results_b), 4)
            self.assertTrue(all(r.status == "applied" for r in results_b))

            b_claude_link = spec_b.home / ".claude" / "agents" / "auditor.md"
            self.assertTrue(b_claude_link.is_symlink())
            self.assertEqual(
                b_claude_link.resolve(),
                (spec_b.agents_root / "auditor.md").resolve(),
            )

            b_codex_file = spec_b.home / ".codex" / "agents" / "auditor.toml"
            self.assertTrue(b_codex_file.is_file())

            b_skill_link = spec_b.claude_root / "shared-audit"
            self.assertTrue(b_skill_link.is_symlink())
            self.assertEqual(
                b_skill_link.resolve(),
                (spec_b.skills_store_root / "shared-audit").resolve(),
            )

            b_cmd_file = spec_b.home / ".codex" / "prompts" / "code-review.md"
            self.assertTrue(b_cmd_file.is_file())

            # Assert 5: Idempotence — re-running planner on Machine B yields 0 linkable actions
            plan_b_second = container_b.adoption_planner.plan()
            self.assertEqual(len(plan_b_second.linkable), 0)
            self.assertEqual(len(plan_b_second.skipped), 4)
            self.assertTrue(all(a.reason == "already-linked" for a in plan_b_second.skipped))

            # Re-applying yields status=applied as a no-op
            reapply_results = container_b.adoption_applier.apply(plan_b.actions)
            self.assertTrue(all(r.status == "applied" for r in reapply_results))

            # Assert 6: Reconcile / auto-adopt runs cleanly without crashing or corrupting store
            container_b.agents_reconcile.reconcile()
            container_b.skills_queries.inventory()
            container_b.slash_command_queries.list_commands()

            # Assert 5: No paths from Machine A leak into Machine B's persisted state files
            ledger_text = container_b.paths.bindings_ledger_path.read_text(encoding="utf-8")
            self.assertNotIn(str(root_a), ledger_text)
            self.assertIn("~/", ledger_text)

            sync_state_text = container_b.paths.slash_command_sync_state_path.read_text(encoding="utf-8")
            self.assertNotIn(str(root_a), sync_state_text)

    def test_cross_device_legacy_absolute_paths_degrade_safely(self) -> None:
        """When a legacy store with machine A's absolute paths is copied to machine B,
        machine B safely treats those records as unusable/no-record without crashing.
        """
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            root_b = tmp_path / "machine-b"
            spec_b = FakeHomeSpec(
                root=root_b,
                home=root_b / "home" / "bob",
                xdg_config_home=root_b / "home" / "bob" / ".config",
                xdg_data_home=root_b / "home" / "bob" / ".local" / "share",
                xdg_state_home=root_b / "home" / "bob" / ".local" / "state",
            )
            for p in (
                spec_b.skills_store_root,
                spec_b.agents_root,
                spec_b.codex_root,
                spec_b.claude_root,
                spec_b.xdg_state_home,
                spec_b.bin_dir,
                spec_b.home / ".claude" / "agents",
            ):
                p.mkdir(parents=True, exist_ok=True)
            for executable in ("codex", "claude", "cursor-agent", "opencode", "agy", "hermes"):
                write_cli_stub(spec_b.bin_dir / executable, executable)

            store_b = spec_b.xdg_data_home / APP_NAME
            store_b.mkdir(parents=True, exist_ok=True)

            # Create agent in store
            (spec_b.agents_root / "reviewer.md").write_text(
                "---\nname: Reviewer\ndescription: reviews\n---\nPrompt", encoding="utf-8"
            )

            # Write legacy bindings.json with foreign machine A absolute paths
            foreign_ledger = {
                "version": 1,
                "agents": {
                    "reviewer": {
                        "claude": {
                            "target": "/Users/alice/.local/share/harnessam/agents/reviewer.md",
                            "linkedAt": 12345.0,
                            "storeSha256": "sha256:abc",
                        }
                    }
                },
            }
            (store_b / "bindings.json").write_text(json.dumps(foreign_ledger, indent=2), encoding="utf-8")

            # Write legacy slash commands sync-state with foreign machine A absolute paths
            slash_dir = store_b / "slash-commands"
            slash_dir.mkdir(parents=True, exist_ok=True)
            foreign_sync = {
                "version": 2,
                "commands": {
                    "test-cmd": {
                        "claude": {
                            "target": "claude",
                            "path": "/Users/alice/.claude/commands/test-cmd.md",
                            "contentHash": "sha256:def",
                            "renderFormat": "frontmatter_markdown",
                        }
                    }
                },
            }
            (slash_dir / "sync-state.json").write_text(json.dumps(foreign_sync, indent=2), encoding="utf-8")

            # Start container on machine B
            container_b = build_backend_container(spec_b.env())

            # Verify that machine B loaded without crashing and treated foreign records as disabled / no-record
            agents_b = container_b.agents_inventory.build()
            self.assertEqual([e.ref for e in agents_b.entries], ["reviewer"])
            reviewer_entry = agents_b.entries[0]
            for binding in reviewer_entry.bindings:
                self.assertEqual(binding.state, "disabled")

            # Re-enabling creates local binding with portable path
            container_b.agents_mutations.enable("reviewer", "claude")
            self.assertTrue((spec_b.home / ".claude" / "agents" / "reviewer.md").is_symlink())

            updated_ledger = json.loads(container_b.paths.bindings_ledger_path.read_text(encoding="utf-8"))
            self.assertEqual(
                updated_ledger["agents"]["reviewer"]["claude"]["target"],
                "~/.local/share/harnessam/agents/reviewer.md",
            )

    def test_cross_device_adoption_pressure_invariants(self) -> None:
        """Pressure-test adoption invariants:
        - Additive-only: local bindings on machine B survive adoption of A's assets untouched
        - Occupied target refusal: foreign occupied files are not clobbered without explicit permission
        - Harness absent: intent for uninstalled harnesses degrades to skip, never error
        - Corrupt ledgers: unparseable files degrade to empty plan, never 500 or crash
        """
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            root_a = tmp_path / "machine-a"
            root_b = tmp_path / "machine-b"
            spec_a = FakeHomeSpec(
                root=root_a,
                home=root_a / "Users" / "alice",
                xdg_config_home=root_a / "Users" / "alice" / ".config",
                xdg_data_home=root_a / "Users" / "alice" / ".local" / "share",
                xdg_state_home=root_a / "Users" / "alice" / ".local" / "state",
            )
            spec_b = FakeHomeSpec(
                root=root_b,
                home=root_b / "home" / "bob",
                xdg_config_home=root_b / "home" / "bob" / ".config",
                xdg_data_home=root_b / "home" / "bob" / ".local" / "share",
                xdg_state_home=root_b / "home" / "bob" / ".local" / "state",
            )
            for spec in (spec_a, spec_b):
                for p in (
                    spec.skills_store_root,
                    spec.agents_root,
                    spec.claude_root,
                    spec.codex_root,
                    spec.xdg_state_home,
                    spec.bin_dir,
                    spec.home / ".claude" / "agents",
                    spec.home / ".codex" / "agents",
                    spec.home / ".codex" / "prompts",
                ):
                    p.mkdir(parents=True, exist_ok=True)
            # Machine A has claude and codex
            for executable in ("codex", "claude"):
                write_cli_stub(spec_a.bin_dir / executable, executable)
            # Machine B has ONLY claude (codex is NOT installed on B)
            write_cli_stub(spec_b.bin_dir / "claude", "claude")
            if (spec_b.home / ".codex").exists():
                shutil.rmtree(spec_b.home / ".codex")
            if spec_b.codex_root.exists():
                shutil.rmtree(spec_b.codex_root)

            # Machine A creates auditor and syncs to claude AND codex
            container_a = build_backend_container(spec_a.env())
            container_a.agents_store.create(name="Auditor", description="audits", prompt="audit prompt")
            container_a.agents_mutations.enable("auditor", "claude")
            container_a.agents_mutations.enable("auditor", "codex")

            # Copy store from A to B
            store_a = spec_a.xdg_data_home / APP_NAME
            store_b = spec_b.xdg_data_home / APP_NAME
            if store_b.exists():
                shutil.rmtree(store_b)
            shutil.copytree(store_a, store_b)

            container_b = build_backend_container(spec_b.env())

            # 1. Additive-only: B creates a local agent BEFORE adopting A's assets
            container_b.agents_store.create(name="LocalAgent", description="local", prompt="local prompt")
            container_b.agents_mutations.enable("localagent", "claude")
            local_agent_link = spec_b.home / ".claude" / "agents" / "localagent.md"
            self.assertTrue(local_agent_link.is_symlink())

            # 2. Occupied target refusal: put a foreign file where auditor would be linked on B
            auditor_claude_target = spec_b.home / ".claude" / "agents" / "auditor.md"
            auditor_claude_target.write_text("pre-existing foreign file", encoding="utf-8")

            # 3. Plan on B
            plan = container_b.adoption_planner.plan()

            # Verify:
            # - auditor on codex -> skip (harness-not-installed on B)
            # - auditor on claude -> conflict (target-occupied on B)
            codex_action = next(a for a in plan.actions if a.ref == "auditor" and a.harness == "codex")
            self.assertEqual(codex_action.action, "skip")
            self.assertEqual(codex_action.reason, "harness-not-installed")

            claude_action = next(a for a in plan.actions if a.ref == "auditor" and a.harness == "claude")
            self.assertEqual(claude_action.action, "conflict")
            self.assertEqual(claude_action.reason, "target-occupied")

            # Apply only linkable (none) -> foreign file unchanged
            container_b.adoption_applier.apply(plan.linkable)
            self.assertEqual(auditor_claude_target.read_text(encoding="utf-8"), "pre-existing foreign file")

            # Try applying conflict action without allow_conflicts -> refuses
            refused = container_b.adoption_applier.apply([claude_action], allow_conflicts=False)
            self.assertEqual(refused[0].status, "failed")
            self.assertIn("overwrite", refused[0].error or "")
            self.assertEqual(auditor_claude_target.read_text(encoding="utf-8"), "pre-existing foreign file")

            # Verify local agent was untouched throughout all of this
            self.assertTrue(local_agent_link.is_symlink())

            # 4. Corrupt ledger degradation
            container_b.paths.bindings_ledger_path.write_text("{corrupt-json", encoding="utf-8")
            degraded_plan = container_b.adoption_planner.plan()
            # Degrades safely without raising; returns whatever else is valid or empty
            self.assertTrue(isinstance(degraded_plan.actions, tuple))


if __name__ == "__main__":
    unittest.main()

