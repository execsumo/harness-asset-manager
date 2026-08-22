from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from harness_asset_manager.application.config_auto_adopt import (
    McpAutoAdoptService,
    ObservedConfigAutoAdoptService,
)
from harness_asset_manager.application.mutation_audit import MutationAuditJournal
from harness_asset_manager.errors import MutationError


def _journal(root: Path) -> MutationAuditJournal:
    return MutationAuditJournal(root / "app" / "mutation-audit.jsonl")


class AlreadyManagedRaceTests(unittest.TestCase):
    """A reconcile that loses an adoption race must not record a failed event.

    Every read endpoint runs reconcile over one shared service instance in a
    threadpool, so two concurrent readers can both decide to adopt the same
    unmanaged entry. The loser hits the mutation service's ``already managed``
    409 after the winner has already adopted — the desired outcome, not a
    failure to pollute the Activity trail with.
    """

    def _outcomes(self, journal: MutationAuditJournal) -> list[dict[str, object]]:
        return [
            event
            for event in journal.read_recent(limit=10)
            if event.get("operation") == "auto_adopt"
        ]

    def test_mcp_concurrent_adoption_409_is_not_recorded_as_failed(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = _journal(root)

            def adopt(name: str, *, harnesses: list[str] | None = None) -> dict[str, object]:
                raise MutationError("a managed server named 'x' already exists")

            group = SimpleNamespace(
                name="x",
                identical=True,
                canonical_spec=object(),
                sightings=(SimpleNamespace(harness="claude"),),
            )
            service = McpAutoAdoptService(
                planner=SimpleNamespace(plan=lambda: SimpleNamespace(groups=(group,))),
                mutations=SimpleNamespace(
                    read_models=SimpleNamespace(enabled_writable_adapters=lambda: []),
                    adopt=adopt,
                ),
                is_enabled=lambda: True,
                journal=journal,
            )

            service.reconcile()

            self.assertEqual(self._outcomes(journal), [])

    def test_mcp_genuine_failure_is_still_recorded(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = _journal(root)
            group = SimpleNamespace(
                name="x",
                identical=True,
                canonical_spec=object(),
                sightings=(SimpleNamespace(harness="claude"),),
            )
            service = McpAutoAdoptService(
                planner=SimpleNamespace(plan=lambda: SimpleNamespace(groups=(group,))),
                mutations=SimpleNamespace(
                    read_models=SimpleNamespace(enabled_writable_adapters=lambda: []),
                    adopt=lambda name, harnesses=None: (_ for _ in ()).throw(OSError("disk full")),
                ),
                is_enabled=lambda: True,
                journal=journal,
            )

            service.reconcile()

            outcomes = self._outcomes(journal)
            self.assertEqual(len(outcomes), 1)
            self.assertEqual(outcomes[0]["outcome"], "failed")
            self.assertEqual(outcomes[0]["errorType"], "OSError")

    def test_observed_config_concurrent_promotion_409_is_not_recorded_as_failed(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            journal = _journal(root)
            scan_entry = SimpleNamespace(id="x", state="unmanaged", parsed_spec=object())
            service = ObservedConfigAutoAdoptService(
                read_models=SimpleNamespace(
                    snapshot=lambda: SimpleNamespace(harness_scans=(
                        SimpleNamespace(harness="claude", entries=(scan_entry,)),
                    ))
                ),
                store=SimpleNamespace(list_managed=lambda: []),
                promote=lambda ref, observed_harness=None: (_ for _ in ()).throw(
                    MutationError("hook 'x' is already managed")
                ),
                family="hooks",
                is_enabled=lambda: True,
                journal=journal,
            )

            service.reconcile()

            self.assertEqual(self._outcomes(journal), [])


__all__ = ["AlreadyManagedRaceTests"]
