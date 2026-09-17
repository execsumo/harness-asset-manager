import tempfile
import unittest
from pathlib import Path

from harness_asset_manager.application.agents.attachments import (
    agent_roster,
    skill_attachments,
)
from harness_asset_manager.application.agents.store import AgentStore
from tests.support.app_harness import AppTestHarness


class TestAgentSkillAttachments(unittest.TestCase):
    def test_skill_attachments_inversion(self) -> None:
        with AppTestHarness() as harness:
            store_dir = harness.spec.agents_root
            store_dir.mkdir(parents=True, exist_ok=True)
            
            (store_dir / "agent1.md").write_text("---\nname: Agent 1\nskills:\n  - skill-a\n  - skill-b\n---\nbody")
            (store_dir / "agent2.md").write_text("---\nname: Agent 2\nskills:\n  - skill-b\n  - skill-c\n---\nbody")
            (store_dir / "agent3.md").write_text("---\nname: Agent 3\nskills: []\n---\nbody")
            
            store = AgentStore(store_dir, lambda _: [])
            attachments = skill_attachments(store)
            
            self.assertEqual(set(attachments.keys()), {"skill-a", "skill-b", "skill-c"})
            
            self.assertEqual(len(attachments["skill-a"]), 1)
            self.assertEqual(attachments["skill-a"][0].ref, "agent1")
            self.assertEqual(attachments["skill-a"][0].name, "Agent 1")
            
            self.assertEqual(len(attachments["skill-b"]), 2)
            refs = {a.ref for a in attachments["skill-b"]}
            self.assertEqual(refs, {"agent1", "agent2"})
            
            self.assertEqual(len(attachments["skill-c"]), 1)
            self.assertEqual(attachments["skill-c"][0].ref, "agent2")

    def test_skill_attachments_empty_store(self) -> None:
        with AppTestHarness() as harness:
            store = AgentStore(harness.spec.agents_root, lambda _: [])
            self.assertEqual(skill_attachments(store), {})

    def test_skill_attachments_malformed_agent(self) -> None:
        with AppTestHarness() as harness:
            store_dir = harness.spec.agents_root
            store_dir.mkdir(parents=True, exist_ok=True)
            
            (store_dir / "agent1.md").write_text("---\nname: Agent 1\nskills:\n  - skill-a\n---\nbody")
            (store_dir / "agent2.md").write_text("---\nbad_yaml: [\n---\nbody")
            
            store = AgentStore(store_dir, lambda _: [])
            attachments = skill_attachments(store)
            
            self.assertEqual(set(attachments.keys()), {"skill-a"})
            self.assertEqual(len(attachments["skill-a"]), 1)
            self.assertEqual(attachments["skill-a"][0].ref, "agent1")

    def test_agent_roster_lists_managed_agents_with_no_attachments(self) -> None:
        # Regression: the bulk popover's vocabulary must not come from the
        # attachment inversion. An agent with no `skills:` list is invisible to
        # skill_attachments, but must still be offerable as an attach target -
        # otherwise the very first attach is impossible.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "agents"
            root.mkdir(parents=True)
            (root / "no-skills.md").write_text("---\nname: No Skills\n---\nbody")
            (root / "has-skills.md").write_text("---\nname: Has Skills\nskills:\n  - skill-a\n---\nbody")
            store = AgentStore(root, lambda *args, **kwargs: None)

            self.assertEqual(skill_attachments(store).keys(), {"skill-a"})
            roster = agent_roster(store)
            self.assertEqual(
                [(a.ref, a.name) for a in roster],
                [("has-skills", "Has Skills"), ("no-skills", "No Skills")],
            )

    def test_agent_roster_empty_store(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = AgentStore(Path(tmp) / "missing", lambda *args, **kwargs: None)
            self.assertEqual(agent_roster(store), ())

    def test_skills_payload_carries_agent_options(self) -> None:
        # The page payload must expose the roster even when nothing is attached.
        with AppTestHarness() as harness:
            store_dir = harness.spec.agents_root
            store_dir.mkdir(parents=True, exist_ok=True)
            (store_dir / "lonely.md").write_text("---\nname: Lonely\n---\nbody")

            payload = harness.get_json("/api/skills")
            self.assertIn("agentOptions", payload)
            self.assertIn(
                {"ref": "lonely", "name": "Lonely"},
                payload["agentOptions"],
            )
            self.assertTrue(all(not row.get("agents") for row in payload["rows"]))

    def test_get_skills_no_write_guarantee(self) -> None:
        with AppTestHarness() as harness:
            store_dir = harness.spec.agents_root
            store_dir.mkdir(parents=True, exist_ok=True)
            
            (store_dir / "agent1.md").write_text("---\nname: Agent 1\nskills:\n  - skill-a\n---\nbody")
            
            mtimes = {}
            for p in store_dir.glob("*.md"):
                mtimes[p] = p.stat().st_mtime

            journal_path = harness.container.paths.mutation_audit_path
            journal_content_before = journal_path.read_text() if journal_path.exists() else ""

            # Act
            response = harness.get_json("/api/skills")
            self.assertIn("rows", response)

            # Assert no writes
            for p in store_dir.glob("*.md"):
                self.assertEqual(p.stat().st_mtime, mtimes[p])
                
            journal_content_after = journal_path.read_text() if journal_path.exists() else ""
            self.assertEqual(journal_content_before, journal_content_after)
