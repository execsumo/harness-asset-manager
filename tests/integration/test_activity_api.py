from __future__ import annotations

import json
import unittest

from tests.support.app_harness import AppTestHarness


class ActivityApiTests(unittest.TestCase):
    def test_returns_recent_valid_events_newest_first(self) -> None:
        with AppTestHarness() as harness:
            path = harness.container.mutation_audit.path
            path.parent.mkdir(parents=True, exist_ok=True)
            valid_events = [
                {
                    "version": 1,
                    "timestamp": "2026-08-07T10:00:00Z",
                    "family": "skills",
                    "operation": "enable",
                    "parameters": {"skill_ref": "audit", "harness": "claude"},
                    "targetPaths": [str(harness.spec.claude_root / "audit")],
                    "outcome": "succeeded",
                },
                {
                    "version": 1,
                    "timestamp": "2026-08-07T11:00:00Z",
                    "family": "mcp",
                    "operation": "reconcile_server",
                    "parameters": {"name": "exa"},
                    "targetPaths": [],
                    "outcome": "refused",
                },
            ]
            path.write_text(
                json.dumps(valid_events[0])
                + "\n"
                + '{"version":1,"timestamp":"not-a-date"}\n'
                + json.dumps(valid_events[1])
                + "\n"
                + '{"version":',
                encoding="utf-8",
            )

            payload = harness.get_json("/api/activity?limit=2")

            self.assertEqual(
                [(event["family"], event["operation"]) for event in payload["events"]],
                [("mcp", "reconcile_server"), ("skills", "enable")],
            )
            self.assertEqual(payload["events"][0]["outcome"], "refused")

    def test_rejects_out_of_range_limit(self) -> None:
        with AppTestHarness() as harness:
            harness.get_json("/api/activity?limit=201", expected_status=422)


if __name__ == "__main__":
    unittest.main()
