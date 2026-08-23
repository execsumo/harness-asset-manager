from __future__ import annotations

import unittest

from tests.support.app_harness import AppTestHarness


class HooksTagsRoutesTests(unittest.TestCase):
    def test_hooks_tags_put_and_get_lifecycle(self) -> None:
        with AppTestHarness() as harness:
            # Create a managed hook
            harness.post_json(
                "/api/hooks",
                {
                    "id": "pre-compact",
                    "event": "pre_compact",
                    "command": "echo compacting",
                    "description": "Pre compact hook",
                },
            )

            # Initially empty tags in list & detail
            detail = harness.get_json("/api/hooks/pre-compact")
            self.assertEqual(detail["tags"], [])

            list_page = harness.get_json("/api/hooks")
            entry = next(e for e in list_page["entries"] if e["id"] == "pre-compact")
            self.assertEqual(entry["tags"], [])

            # PUT /api/hooks/{id}/tags - Normalization, deduplication, sorting
            put_resp = harness.put_json(
                "/api/hooks/pre-compact/tags",
                {"tags": ["  security  ", "Security", " starred ", "Audit"]},
            )
            self.assertEqual(put_resp["tags"], ["starred", "Audit", "security"])

            # Verify tags ride along on GET detail
            updated_detail = harness.get_json("/api/hooks/pre-compact")
            self.assertEqual(updated_detail["tags"], ["starred", "Audit", "security"])

            # Verify tags ride along on GET list
            updated_list = harness.get_json("/api/hooks")
            updated_entry = next(e for e in updated_list["entries"] if e["id"] == "pre-compact")
            self.assertEqual(updated_entry["tags"], ["starred", "Audit", "security"])

            # Clear tags
            clear_resp = harness.put_json(
                "/api/hooks/pre-compact/tags",
                {"tags": []},
            )
            self.assertEqual(clear_resp["tags"], [])
            cleared_detail = harness.get_json("/api/hooks/pre-compact")
            self.assertEqual(cleared_detail["tags"], [])

    def test_hooks_tags_put_validation_errors(self) -> None:
        with AppTestHarness() as harness:
            harness.post_json(
                "/api/hooks",
                {
                    "id": "valhook",
                    "event": "pre_tool_use",
                    "command": "echo val",
                },
            )

            # Empty tag -> 400
            err_empty = harness.put_json(
                "/api/hooks/valhook/tags",
                {"tags": ["valid", "   "]},
                expected_status=400,
            )
            self.assertEqual(err_empty["code"], "invalid_tag")

            # Overly long tag -> 400
            err_long = harness.put_json(
                "/api/hooks/valhook/tags",
                {"tags": ["x" * 65]},
                expected_status=400,
            )
            self.assertEqual(err_long["code"], "invalid_tag")

            # Unknown hook -> 404
            err_unknown = harness.put_json(
                "/api/hooks/non-existent-hook/tags",
                {"tags": ["starred"]},
                expected_status=404,
            )
            self.assertEqual(err_unknown["code"], "hook_not_found")
