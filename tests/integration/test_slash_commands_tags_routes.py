from __future__ import annotations

import unittest

from tests.support.app_harness import AppTestHarness


class SlashCommandsTagsRoutesTests(unittest.TestCase):
    def test_slash_commands_tags_put_and_get_lifecycle(self) -> None:
        with AppTestHarness() as harness:
            # Create a slash command
            harness.post_json(
                "/api/slash-commands",
                {
                    "name": "review",
                    "description": "Code review command.",
                    "prompt": "Review this code carefully.",
                    "targets": ["claude"],
                },
            )

            # Initially empty tags in list & detail
            detail = harness.get_json("/api/slash-commands/review")
            self.assertEqual(detail["tags"], [])

            list_page = harness.get_json("/api/slash-commands")
            cmd = next(c for c in list_page["commands"] if c["name"] == "review")
            self.assertEqual(cmd["tags"], [])

            # PUT /api/slash-commands/{name}/tags - Happy path with mixed cases, duplicates, whitespace
            put_resp = harness.put_json(
                "/api/slash-commands/review/tags",
                {"tags": ["  devops  ", "DevOps", " starred ", "Core"]},
            )
            # Response returns updated tags, normalized, deduped, sorted with starred first
            self.assertEqual(put_resp["tags"], ["starred", "Core", "devops"])

            # Verify tags ride along on GET detail
            updated_detail = harness.get_json("/api/slash-commands/review")
            self.assertEqual(updated_detail["tags"], ["starred", "Core", "devops"])

            # Verify tags ride along on GET list
            updated_list = harness.get_json("/api/slash-commands")
            updated_cmd = next(c for c in updated_list["commands"] if c["name"] == "review")
            self.assertEqual(updated_cmd["tags"], ["starred", "Core", "devops"])

            # Clear tags via empty list
            clear_resp = harness.put_json(
                "/api/slash-commands/review/tags",
                {"tags": []},
            )
            self.assertEqual(clear_resp["tags"], [])
            cleared_detail = harness.get_json("/api/slash-commands/review")
            self.assertEqual(cleared_detail["tags"], [])

    def test_slash_commands_tags_put_validation_errors(self) -> None:
        with AppTestHarness() as harness:
            harness.post_json(
                "/api/slash-commands",
                {"name": "valcmd", "description": "Validation command", "prompt": "Val."},
            )

            # Empty tag string -> 400
            err_empty = harness.put_json(
                "/api/slash-commands/valcmd/tags",
                {"tags": ["valid", "   "]},
                expected_status=400,
            )
            self.assertEqual(err_empty["code"], "invalid_tag")
            self.assertIn("empty", err_empty["error"])

            # Overly long tag -> 400
            err_long = harness.put_json(
                "/api/slash-commands/valcmd/tags",
                {"tags": ["a" * 65]},
                expected_status=400,
            )
            self.assertEqual(err_long["code"], "invalid_tag")
            self.assertIn("exceeds maximum length", err_long["error"])

            # Unknown command -> 404
            err_unknown = harness.put_json(
                "/api/slash-commands/non-existent/tags",
                {"tags": ["starred"]},
                expected_status=404,
            )
            self.assertEqual(err_unknown["code"], "slash_command_not_found")

    def test_unmanaged_slash_command_tagging_and_import_migration(self) -> None:
        with AppTestHarness() as harness:
            claude_dir = harness.spec.home / ".claude" / "commands"
            claude_dir.mkdir(parents=True, exist_ok=True)
            (claude_dir / "unmanaged-cmd.md").write_text(
                "---\ndescription: Unmanaged command\n---\nPrompt body.\n",
                encoding="utf-8",
            )

            # Lists as reviewCommand
            list_page = harness.get_json("/api/slash-commands")
            review_cmd = next(r for r in list_page["reviewCommands"] if r["name"] == "unmanaged-cmd")
            review_ref = review_cmd["reviewRef"]
            self.assertEqual(review_cmd["tags"], [])

            # Tag unmanaged review command via reviewRef
            put_resp = harness.put_json(
                f"/api/slash-commands/{review_ref}/tags",
                {"tags": ["starred", "custom-tag"]},
            )
            self.assertEqual(put_resp["tags"], ["starred", "custom-tag"])

            # Review command in list now has tags
            updated_list = harness.get_json("/api/slash-commands")
            updated_review = next(r for r in updated_list["reviewCommands"] if r["name"] == "unmanaged-cmd")
            self.assertEqual(updated_review["tags"], ["starred", "custom-tag"])

            # Import unmanaged command
            import_resp = harness.post_json(
                "/api/slash-commands/review/import",
                {"target": "claude", "name": "unmanaged-cmd"},
            )
            self.assertTrue(import_resp["ok"])

            # Managed command detail retains tags
            managed_detail = harness.get_json("/api/slash-commands/unmanaged-cmd")
            self.assertEqual(managed_detail["tags"], ["starred", "custom-tag"])
