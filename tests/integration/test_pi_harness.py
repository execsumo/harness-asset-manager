from __future__ import annotations

import unittest

from tests.support.app_harness import AppTestHarness
from tests.support.fake_home import FakeHomeSpec, seed_skill_package, write_cli_stub


def seed_pi_installation(spec: FakeHomeSpec) -> None:
    pi_agent = spec.home / ".pi" / "agent"
    for directory in (pi_agent / "skills", pi_agent / "agents", pi_agent / "prompts"):
        directory.mkdir(parents=True, exist_ok=True)
    write_cli_stub(spec.bin_dir / "pi", "pi")


class PiHarnessIntegrationTests(unittest.TestCase):
    def test_pi_uses_its_global_agent_store_for_skills_agents_and_prompts(self) -> None:
        def seed(spec: FakeHomeSpec) -> None:
            seed_pi_installation(spec)
            seed_skill_package(
                spec.home / ".pi" / "agent" / "skills",
                "pi-skill",
                "Pi Skill",
            )

        with AppTestHarness(fixture_factory=seed) as harness:
            skills = harness.get_json("/api/skills")
            pi_column = next(column for column in skills["harnessColumns"] if column["harness"] == "pi")
            self.assertTrue(pi_column["installed"])
            self.assertEqual(pi_column["logoKey"], "pi")
            self.assertTrue(
                any(
                    cell["harness"] == "pi" and cell["state"] == "found"
                    for row in skills["rows"]
                    for cell in row["cells"]
                )
            )

            harness.post_json(
                "/api/agents",
                {
                    "name": "Pi Reviewer",
                    "description": "Reviews code",
                    "prompt": "Review the code.",
                    "harnesses": ["pi"],
                },
            )
            agent_path = harness.spec.home / ".pi" / "agent" / "agents" / "pi-reviewer.md"
            self.assertTrue(agent_path.is_symlink())
            self.assertEqual(agent_path.resolve(), harness.container.agents_store.path_for("pi-reviewer").resolve())

            harness.post_json(
                "/api/slash-commands",
                {
                    "name": "pi-review",
                    "description": "Review code",
                    "prompt": "Review the code.",
                    "targets": ["pi"],
                },
            )
            prompt_path = harness.spec.home / ".pi" / "agent" / "prompts" / "pi-review.md"
            self.assertTrue(prompt_path.is_file())
            self.assertIn("Review the code.", prompt_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
