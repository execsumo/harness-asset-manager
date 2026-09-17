from __future__ import annotations

import unittest

from tests.support.app_harness import AppTestHarness
from tests.support.fake_home import seed_shared_only_fixture


class TestSkillsAttachAgentsRoutes(unittest.TestCase):
    def setUp(self) -> None:
        self.harness_ctx = AppTestHarness()
        self.harness = self.harness_ctx.__enter__()
        self.spec = self.harness.spec
        seed_shared_only_fixture(self.spec)

        from harness_asset_manager.application.skills.manifest import SkillStoreEntry
        from tests.support.fake_home import seed_skill_package, seed_store_manifest
        pkg_other = seed_skill_package(
            self.spec.skills_store_root,
            "other-skill",
            "Other Skill",
            body="test"
        )
        self.spec.skills_store_root.joinpath("manifest.json").unlink(missing_ok=True)
        seed_store_manifest(
            self.spec,
            [
                SkillStoreEntry(
                    package_dir="shared-audit",
                    declared_name="Shared Audit",
                    source_kind="github",
                    source_locator="github:mode-io/shared-audit",
                    revision="fake"
                ),
                SkillStoreEntry(
                    package_dir="other-skill",
                    declared_name="Other Skill",
                    source_kind="github",
                    source_locator="github:mode-io/other",
                    revision="fake"
                )
            ]
        )

        

        self.harness.post_json("/api/agents", {"name": "Agent 1", "prompt": "body", "skills": ["other-skill"], "slug": "agent-1"})
        self.harness.post_json("/api/agents", {"name": "Agent 2", "prompt": "body", "skills": ["other-skill"], "slug": "agent-2"})
        self.harness.post_json("/api/agents", {"name": "Agent 3", "prompt": "body", "skills": ["other-skill", "shared-audit"], "slug": "agent-3"})
        self.harness.post_json("/api/agents", {"name": "Agent Bulk", "prompt": "body", "skills": ["other-skill"], "slug": "agent-bulk"})
        self.harness.post_json("/api/agents", {"name": "Agent Single", "prompt": "body", "skills": ["other-skill"], "slug": "agent-single"})

        
        
    def tearDown(self) -> None:
        self.harness_ctx.__exit__(None, None, None)

    def test_attach_agents(self) -> None:
        # Attach shared-audit to agent1 and agent2
        resp = self.harness.post_json("/api/skills/attach-agents", {
            "skillRefs": ["shared:shared-audit"],
            "agentRefs": ["agent-1", "agent-2"],
            "mode": "attach",
            "dryRun": False
        })
        data = resp
        self.assertEqual(data["changed"], ["agent-1", "agent-2"])
        
        # Verify
        a1 = (self.spec.agents_root / "agent-1.md").read_text()
        self.assertIn("- shared-audit", a1)

    def test_dry_run_matches_apply(self) -> None:
        payload = {
            "skillRefs": ["shared:shared-audit"],
            "agentRefs": ["agent-1", "agent-2"],
            "mode": "attach",
            "dryRun": True
        }
        dry = self.harness.post_json("/api/skills/attach-agents", payload)
        
        payload["dryRun"] = False
        apply = self.harness.post_json("/api/skills/attach-agents", payload)
        
        self.assertEqual(dry["changed"], apply["changed"])
        self.assertEqual(dry["autoEnabled"], apply["autoEnabled"])
        self.assertEqual(dry["failed"], apply["failed"])

    def test_detach_agents(self) -> None:
        resp = self.harness.post_json("/api/skills/attach-agents", {
            "skillRefs": ["shared:other-skill"],
            "agentRefs": ["agent-3"],
            "mode": "detach",
            "dryRun": False
        })
        self.assertEqual(resp["changed"], ["agent-3"])
        a3 = (self.spec.agents_root / "agent-3.md").read_text()
        self.assertIn("- shared-audit", a3)

    def test_unmanaged_rejection(self) -> None:
        resp = self.harness.post_json("/api/skills/attach-agents", {
            "skillRefs": ["unmanaged:foo"],
            "agentRefs": ["agent-1"],
            "mode": "attach",
            "dryRun": False
        }, expected_status=400)
        self.assertEqual(resp["code"], "invalid_skill")

    def test_partial_failure(self) -> None:
        # agent-bad fails to parse
        (self.spec.agents_root / "agent-bad.md").write_text("invalid")
        resp = self.harness.post_json("/api/skills/attach-agents", {
            "skillRefs": ["shared:shared-audit"],
            "agentRefs": ["agent-1", "agent-bad"],
            "mode": "attach",
            "dryRun": False
        })
        data = resp
        self.assertIn("agent-1", data["changed"])
        # Should be skipped or failed
        skipped_refs = [s["ref"] for s in data["skipped"]]
        self.assertIn("agent-bad", skipped_refs)

    def test_byte_identity_with_agent_update(self) -> None:
        # The byte-identity test — the single claim the whole design rests on (§6): a test proving
        # that attaching a skill via POST /api/skills/attach-agents and attaching the same skill via
        # the existing agent update path (PUT /api/agents/{ref}, what AgentSkillsFieldEditor calls)
        # produce byte-identical agent files. Assert on file bytes, not on parsed structures.
        
        
        self.harness.post_json("/api/skills/attach-agents", {
            "skillRefs": ["shared:shared-audit"],
            "agentRefs": ["agent-bulk"],
            "mode": "attach",
            "dryRun": False
        })
        
        # the PUT endpoint requires a full agent document
        self.harness.put_json("/api/agents/agent-single", {
            "name": "Agent Bulk",
            "description": "",
            "prompt": "body",
            "skills": ["other-skill", "shared-audit"]
        })
        
        bulk_bytes = (self.spec.agents_root / "agent-bulk.md").read_bytes()
        single_bytes = (self.spec.agents_root / "agent-single.md").read_bytes()
        self.assertEqual(bulk_bytes, single_bytes)

