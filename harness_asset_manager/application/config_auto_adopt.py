from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from harness_asset_manager.application.auto_adopt import record_auto_adopt
from harness_asset_manager.application.mutation_audit import MutationAuditJournal


class ObservedConfigAutoAdoptService:
    """Promote equivalent unmanaged hook/permission entries into their manifest.

    These families are embedded in harness-owned config documents. Promotion only
    writes the normalized manifest; it never rewrites a harness config during the
    automatic pass.
    """

    def __init__(
        self,
        *,
        read_models: object,
        store: object,
        promote: Callable[..., object],
        family: str,
        is_enabled: Callable[[], bool],
        journal: MutationAuditJournal,
    ) -> None:
        self.read_models = read_models
        self.store = store
        self.promote = promote
        self.family = family
        self.is_enabled = is_enabled
        self.journal = journal

    def reconcile(self) -> None:
        if not self.is_enabled():
            return
        snapshot = self.read_models.snapshot()
        grouped: dict[str, list[tuple[str, object]]] = defaultdict(list)
        for scan in snapshot.harness_scans:
            for entry in scan.entries:
                if entry.state == "unmanaged" and entry.parsed_spec is not None:
                    grouped[entry.id].append((scan.harness, entry.parsed_spec))

        managed_ids = {spec.id for spec in self.store.list_managed()}
        for ref, sightings in grouped.items():
            if ref in managed_ids or not sightings:
                continue
            first_spec = sightings[0][1]
            if any(spec != first_spec for _harness, spec in sightings[1:]):
                continue
            try:
                self.promote(ref, observed_harness=sightings[0][0])
            except Exception as error:  # noqa: BLE001 — leave ambiguous/failed entries for review
                record_auto_adopt(
                    self.journal,
                    family=self.family,
                    ref=ref,
                    outcome="failed",
                    error_type=error.__class__.__name__,
                )
                continue
            record_auto_adopt(self.journal, family=self.family, ref=ref)


class McpAutoAdoptService:
    """Adopt unmanaged MCP servers only when every observed config is identical."""

    def __init__(
        self,
        *,
        planner: object,
        mutations: object,
        is_enabled: Callable[[], bool],
        journal: MutationAuditJournal,
    ) -> None:
        self.planner = planner
        self.mutations = mutations
        self.is_enabled = is_enabled
        self.journal = journal

    def reconcile(self) -> None:
        if not self.is_enabled():
            return
        plan = self.planner.plan()
        for group in plan.groups:
            if not group.identical or group.canonical_spec is None:
                continue
            try:
                result = self.mutations.adopt(group.name)
                if isinstance(result, dict) and result.get("ok") is False:
                    continue
            except Exception as error:  # noqa: BLE001 — preserve the unmanaged entry for review
                record_auto_adopt(
                    self.journal,
                    family="mcp",
                    ref=group.name,
                    outcome="failed",
                    error_type=error.__class__.__name__,
                )
                continue
            record_auto_adopt(
                self.journal,
                family="mcp",
                ref=group.name,
                target_paths=(sighting.config_path for sighting in group.sightings if sighting.config_path),
            )


__all__ = ["McpAutoAdoptService", "ObservedConfigAutoAdoptService"]
