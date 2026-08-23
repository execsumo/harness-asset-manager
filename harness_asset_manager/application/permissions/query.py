from __future__ import annotations

import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

from harness_asset_manager.errors import MutationError

from .contracts import (
    PermissionHarnessScan,
    PermissionInventory,
    PermissionInventoryIssue,
)
from .inventory import build_inventory
from .managed_state import entry_payload, inventory_payload
from .read_models import PermissionsReadModelService

if TYPE_CHECKING:
    from harness_asset_manager.application.asset_tags.service import AssetTagService


class PermissionsQueryService:
    """Read-side service exposing canonical permissions config and inventory views."""

    def __init__(
        self,
        read_models: PermissionsReadModelService,
        reconcile: Callable[[], object] | None = None,
        *,
        asset_tags: AssetTagService | None = None,
    ) -> None:
        self.read_models = read_models
        self._reconcile = reconcile
        self._asset_tags = asset_tags
        # Reentrancy guard, per thread (mirrors SkillsQueryService). Reconcile does
        # not currently read back through this service, but the wiring is identical
        # to the slash-commands family where that assumption broke; keep the
        # invariant structural. Must be thread-local: sync API endpoints run in a
        # threadpool over one shared service instance.
        self._reconcile_state = threading.local()

    def set_reconcile(self, reconcile: Callable[[], object] | None) -> None:
        self._reconcile = reconcile

    def _reconcile_once(self) -> None:
        if self._reconcile is None or getattr(self._reconcile_state, "active", False):
            return
        self._reconcile_state.active = True
        try:
            self._reconcile()
        finally:
            self._reconcile_state.active = False

    def _active_scans(self, snapshot) -> tuple[PermissionHarnessScan, ...]:
        return tuple(
            scan for scan in self.read_models.visible_scans(snapshot)
            if scan.installed or scan.config_present
        )

    def list_permissions(self) -> dict[str, object]:
        self._reconcile_once()
        snapshot = self.read_models.snapshot()
        active_scans = self._active_scans(snapshot)
        inventory = self._inventory(active_scans)
        return inventory_payload(
            inventory,
            active_scans,
        )

    def get_permission(self, id: str) -> dict[str, object]:
        self._reconcile_once()
        snapshot = self.read_models.snapshot()
        active_scans = self._active_scans(snapshot)
        inventory = self._inventory(active_scans)
        for entry in inventory.entries:
            if entry.id == id:
                return entry_payload(
                    entry,
                    active_scans,
                )
        raise MutationError(f"unknown permission: {id}", status=404)

    def _inventory(self, scans: tuple[PermissionHarnessScan, ...]) -> PermissionInventory:
        issues = [
            PermissionInventoryIssue(name=issue.name, reason=issue.reason)
            for issue in self.read_models.store.manifest_issues()
        ]
        issues.extend(
            PermissionInventoryIssue(name=f"{scan.label} config", reason=scan.scan_issue)
            for scan in scans
            if scan.scan_issue
        )
        tags_by_ref = (
            self._asset_tags.get_tags_for_family("permissions")
            if self._asset_tags is not None
            else {}
        )
        return build_inventory(
            managed_permissions=self.read_models.store.list_managed(),
            specs=self.read_models.store.list_managed(),
            scans=scans,
            issues=issues,
            tags_by_ref=tags_by_ref,
        )


__all__ = ["PermissionsQueryService"]
