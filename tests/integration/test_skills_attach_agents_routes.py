from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from harness_asset_manager.atomic_files import atomic_write_text
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

    def _latest_agent_update_event(self, agent_ref: str) -> dict[str, object]:
        suffix = f"/{agent_ref}.md"
        for event in reversed(self.harness.container.mutation_audit.read_recent(limit=100)):
            if event.get("family") != "agents" or event.get("operation") != "update":
                continue
            target_paths = event.get("targetPaths", [])
            if isinstance(target_paths, list) and any(str(path).endswith(suffix) for path in target_paths):
                return event
        self.fail(f"no agents update audit event found for {agent_ref}")

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
        self.assertNotIn("- other-skill", a3)
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

    def test_profile_failure_reports_failure_without_rolling_back_agent_update(self) -> None:
        def fail_profile_config(path: Path, text: str, **kwargs) -> None:
            if path.name == "config.yaml":
                raise OSError("simulated Hermes config write failure")
            atomic_write_text(path, text, **kwargs)

        with mock.patch(
            "harness_asset_manager.application.agents.hermes_profile.atomic_write_text",
            side_effect=fail_profile_config,
        ):
            resp = self.harness.post_json("/api/skills/attach-agents", {
                "skillRefs": ["shared:shared-audit"],
                "agentRefs": ["agent-1"],
                "mode": "attach",
                "dryRun": False
            })

        self.assertEqual(resp["changed"], ["agent-1"])
        self.assertEqual(resp["skipped"], [])
        self.assertEqual(resp["failed"][0]["skillRef"], "shared:shared-audit")
        self.assertEqual(resp["failed"][0]["harness"], "hermes")
        self.assertIn("simulated Hermes config write failure", resp["failed"][0]["error"])
        a1 = (self.spec.agents_root / "agent-1.md").read_text()
        self.assertIn("- shared-audit", a1)

    def test_bulk_attach_audit_entry_matches_single_agent_update_shape(self) -> None:
        bulk_resp = self.harness.post_json("/api/skills/attach-agents", {
            "skillRefs": ["shared:shared-audit"],
            "agentRefs": ["agent-1"],
            "mode": "attach",
            "dryRun": False
        })
        self.assertEqual(bulk_resp["changed"], ["agent-1"])
        bulk_event = self._latest_agent_update_event("agent-1")

        single_resp = self.harness.put_json("/api/agents/agent-2", {
            "skills": ["other-skill", "shared-audit"]
        })
        self.assertEqual([skill["slug"] for skill in single_resp["skills"]], ["other-skill", "shared-audit"])
        single_event = self._latest_agent_update_event("agent-2")

        self.assertEqual(set(bulk_event), set(single_event))
        for key in ("version", "family", "operation", "outcome", "parameters"):
            self.assertEqual(bulk_event[key], single_event[key])
        self.assertEqual(bulk_event["family"], "agents")
        self.assertEqual(bulk_event["operation"], "update")
        self.assertEqual(bulk_event["outcome"], "succeeded")
        self.assertEqual(len(bulk_event["targetPaths"]), len(single_event["targetPaths"]))
        self.assertEqual(len(bulk_event["targetPaths"]), 1)

    def test_byte_identity_with_agent_update(self) -> None:
        # The byte-identity test — the single claim the whole design rests on (§6): a test proving
        # that attaching a skill via POST /api/skills/attach-agents and attaching the same skill via
        # the existing agent update path (PUT /api/agents/{ref}, what AgentSkillsFieldEditor calls)
        # produce byte-identical agent files. Assert on file bytes, not on parsed structures.
        bulk_resp = self.harness.post_json("/api/skills/attach-agents", {
            "skillRefs": ["shared:shared-audit"],
            "agentRefs": ["agent-bulk"],
            "mode": "attach",
            "dryRun": False
        })
        self.assertEqual(bulk_resp["changed"], ["agent-bulk"])
        self.assertEqual(bulk_resp["skipped"], [])
        
        # the PUT endpoint requires a full agent document
        single_resp = self.harness.put_json("/api/agents/agent-single", {
            "name": "Agent Bulk",
            "description": "",
            "prompt": "body",
            "skills": ["other-skill", "shared-audit"]
        })
        self.assertEqual([skill["slug"] for skill in single_resp["skills"]], ["other-skill", "shared-audit"])
        
        bulk_bytes = (self.spec.agents_root / "agent-bulk.md").read_bytes()
        single_bytes = (self.spec.agents_root / "agent-single.md").read_bytes()
        self.assertIn(b"shared-audit", bulk_bytes)
        self.assertIn(b"shared-audit", single_bytes)
        self.assertEqual(bulk_bytes, single_bytes)

