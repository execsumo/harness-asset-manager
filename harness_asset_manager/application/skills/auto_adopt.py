from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from harness_asset_manager.application.auto_adopt import record_auto_adopt
from harness_asset_manager.application.mutation_audit import MutationAuditJournal
from harness_asset_manager.atomic_files import file_lock

from .inventory import InventoryEntry, SkillInventory
from .mutations import SkillsMutationService
from .read_models import SkillsReadModelService


@dataclass(frozen=True)
class SkillsAutoAdoptOutcome:
    adopted: tuple[str, ...] = ()
    skipped: tuple[tuple[str, str], ...] = ()


class SkillsAutoAdoptService:
    """Adopt new, unmanaged skill directories when their ownership is unambiguous.

    Skills are directory symlinks, so an existing managed binding cannot be
    clobbered by the harness. The only automatic case here is a genuinely new
    local directory. All copies of the same skill must have the same fingerprint;
    differing local copies remain for manual review.
    """

    def __init__(
        self,
        *,
        read_models: SkillsReadModelService,
        mutations: SkillsMutationService,
        is_enabled: Callable[[], bool],
        journal: MutationAuditJournal,
        lock_path: Path,
        default_harnesses: Callable[[], tuple[str, ...]] | None = None,
    ) -> None:
        self.read_models = read_models
        self.mutations = mutations
        self.is_enabled = is_enabled
        self.journal = journal
        self.lock_path = lock_path
        self.default_harnesses = default_harnesses or (lambda: ())
        self._is_reconciling = False

    def reconcile(self) -> SkillsAutoAdoptOutcome:
        if not self.is_enabled() or self._is_reconciling:
            return SkillsAutoAdoptOutcome()

        self._is_reconciling = True
        try:
            with file_lock(self.lock_path):
                snapshot = self.read_models.snapshot()
                inventory = SkillInventory.from_snapshot(
                    store_scan=snapshot.store_scan,
                    harness_scans=self.read_models.visible_scans(snapshot),
                )
                unmanaged = [entry for entry in inventory.entries if entry.kind == "unmanaged"]
                grouped: dict[tuple[str, str, str], list[InventoryEntry]] = defaultdict(list)
                for entry in unmanaged:
                    grouped[(entry.name, entry.source.kind, entry.source.locator)].append(entry)

                adopted: list[str] = []
                skipped: list[tuple[str, str]] = []
                for entries in grouped.values():
                    revisions = {entry.current_revision for entry in entries}
                    if len(revisions) != 1:
                        for entry in entries:
                            skipped.append((entry.skill_ref, "different local revisions require review"))
                        continue
                    entry = entries[0]
                    reason = self._unsafe_reason(entry)
                    if reason is not None:
                        skipped.append((entry.skill_ref, reason))
                        continue
                    try:
                        package_path = self.mutations.manage_entry(entry)
                        enabled = {
                            adapter.harness for adapter in self.read_models.enabled_installed_adapters()
                        }
                        for harness in self.default_harnesses():
                            if harness in enabled:
                                self.mutations.enable_managed_package(package_path, harness)
                    except Exception as error:  # noqa: BLE001 — keep one bad skill from blocking the inventory
                        skipped.append((entry.skill_ref, str(error)))
                        record_auto_adopt(
                            self.journal,
                            family="skills",
                            ref=entry.skill_ref,
                            target_paths=self._paths(entry),
                            outcome="failed",
                            error_type=error.__class__.__name__,
                        )
                        continue
                    adopted.append(entry.skill_ref)
                    record_auto_adopt(
                        self.journal,
                        family="skills",
                        ref=entry.skill_ref,
                        target_paths=self._paths(entry),
                    )

                if adopted:
                    self.read_models.invalidate()
                return SkillsAutoAdoptOutcome(tuple(adopted), tuple(skipped))
        finally:
            self._is_reconciling = False

    @staticmethod
    def _unsafe_reason(entry: InventoryEntry) -> str | None:
        sightings = [sighting for sighting in entry.sightings if sighting.kind == "harness"]
        if not sightings:
            return "no harness copy was found"
        for sighting in sightings:
            if sighting.path is None:
                return "harness path is unavailable"
            if sighting.path.is_symlink():
                return "a symlink is not auto-adopted"
            if not sighting.path.is_dir():
                return "harness path is not a directory"
        return None

    @staticmethod
    def _paths(entry: InventoryEntry) -> tuple[str, ...]:
        return tuple(
            str(sighting.path)
            for sighting in entry.sightings
            if sighting.path is not None
        )


__all__ = ["SkillsAutoAdoptOutcome", "SkillsAutoAdoptService"]
