"""Cross-family pressure test for tags and stars.

Exercises tag/star operations across all included families (Agents, Slash
Commands, MCP, Hooks, Permissions) — but NOT Config — and asserts consistent
behavior, persistence, isolation, and representative filter/payload semantics.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from harness_asset_manager.application.asset_tags import (
    AssetTagService,
    AssetTagStore,
)
from harness_asset_manager.application.skills.manifest import SkillStoreEntry
from harness_asset_manager.application.skills.package import fingerprint_package
from tests.integration.test_mcp_routes import _seed_manual_remote
from tests.support.app_harness import AppTestHarness
from tests.support.fake_home import seed_skill_package, seed_store_manifest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_agent(harness: AppTestHarness) -> str:
    resp = harness.post_json(
        "/api/agents",
        {
            "name": "PressureAgent",
            "description": "Agent for tag pressure test.",
            "prompt": "You are a test agent.",
        },
    )
    return resp["ref"]


def _create_hook(harness: AppTestHarness) -> str:
    harness.post_json(
        "/api/hooks",
        {
            "id": "pressure-hook",
            "event": "pre_tool_use",
            "command": "echo pressure",
            "description": "Hook for tag pressure test.",
        },
    )
    return "pressure-hook"


def _create_mcp(harness: AppTestHarness) -> str:
    _seed_manual_remote(harness, "pressure-mcp")
    return "pressure-mcp"


def _create_permission(harness: AppTestHarness) -> str:
    harness.post_json(
        "/api/permissions",
        {
            "id": "deny-pressure",
            "decision": "deny",
            "scope": "shell",
            "pattern": "rm -rf /*",
            "description": "Permission for tag pressure test.",
        },
    )
    return "deny-pressure"


def _create_slash_command(harness: AppTestHarness) -> str:
    harness.post_json(
        "/api/slash-commands",
        {
            "name": "pressure-cmd",
            "description": "Slash command for tag pressure test.",
            "prompt": "Pressure test.",
        },
    )
    return "pressure-cmd"


def _create_skill(harness: AppTestHarness) -> str:
    package_root = seed_skill_package(
        harness.spec.skills_store_root,
        "pressure-skill",
        "Pressure Skill",
        body="Pressure test skill body.",
    )
    revision, _ = fingerprint_package(package_root)
    seed_store_manifest(
        harness.spec,
        [
            SkillStoreEntry(
                package_dir="pressure-skill",
                declared_name="Pressure Skill",
                source_kind="manual",
                source_locator="manual",
                revision=revision,
            )
        ],
    )
    return "shared:pressure-skill"


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class CrossFamilyTagsPressureTest(unittest.TestCase):
    """Exercises tag/star behaviour across every included family in a single
    harness session so storage isolation is tested end-to-end."""

    def test_tags_and_stars_across_all_families(self) -> None:
        """Full lifecycle: set, read-back, starred, filter payload,
        isolation, clear, across every asset family except Config."""

        with AppTestHarness() as harness:
            # -- Create one asset per family -----------------------------------

            agent_ref = _create_agent(harness)
            hook_id = _create_hook(harness)
            mcp_name = _create_mcp(harness)
            perm_id = _create_permission(harness)
            slash_name = _create_slash_command(harness)
            skill_ref = _create_skill(harness)

            # -- Tag each asset with shared + family-specific tags -------------

            family_refs: dict[str, tuple[str, str]] = {
                # family: (route_path, identifier_key)
                "agents": (f"/api/agents/{agent_ref}/tags", "agents"),
                "hooks": (f"/api/hooks/{hook_id}/tags", "hooks"),
                "mcp": (f"/api/mcp/servers/{mcp_name}/tags", "mcp"),
                "permissions": (f"/api/permissions/{perm_id}/tags", "permissions"),
                "slash_commands": (f"/api/slash-commands/{slash_name}/tags", "slash_commands"),
                "skills": (f"/api/skills/{skill_ref}/tags", "skills"),
            }

            shared_tag = "cross-family-shared"
            starred_tag = "starred"

            for family, (route, _) in family_refs.items():
                family_tag = f"only-{family}"
                put_resp = harness.put_json(
                    route,
                    {"tags": [shared_tag, family_tag, starred_tag]},
                )

                # Verify starred pinned first, normalization applied
                self.assertEqual(
                    put_resp["tags"][0],
                    "starred",
                    f"[{family}] starred should be pinned first",
                )
                self.assertIn(
                    shared_tag,
                    put_resp["tags"],
                    f"[{family}] shared tag should be present",
                )
                self.assertIn(
                    family_tag,
                    put_resp["tags"],
                    f"[{family}] family-specific tag should be present",
                )

            # -- Verify isolation: each family only sees its own tags ----------

            agent_detail = harness.get_json(f"/api/agents/{agent_ref}")
            self.assertIn("only-agents", agent_detail["tags"])
            self.assertNotIn("only-hooks", agent_detail["tags"])
            self.assertNotIn("only-permissions", agent_detail["tags"])
            self.assertNotIn("only-slash_commands", agent_detail["tags"])
            self.assertNotIn("only-skills", agent_detail["tags"])

            hook_detail = harness.get_json(f"/api/hooks/{hook_id}")
            self.assertIn("only-hooks", hook_detail["tags"])
            self.assertNotIn("only-agents", hook_detail["tags"])

            mcp_detail = harness.get_json(f"/api/mcp/servers/{mcp_name}")
            self.assertIn("only-mcp", mcp_detail["tags"])
            self.assertNotIn("only-agents", mcp_detail["tags"])

            perm_detail = harness.get_json(f"/api/permissions/{perm_id}")
            self.assertIn("only-permissions", perm_detail["tags"])
            self.assertNotIn("only-agents", perm_detail["tags"])

            slash_detail = harness.get_json(f"/api/slash-commands/{slash_name}")
            self.assertIn("only-slash_commands", slash_detail["tags"])
            self.assertNotIn("only-agents", slash_detail["tags"])

            skill_detail = harness.get_json(f"/api/skills/{skill_ref}")
            self.assertIn("only-skills", skill_detail["tags"])
            self.assertNotIn("only-agents", skill_detail["tags"])

            # -- Verify tags ride along on list payloads -----------------------

            agents_list = harness.get_json("/api/agents")
            agent_entry = next(e for e in agents_list["entries"] if e["ref"] == agent_ref)
            self.assertEqual(agent_entry["tags"][0], "starred")
            self.assertIn(shared_tag, agent_entry["tags"])

            hooks_list = harness.get_json("/api/hooks")
            hook_entry = next(e for e in hooks_list["entries"] if e["id"] == hook_id)
            self.assertIn(shared_tag, hook_entry["tags"])

            mcp_list = harness.get_json("/api/mcp/servers")
            mcp_entry = next(e for e in mcp_list["entries"] if e["name"] == mcp_name)
            self.assertIn(shared_tag, mcp_entry["tags"])

            perms_list = harness.get_json("/api/permissions")
            perm_entry = next(e for e in perms_list["entries"] if e["id"] == perm_id)
            self.assertIn(shared_tag, perm_entry["tags"])

            slash_list = harness.get_json("/api/slash-commands")
            slash_entry = next(c for c in slash_list["commands"] if c["name"] == slash_name)
            self.assertIn(shared_tag, slash_entry["tags"])

            skills_list = harness.get_json("/api/skills")
            skill_row = next(r for r in skills_list["rows"] if r["skillRef"] == skill_ref)
            self.assertIn(shared_tag, skill_row["tags"])

            # -- Verify starred is a real tag (not a boolean) ------------------

            for family, (route, _) in family_refs.items():
                # Unstar by setting tags without "starred"
                put_resp = harness.put_json(
                    route,
                    {"tags": [shared_tag, f"only-{family}"]},
                )
                self.assertNotIn("starred", put_resp["tags"])

                # Re-star
                put_resp = harness.put_json(
                    route,
                    {"tags": ["starred", shared_tag, f"only-{family}"]},
                )
                self.assertEqual(put_resp["tags"][0], "starred")

            # -- Clear tags and verify isolation persists ----------------------

            # Clear only the agent's tags
            harness.put_json(f"/api/agents/{agent_ref}/tags", {"tags": []})
            cleared_agent = harness.get_json(f"/api/agents/{agent_ref}")
            self.assertEqual(cleared_agent["tags"], [])

            # Other families should still have their tags
            hook_still_tagged = harness.get_json(f"/api/hooks/{hook_id}")
            self.assertIn(shared_tag, hook_still_tagged["tags"])
            self.assertIn("only-hooks", hook_still_tagged["tags"])

            mcp_still_tagged = harness.get_json(f"/api/mcp/servers/{mcp_name}")
            self.assertIn(shared_tag, mcp_still_tagged["tags"])
            self.assertIn("only-mcp", mcp_still_tagged["tags"])

            perm_still_tagged = harness.get_json(f"/api/permissions/{perm_id}")
            self.assertIn(shared_tag, perm_still_tagged["tags"])

            slash_still_tagged = harness.get_json(f"/api/slash-commands/{slash_name}")
            self.assertIn(shared_tag, slash_still_tagged["tags"])

            skill_still_tagged = harness.get_json(f"/api/skills/{skill_ref}")
            self.assertIn(shared_tag, skill_still_tagged["tags"])

    def test_tag_persistence_survives_store_reload(self) -> None:
        """Tags written via the API survive being loaded from the raw file."""

        with AppTestHarness() as harness:
            hook_id = _create_hook(harness)
            perm_id = _create_permission(harness)

            harness.put_json(f"/api/hooks/{hook_id}/tags", {"tags": ["starred", "persistent"]})
            harness.put_json(f"/api/permissions/{perm_id}/tags", {"tags": ["durable"]})

            # Re-read the raw JSON file to verify persistence
            tags_path = harness.container.paths.asset_tags_path
            raw = json.loads(tags_path.read_text(encoding="utf-8"))

            self.assertIn(f"hooks:{hook_id}", raw["tags"])
            self.assertEqual(raw["tags"][f"hooks:{hook_id}"], ["starred", "persistent"])

            self.assertIn(f"permissions:{perm_id}", raw["tags"])
            self.assertEqual(raw["tags"][f"permissions:{perm_id}"], ["durable"])

    def test_service_level_family_isolation(self) -> None:
        """Direct AssetTagService: tags from one family are not visible to
        another family via get_tags_for_family."""

        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as tmp:
            store = AssetTagStore(Path(tmp) / "asset-tags.json")
            service = AssetTagService(store)

            service.set_tags("agents", "reviewer", ["starred", "team-a"])
            service.set_tags("hooks", "pre-compact", ["starred", "security"])
            service.set_tags("mcp", "filesystem", ["local"])
            service.set_tags("permissions", "deny-prod", ["production"])
            service.set_tags("slash_commands", "deploy", ["ops", "starred"])
            service.set_tags("skills", "academic-research", ["core"])

            # Each family sees only its own keys
            agent_tags = service.get_tags_for_family("agents")
            self.assertIn("reviewer", agent_tags)
            self.assertNotIn("pre-compact", agent_tags)
            self.assertNotIn("deny-prod", agent_tags)

            hook_tags = service.get_tags_for_family("hooks")
            self.assertIn("pre-compact", hook_tags)
            self.assertNotIn("reviewer", hook_tags)

            mcp_tags = service.get_tags_for_family("mcp")
            self.assertIn("filesystem", mcp_tags)
            self.assertNotIn("reviewer", mcp_tags)

            perm_tags = service.get_tags_for_family("permissions")
            self.assertIn("deny-prod", perm_tags)

            slash_tags = service.get_tags_for_family("slash_commands")
            self.assertIn("deploy", slash_tags)

            skill_tags = service.get_tags_for_family("skills")
            self.assertIn("academic-research", skill_tags)

            # Config is NOT an included family — verify no crosstalk
            config_tags = service.get_tags_for_family("configs")
            self.assertEqual(config_tags, {})

    def test_validation_consistent_across_families(self) -> None:
        """Validation rules (empty tag, overlength tag) apply identically to
        every family."""

        with AppTestHarness() as harness:
            hook_id = _create_hook(harness)
            mcp_name = _create_mcp(harness)
            perm_id = _create_permission(harness)
            slash_name = _create_slash_command(harness)
            agent_ref = _create_agent(harness)

            routes = [
                f"/api/hooks/{hook_id}/tags",
                f"/api/mcp/servers/{mcp_name}/tags",
                f"/api/permissions/{perm_id}/tags",
                f"/api/slash-commands/{slash_name}/tags",
                f"/api/agents/{agent_ref}/tags",
            ]

            for route in routes:
                # Empty tag -> 400
                err_empty = harness.put_json(
                    route,
                    {"tags": ["valid", "   "]},
                    expected_status=400,
                )
                self.assertEqual(
                    err_empty["code"],
                    "invalid_tag",
                    f"Empty tag should be rejected for {route}",
                )

                # Overlength tag -> 400
                err_long = harness.put_json(
                    route,
                    {"tags": ["a" * 65]},
                    expected_status=400,
                )
                self.assertEqual(
                    err_long["code"],
                    "invalid_tag",
                    f"Overlength tag should be rejected for {route}",
                )

    def test_unmanaged_same_name_different_harness_isolation(self) -> None:
        """Same-name unmanaged assets in different harnesses use distinct canonical keys
        and do not collide or overwrite each other's tags."""
        with AppTestHarness() as harness:
            # 1. Unmanaged agents in Claude vs Cursor
            claude_agent_dir = harness.spec.home / ".claude" / "agents"
            claude_agent_dir.mkdir(parents=True, exist_ok=True)
            (claude_agent_dir / "worker.md").write_text("---\nname: Worker\n---\nPrompt.", encoding="utf-8")

            cursor_agent_dir = harness.spec.home / ".cursor" / "agents"
            cursor_agent_dir.mkdir(parents=True, exist_ok=True)
            (cursor_agent_dir / "worker.md").write_text("---\nname: Worker\n---\nPrompt.", encoding="utf-8")

            # Tag claude worker vs cursor worker differently
            harness.put_json("/api/agents/claude/worker/tags", {"tags": ["claude-only", "starred"]})
            harness.put_json("/api/agents/cursor/worker/tags", {"tags": ["cursor-only"]})

            claude_detail = harness.get_json("/api/agents/claude/worker")
            self.assertEqual(claude_detail["tags"], ["starred", "claude-only"])

            cursor_detail = harness.get_json("/api/agents/cursor/worker")
            self.assertEqual(cursor_detail["tags"], ["cursor-only"])

            # 2. Unmanaged slash commands in Claude vs Cursor
            claude_cmd_dir = harness.spec.home / ".claude" / "commands"
            claude_cmd_dir.mkdir(parents=True, exist_ok=True)
            (claude_cmd_dir / "build.md").write_text("---\ndescription: Claude build\n---\nPrompt.", encoding="utf-8")

            cursor_cmd_dir = harness.spec.home / ".cursor" / "commands"
            cursor_cmd_dir.mkdir(parents=True, exist_ok=True)
            (cursor_cmd_dir / "build.md").write_text("---\ndescription: Cursor build\n---\nPrompt.", encoding="utf-8")

            harness.put_json("/api/slash-commands/unmanaged:claude:build/tags", {"tags": ["claude-build", "starred"]})
            harness.put_json("/api/slash-commands/unmanaged:cursor:build/tags", {"tags": ["cursor-build"]})

            slash_list = harness.get_json("/api/slash-commands")
            claude_rev = next(r for r in slash_list["reviewCommands"] if r["reviewRef"] == "unmanaged:claude:build")
            cursor_rev = next(r for r in slash_list["reviewCommands"] if r["reviewRef"] == "unmanaged:cursor:build")

            self.assertEqual(claude_rev["tags"], ["starred", "claude-build"])
            self.assertEqual(cursor_rev["tags"], ["cursor-build"])


if __name__ == "__main__":
    unittest.main()
