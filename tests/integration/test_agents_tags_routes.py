from __future__ import annotations

import unittest

from tests.support.app_harness import AppTestHarness
from tests.support.fake_home import FakeHomeSpec


def _seed_unmanaged_claude_agent(spec: FakeHomeSpec, slug: str = "stray") -> None:
    agents_dir = spec.home / ".claude" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    (agents_dir / f"{slug}.md").write_text(
        f"---\nname: {slug.title()}\ndescription: found in claude\n---\n\nharness body\n",
        encoding="utf-8",
    )


class AgentsTagsRoutesTests(unittest.TestCase):
    def test_agents_tags_put_and_get_lifecycle(self) -> None:
        with AppTestHarness() as harness:
            create_resp = harness.post_json(
                "/api/agents",
                {
                    "name": "Reviewer",
                    "description": "Reviews code.",
                    "prompt": "You are a code reviewer.",
                    "tools": ["read_file"],
                },
            )
            slug = create_resp["ref"]

            # Initially empty tags in list & detail
            detail = harness.get_json(f"/api/agents/{slug}")
            self.assertEqual(detail["tags"], [])

            list_page = harness.get_json("/api/agents")
            row = next(r for r in list_page["entries"] if r["ref"] == slug)
            self.assertEqual(row["tags"], [])

            # PUT /api/agents/{slug}/tags - Happy path with mixed cases, duplicates, whitespace
            put_resp = harness.put_json(
                f"/api/agents/{slug}/tags",
                {"tags": ["  devops  ", "DevOps", " starred ", "Core"]},
            )
            # Response returns updated tags, normalized, deduped, sorted with starred first
            self.assertEqual(put_resp["tags"], ["starred", "Core", "devops"])

            # Verify tags ride along on GET detail
            updated_detail = harness.get_json(f"/api/agents/{slug}")
            self.assertEqual(updated_detail["tags"], ["starred", "Core", "devops"])

            # Verify tags ride along on GET list
            updated_list = harness.get_json("/api/agents")
            updated_row = next(r for r in updated_list["entries"] if r["ref"] == slug)
            self.assertEqual(updated_row["tags"], ["starred", "Core", "devops"])

            # Clear tags via empty list
            clear_resp = harness.put_json(
                f"/api/agents/{slug}/tags",
                {"tags": []},
            )
            self.assertEqual(clear_resp["tags"], [])
            cleared_detail = harness.get_json(f"/api/agents/{slug}")
            self.assertEqual(cleared_detail["tags"], [])

    def test_agents_tags_put_validation_errors(self) -> None:
        with AppTestHarness() as harness:
            harness.post_json(
                "/api/agents",
                {"name": "ValAgent", "description": "Validation Agent", "prompt": "Val."},
            )

            # Empty tag string -> 400
            err_empty = harness.put_json(
                "/api/agents/valagent/tags",
                {"tags": ["valid", "   "]},
                expected_status=400,
            )
            self.assertEqual(err_empty["code"], "invalid_tag")
            self.assertIn("empty", err_empty["error"])

            # Overly long tag -> 400
            err_long = harness.put_json(
                "/api/agents/valagent/tags",
                {"tags": ["a" * 65]},
                expected_status=400,
            )
            self.assertEqual(err_long["code"], "invalid_tag")
            self.assertIn("exceeds maximum length", err_long["error"])

            # Unknown agent -> 404
            err_unknown = harness.put_json(
                "/api/agents/non-existent/tags",
                {"tags": ["starred"]},
                expected_status=404,
            )
            self.assertEqual(err_unknown["code"], "agent_not_found")

    def test_unmanaged_agent_tagging_and_adoption_migration(self) -> None:
        with AppTestHarness() as harness:
            _seed_unmanaged_claude_agent(harness.spec, "stray")

            # Unmanaged agent is taggable via its canonical ref
            put_resp = harness.put_json(
                "/api/agents/claude/stray/tags",
                {"tags": ["starred", "imported-soon"]},
            )
            self.assertEqual(put_resp["tags"], ["starred", "imported-soon"])

            # Detail shows tags
            detail = harness.get_json("/api/agents/claude/stray")
            self.assertEqual(detail["tags"], ["starred", "imported-soon"])

            # List shows tags for unmanaged row
            list_page = harness.get_json("/api/agents")
            row = next(r for r in list_page["entries"] if r["ref"] == "claude/stray")
            self.assertEqual(row["tags"], ["starred", "imported-soon"])

            # Adopt agent
            adopt_resp = harness.post_json(
                "/api/agents/claude/stray/adopt",
                {},
            )
            self.assertEqual(adopt_resp["ref"], "stray")

            # Managed agent detail retains tags!
            managed_detail = harness.get_json("/api/agents/stray")
            self.assertEqual(managed_detail["tags"], ["starred", "imported-soon"])
