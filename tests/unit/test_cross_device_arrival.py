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
    create_fake_home_spec,
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

            # Assert 3: Re-enabling on Machine B creates valid symlinks/renders under Machine B paths
            container_b.agents_mutations.enable("auditor", "claude")
            b_claude_link = spec_b.home / ".claude" / "agents" / "auditor.md"
            self.assertTrue(b_claude_link.is_symlink())
            self.assertEqual(
                b_claude_link.resolve(),
                (spec_b.agents_root / "auditor.md").resolve(),
            )

            container_b.agents_mutations.enable("auditor", "codex")
            b_codex_file = spec_b.home / ".codex" / "agents" / "auditor.toml"
            self.assertTrue(b_codex_file.is_file())

            container_b.skills_mutations.enable_managed_package(spec_b.skills_store_root / "shared-audit", "claude")
            b_skill_link = spec_b.claude_root / "shared-audit"
            self.assertTrue(b_skill_link.is_symlink())
            self.assertEqual(
                b_skill_link.resolve(),
                (spec_b.skills_store_root / "shared-audit").resolve(),
            )

            container_b.slash_command_mutations.sync_command("code-review", targets=["codex"])
            b_cmd_file = spec_b.home / ".codex" / "prompts" / "code-review.md"
            self.assertTrue(b_cmd_file.is_file())

            # Assert 4: Reconcile / auto-adopt runs cleanly without crashing or corrupting store
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


if __name__ == "__main__":
    unittest.main()
