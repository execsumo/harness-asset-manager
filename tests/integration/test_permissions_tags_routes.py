from __future__ import annotations

import unittest

from tests.support.app_harness import AppTestHarness


class PermissionsTagsRoutesTests(unittest.TestCase):
    def test_permissions_tags_put_and_get_lifecycle(self) -> None:
        with AppTestHarness() as harness:
            # Create a managed permission
            harness.post_json(
                "/api/permissions",
                {
                    "id": "deny-prod-deploy",
                    "decision": "deny",
                    "scope": "shell",
                    "pattern": "kubectl apply *prod*",
                    "description": "Block production kubectl",
                },
            )

            # Initially empty tags in list & detail
            detail = harness.get_json("/api/permissions/deny-prod-deploy")
            self.assertEqual(detail["tags"], [])

            list_page = harness.get_json("/api/permissions")
            entry = next(e for e in list_page["entries"] if e["id"] == "deny-prod-deploy")
            self.assertEqual(entry["tags"], [])

            # PUT /api/permissions/{id}/tags
            put_resp = harness.put_json(
                "/api/permissions/deny-prod-deploy/tags",
                {"tags": ["  security  ", "Security", " starred ", "Production"]},
            )
            self.assertEqual(put_resp["tags"], ["starred", "Production", "security"])

            # Verify tags ride along on GET detail
            updated_detail = harness.get_json("/api/permissions/deny-prod-deploy")
            self.assertEqual(updated_detail["tags"], ["starred", "Production", "security"])

            # Verify tags ride along on GET list
            updated_list = harness.get_json("/api/permissions")
            updated_entry = next(e for e in updated_list["entries"] if e["id"] == "deny-prod-deploy")
            self.assertEqual(updated_entry["tags"], ["starred", "Production", "security"])

            # Clear tags
            clear_resp = harness.put_json(
                "/api/permissions/deny-prod-deploy/tags",
                {"tags": []},
            )
            self.assertEqual(clear_resp["tags"], [])
            cleared_detail = harness.get_json("/api/permissions/deny-prod-deploy")
            self.assertEqual(cleared_detail["tags"], [])

    def test_permissions_tags_put_validation_errors(self) -> None:
        with AppTestHarness() as harness:
            harness.post_json(
                "/api/permissions",
                {
                    "id": "deny-rm-rf",
                    "decision": "deny",
                    "scope": "shell",
                    "pattern": "rm -rf",
                    "description": "Block rm -rf",
                },
            )

            # Empty tag -> 400
            err_empty = harness.put_json(
                "/api/permissions/deny-rm-rf/tags",
                {"tags": ["valid", "   "]},
                expected_status=400,
            )
            self.assertEqual(err_empty["code"], "invalid_tag")

            # Overly long tag -> 400
            err_long = harness.put_json(
                "/api/permissions/deny-rm-rf/tags",
                {"tags": ["x" * 65]},
                expected_status=400,
            )
            self.assertEqual(err_long["code"], "invalid_tag")

            # Unknown permission -> 404
            err_unknown = harness.put_json(
                "/api/permissions/non-existent-perm/tags",
                {"tags": ["starred"]},
                expected_status=404,
            )
            self.assertEqual(err_unknown["code"], "not_found")
