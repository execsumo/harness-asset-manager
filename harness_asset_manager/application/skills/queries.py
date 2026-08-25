from __future__ import annotations

import threading
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Callable, Literal

from harness_asset_manager.errors import MutationError
from harness_asset_manager.sources import (
    github_folder_url,
    github_repo_from_locator,
    github_repo_url,
)

from .document_utils import read_skill_document_and_metadata
from .inventory import InventoryEntry, SkillInventory
from .package import fingerprint_package
from .policy import can_stop_managing, can_update, has_local_changes
from .presenters import skill_detail_payload, skills_page_payload, source_status_payload
from .read_models import SkillsReadModelService
from .source_fetch import SourceFetchService

if TYPE_CHECKING:
    from harness_asset_manager.application.asset_tags import AssetTagService


class SkillsQueryService:
    def __init__(
        self,
        read_models: SkillsReadModelService,
        source_fetcher: SourceFetchService,
        asset_tags: AssetTagService | None = None,
        reconcile: Callable[[], object] | None = None,
    ) -> None:
        self.read_models = read_models
        self.source_fetcher = source_fetcher
        self.asset_tags = asset_tags
        self._reconcile = reconcile
        # Reentrancy guard, per thread. A plain instance flag would let a concurrent
        # reader see another thread's in-flight reconcile and skip its own, returning a
        # snapshot taken mid-adoption. Sync API endpoints run in a threadpool over one
        # shared service instance, so that is a live path, not a theoretical one.
        self._reconcile_state = threading.local()

    def set_reconcile(self, reconcile: Callable[[], object] | None) -> None:
        self._reconcile = reconcile

    def health(self) -> dict[str, object]:
        snapshot = self.read_models.snapshot()
        return {
            "ok": True,
            "app": "harness-asset-manager",
            "readOnly": False,
            "harnessCount": len(snapshot.harness_scans),
        }

    def list_skills(self) -> dict[str, object]:
        all_tags = self.asset_tags.get_tags_for_family("skills") if self.asset_tags is not None else {}
        return skills_page_payload(self.inventory(), tags=all_tags)

    def get_skill_detail(self, skill_ref: str) -> dict[str, object] | None:
        inventory = self.inventory()
        entry = inventory.find(skill_ref)
        if entry is None:
            return None
        package_root = self.resolve_detail_package_root(entry)
        document_markdown, metadata = read_skill_document_and_metadata(package_root)
        tags = self.asset_tags.get_tags("skills", entry.skill_ref) if self.asset_tags is not None else []
        return skill_detail_payload(
            entry,
            columns=inventory.columns,
            document_markdown=document_markdown,
            metadata=metadata,
            source_links=self.build_source_links(entry),
            tags=tags,
        )

    def get_skill_source_status(self, skill_ref: str) -> dict[str, object] | None:
        entry = self.inventory().find(skill_ref)
        if entry is None:
            return None
        return source_status_payload(self.resolve_update_status(entry))

    def inventory(self) -> SkillInventory:
        """Repair first, then report -- the reconcile pass here can auto-adopt, i.e. write.

        Callers that only need to read must use ``_inventory_snapshot`` (or
        ``managed_skill_names``) instead, so a read cannot mutate the store.
        """
        if self._reconcile is not None and not getattr(self._reconcile_state, "active", False):
            self._reconcile_state.active = True
            try:
                self._reconcile()
            finally:
                self._reconcile_state.active = False
        return self._inventory_snapshot()

    def _inventory_snapshot(self) -> SkillInventory:
        """The matrix as it stands, with no repair pass. Never writes."""
        snapshot = self.read_models.snapshot()
        active_scans = tuple(
            scan for scan in self.read_models.visible_scans(snapshot)
            if scan.installed
        )
        return SkillInventory.from_snapshot(
            store_scan=snapshot.store_scan,
            harness_scans=active_scans,
        )

    def managed_skill_names(self) -> dict[str, str]:
        """Package dir -> display name for every managed skill, without reconciling.

        The agents matrix resolves its skill chips through this. Going via
        ``inventory()`` made a plain ``GET /api/agents`` able to auto-adopt skills;
        going via the store scan directly would resolve names for packages the
        inventory deliberately hides (Hermes-owned ones), so the read-only
        snapshot -- one declaration of what "managed" means -- is the seam.
        """
        return {
            entry.package_dir: entry.name
            for entry in self._inventory_snapshot().entries
            if entry.kind == "managed" and entry.package_dir is not None
        }

    def require_entry(self, skill_ref: str) -> InventoryEntry:
        entry = self.inventory().find(skill_ref)
        if entry is None:
            raise MutationError(
                f"unknown skill ref: {skill_ref}",
                status=404,
                code="skill_not_found",
            )
        return entry

    def check_for_update(self, entry: InventoryEntry) -> bool | None:
        if not can_update(entry) or entry.current_revision is None:
            return None
        with TemporaryDirectory(prefix="skill-check-") as work_dir:
            try:
                skill_path = self.source_fetcher.fetch(
                    source_kind=entry.source.kind,
                    source_locator=entry.source.locator,
                    work_dir=Path(work_dir),
                )
            except MutationError:
                return None
            fetched_revision, _ = fingerprint_package(skill_path)
            return fetched_revision != entry.current_revision

    def resolve_detail_package_root(self, entry: InventoryEntry) -> Path | None:
        if entry.package_path is not None and (entry.package_path / "SKILL.md").is_file():
            return entry.package_path

        for sighting in entry.detail_sightings():
            if sighting.path is not None and (sighting.path / "SKILL.md").is_file():
                return sighting.path
        return None

    def build_source_links(self, entry: InventoryEntry) -> dict[str, str | None] | None:
        if entry.source.kind != "github":
            return None

        repo = github_repo_from_locator(entry.source.locator)
        if repo is None:
            return None

        return {
            "repoLabel": repo,
            "repoUrl": github_repo_url(repo),
            "folderUrl": self._github_folder_url(entry, repo),
        }

    def _github_folder_url(self, entry: InventoryEntry, repo: str) -> str | None:
        if entry.source_ref is not None and entry.source_path is not None:
            return github_folder_url(repo, ref=entry.source_ref, relative_path=entry.source_path)
        if entry.source.locator.removeprefix("github:").count("/") < 2:
            return None
        with TemporaryDirectory(prefix="skill-source-links-") as work_dir:
            try:
                fetched = self.source_fetcher.fetch_package(
                    source_kind=entry.source.kind,
                    source_locator=entry.source.locator,
                    work_dir=Path(work_dir),
                )
            except MutationError:
                return None
        return github_folder_url(repo, ref=fetched.source_ref, relative_path=fetched.source_path)

    def resolve_update_status(
        self,
        entry: InventoryEntry,
    ) -> Literal["update_available", "no_update_available", "no_source_available", "local_changes_detected"] | None:
        if entry.kind != "managed":
            return None
        if has_local_changes(entry):
            return "local_changes_detected"
        if not can_update(entry):
            return "no_source_available"
        if self.check_for_update(entry):
            return "update_available"
        return "no_update_available"

    def can_stop_managing(self, entry: InventoryEntry) -> bool:
        return can_stop_managing(entry)

    def get_skill_path(self, skill_ref: str) -> Path | None:
        entry = self.inventory().find(skill_ref)
        if entry is None:
            return None
        return self.resolve_detail_package_root(entry)
