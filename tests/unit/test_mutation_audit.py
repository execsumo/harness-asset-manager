from __future__ import annotations

import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from harness_asset_manager.application.mutation_audit import (
    AuditedMutationService,
    MutationAuditJournal,
    MutationPathTracker,
)


class _ExampleMutations:
    def __init__(self, target: Path) -> None:
        self.target = target

    def update(
        self,
        name: str,
        *,
        harness: str,
        config: dict[str, object],
        prompt: str,
    ) -> dict[str, object]:
        self.target.write_text("changed", encoding="utf-8")
        return {"ok": True, "name": name}

    def fail(self, name: str) -> None:
        raise ValueError(f"refused {name}")

    def partial(self, name: str) -> dict[str, object]:
        self.target.write_text("partly changed", encoding="utf-8")
        return {"ok": False, "succeeded": ["claude"], "failed": ["codex"]}


class MutationAuditJournalTests(unittest.TestCase):
    def test_proxy_records_changed_paths_without_secret_bearing_arguments(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "config.json"
            journal = MutationAuditJournal(
                root / "audit.log",
                now=lambda: datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc),
            )
            service = AuditedMutationService(
                _ExampleMutations(target),
                family="mcp",
                methods={"update"},
                journal=journal,
                path_tracker=MutationPathTracker(lambda: ((target, False),)),
            )

            result = service.update(
                "exa",
                harness="claude",
                config={"API_KEY": "literal-secret"},
                prompt="also-secret",
            )

            self.assertEqual(result, {"ok": True, "name": "exa"})
            event = journal.read_recent()[0]
            self.assertEqual(event["timestamp"], "2026-08-06T12:00:00Z")
            self.assertEqual(event["family"], "mcp")
            self.assertEqual(event["operation"], "update")
            self.assertEqual(event["parameters"], {"name": "exa", "harness": "claude"})
            self.assertEqual(event["targetPaths"], [str(target)])
            self.assertEqual(event["outcome"], "succeeded")
            serialized = json.dumps(event)
            self.assertNotIn("literal-secret", serialized)
            self.assertNotIn("also-secret", serialized)

    def test_failures_and_partial_results_have_distinct_outcomes(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "config.json"
            journal = MutationAuditJournal(root / "audit.log")
            service = AuditedMutationService(
                _ExampleMutations(target),
                family="hooks",
                methods={"fail", "partial"},
                journal=journal,
                path_tracker=MutationPathTracker(lambda: ((target, False),)),
            )

            with self.assertRaises(ValueError):
                service.fail("lint")
            service.partial("lint")

            failed, partial = journal.read_recent()
            self.assertEqual(failed["outcome"], "failed")
            self.assertEqual(failed["errorType"], "ValueError")
            self.assertNotIn("error", failed)
            self.assertEqual(partial["outcome"], "partial")

    def test_concurrent_appends_leave_complete_json_lines(self) -> None:
        with TemporaryDirectory() as tmp:
            journal = MutationAuditJournal(Path(tmp) / "audit.log")

            def append(index: int) -> None:
                journal.append(
                    family="agents",
                    operation="enable",
                    parameters={"name": str(index)},
                    target_paths=(),
                    outcome="succeeded",
                )

            with ThreadPoolExecutor(max_workers=8) as executor:
                tuple(executor.map(append, range(40)))

            events = journal.read_recent(limit=100)
            self.assertEqual(len(events), 40)
            self.assertEqual({event["parameters"]["name"] for event in events}, {str(i) for i in range(40)})

    def test_recent_reader_skips_a_truncated_line(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.log"
            path.write_text('{"operation":"ok"}\n{"operation":', encoding="utf-8")

            events = MutationAuditJournal(path).read_recent()

            self.assertEqual(events, ({"operation": "ok"},))

    def test_recent_reader_returns_requested_valid_events_despite_corrupt_lines(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.log"
            path.write_text(
                '{"operation":"old"}\nnot-json\n{"operation":"first"}\n{broken}\n{"operation":"second"}\n',
                encoding="utf-8",
            )

            events = MutationAuditJournal(path).read_recent(limit=2)

            self.assertEqual(events, ({"operation": "first"}, {"operation": "second"}))

    def test_recent_reader_bounds_bytes_read_from_large_journal(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "audit.log"
            path.write_text(
                '{"operation":"old"}\n' + ("x" * 256) + '\n{"operation":"recent"}\n',
                encoding="utf-8",
            )

            events = MutationAuditJournal(path).read_recent(limit=10, max_bytes=64)

            self.assertEqual(events, ({"operation": "recent"},))


if __name__ == "__main__":
    unittest.main()
