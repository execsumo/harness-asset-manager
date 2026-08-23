from __future__ import annotations

import unittest

from tests.support.app_harness import AppTestHarness


class SkillsRoutingTests(unittest.TestCase):
    def test_missing_subroute_returns_404_not_405(self) -> None:
        with AppTestHarness(mixed=True) as harness:
            # 1. GET detail with URL-encoded colon -> 200
            detail = harness.get_json("/api/skills/shared%3Ashared-audit")
            self.assertEqual(detail["name"], "Shared Audit")

            # GET detail with raw colon -> 200
            detail_raw = harness.get_json("/api/skills/shared:shared-audit")
            self.assertEqual(detail_raw["name"], "Shared Audit")

            # 2. GET source-status -> 200
            status = harness.get_json("/api/skills/shared%3Ashared-audit/source-status")
            self.assertIn("updateStatus", status)

            # 3. PUT tags -> 200
            tags_resp = harness.put_json(
                "/api/skills/shared%3Ashared-audit/tags",
                {"tags": ["test"]},
            )
            self.assertEqual(tags_resp["tags"], ["test"])

            # 4. Unknown sub-route under skills -> MUST return 404, NOT 405
            put_404 = harness.put_json(
                "/api/skills/shared%3Ashared-audit/nonexistent-subroute",
                {"anything": "value"},
                expected_status=404,
            )
            self.assertEqual(put_404.get("code"), "not_found")

            get_404 = harness.get_json(
                "/api/skills/shared%3Ashared-audit/nonexistent-subroute",
                expected_status=404,
            )
            self.assertEqual(get_404.get("code"), "not_found")

            post_404 = harness.post_json(
                "/api/skills/shared%3Ashared-audit/nonexistent-subroute",
                {},
                expected_status=404,
            )
            self.assertEqual(post_404.get("code"), "not_found")

            delete_404 = harness.delete_json(
                "/api/skills/shared%3Ashared-audit/nonexistent-subroute",
                expected_status=404,
            )
            self.assertEqual(delete_404.get("code"), "not_found")

    def test_unknown_api_endpoints_return_404_json_envelope(self) -> None:
        with AppTestHarness(mixed=True) as harness:
            for method, caller in [
                ("GET", lambda p: harness.get_json(p, expected_status=404)),
                ("POST", lambda p: harness.post_json(p, {}, expected_status=404)),
                ("PUT", lambda p: harness.put_json(p, {}, expected_status=404)),
                ("DELETE", lambda p: harness.delete_json(p, expected_status=404)),
            ]:
                resp = caller("/api/nonexistent-endpoint")
                self.assertEqual(resp.get("code"), "not_found", f"{method} returned {resp}")
                self.assertIn("unknown api path", resp.get("error", ""))
