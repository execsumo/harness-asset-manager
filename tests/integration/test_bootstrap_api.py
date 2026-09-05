from __future__ import annotations

import unittest

from tests.support.app_harness import AppTestHarness
from tests.support.fake_home import seed_skill_package


class BootstrapApiTests(unittest.TestCase):
    def test_plan_and_dismiss_flow(self) -> None:
        with AppTestHarness() as harness:
            # Initially empty store -> zero linkable actions
            plan = harness.get_json("/api/bootstrap/plan")
            self.assertEqual(plan["linkableCount"], 0)
            self.assertEqual(plan["actions"], [])
            self.assertFalse(plan["dismissed"])

            # Ingest a skill and bind on harness A
            skill_src = seed_skill_package(harness.spec.home / "downloads", "my-skill", "My Skill")
            dest = harness.container.skills_store.ingest(
                source_path=skill_src,
                declared_name="My Skill",
                source_kind="github",
                source_locator="github:org/my-skill",
                source_ref="main",
            )
            harness.container.skills_mutations.enable_managed_package(dest, "claude")

            # Remove local symlink to simulate fresh arrival on machine B
            claude_symlink = harness.spec.claude_root / "my-skill"
            claude_symlink.unlink()

            # Now plan shows 1 linkable action
            plan = harness.get_json("/api/bootstrap/plan")
            self.assertEqual(plan["linkableCount"], 1)
            self.assertFalse(plan["dismissed"])
            self.assertEqual(plan["actions"][0]["family"], "skills")
            self.assertEqual(plan["actions"][0]["harness"], "claude")
            self.assertEqual(plan["actions"][0]["action"], "link")

            # Dismiss the banner
            dismiss_res = harness.post_json("/api/bootstrap/dismiss", {})
            self.assertTrue(dismiss_res["ok"])
            self.assertTrue(dismiss_res["dismissed"])

            # Subsequent plan call shows dismissed=True
            plan = harness.get_json("/api/bootstrap/plan")
            self.assertTrue(plan["dismissed"])
            self.assertEqual(plan["linkableCount"], 1)

            # Reset dismissal
            reset_res = harness.post_json("/api/bootstrap/reset-dismiss", {})
            self.assertTrue(reset_res["ok"])
            self.assertFalse(reset_res["dismissed"])

            # Subsequent plan call shows dismissed=False
            plan = harness.get_json("/api/bootstrap/plan")
            self.assertFalse(plan["dismissed"])

    def test_apply_flow(self) -> None:
        with AppTestHarness() as harness:
            # Create an agent and enable on claude
            harness.post_json(
                "/api/agents",
                {"name": "Auditor", "description": "Audit agent", "prompt": "Audit things"},
            )
            harness.post_json("/api/agents/auditor/enable", {"harness": "claude"})

            # Simulate arrival: unlink local target
            claude_agent = harness.spec.home / ".claude" / "agents" / "auditor.md"
            claude_agent.unlink()

            plan = harness.get_json("/api/bootstrap/plan")
            self.assertEqual(plan["linkableCount"], 1)

            # Apply bootstrap
            apply_res = harness.post_json(
                "/api/bootstrap/apply",
                {"actions": plan["actions"], "allowConflicts": False},
            )
            self.assertEqual(apply_res["appliedCount"], 1)
            self.assertEqual(apply_res["failedCount"], 0)
            self.assertEqual(apply_res["results"][0]["status"], "applied")

            # Verify target was created on disk
            self.assertTrue(claude_agent.is_symlink())

            # Verify subsequent plan now shows 0 linkable actions (already-linked)
            plan_after = harness.get_json("/api/bootstrap/plan")
            self.assertEqual(plan_after["linkableCount"], 0)
            self.assertEqual(plan_after["skippedCount"], 1)
            self.assertEqual(plan_after["actions"][0]["reason"], "already-linked")


if __name__ == "__main__":
    unittest.main()
