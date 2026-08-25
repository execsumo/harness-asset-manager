from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from .identity import SourceDescriptor, stable_id
from .observations import SkillsHarnessScan, SkillStoreScan

EntryKind = Literal["managed", "unmanaged"]


@dataclass(frozen=True)
class InventoryColumn:
    harness: str
    label: str
    logo_key: str | None
    installed: bool


@dataclass(frozen=True)
class InventorySighting:
    kind: Literal["shared", "harness"]
    harness: str | None
    label: str
    scope: str | None
    path: Path | None
    revision: str | None
    source: SourceDescriptor
    detail: str = ""


@dataclass
class InventoryEntry:
    skill_ref: str
    name: str
    description: str
    kind: EntryKind
    source: SourceDescriptor
    current_revision: str | None = None
    recorded_revision: str | None = None
    source_ref: str | None = None
    source_path: str | None = None
    package_dir: str | None = None
    package_path: Path | None = None
    origin_harness: str | None = None
    # Every file in the package, relative to its root, as the parser enumerated it.
    # A skill is a folder, not just SKILL.md, and the detail view has to be able to
    # say what else is in there — scripts especially.
    files: tuple[str, ...] = ()
    sightings: list[InventorySighting] = field(default_factory=list)

    def add_sighting(self, sighting: InventorySighting) -> None:
        self.sightings.append(sighting)

    def detail_sightings(self) -> list[InventorySighting]:
        order = {"shared": 0, "harness": 1}
        return sorted(
            self.sightings,
            key=lambda item: (
                order.get(item.kind, 99),
                item.harness or "",
                item.scope or "",
                item.label,
                str(item.path) if item.path is not None else "",
            ),
        )

    def linked_harnesses(self) -> set[str]:
        return {
            sighting.harness
            for sighting in self.sightings
            if sighting.kind == "harness" and sighting.harness is not None and sighting.scope == "canonical"
        }


class SkillInventory:
    def __init__(
        self,
        *,
        columns: tuple[InventoryColumn, ...],
        harness_scans: tuple[SkillsHarnessScan, ...],
        store_issues: tuple[str, ...],
        entries: tuple[InventoryEntry, ...],
    ) -> None:
        self.columns = columns
        self.harness_scans = harness_scans
        self.store_issues = store_issues
        self.entries = entries
        self._by_ref = {entry.skill_ref: entry for entry in entries}

    @classmethod
    def from_snapshot(
        cls,
        *,
        store_scan: SkillStoreScan,
        harness_scans: tuple[SkillsHarnessScan, ...],
    ) -> "SkillInventory":
        from .policy import sort_entries

        columns = tuple(
            InventoryColumn(
                harness=scan.harness,
                label=scan.label,
                logo_key=scan.logo_key,
                installed=scan.installed,
            )
            for scan in harness_scans
        )
        entries: list[InventoryEntry] = []
        shared_path_index: dict[Path, InventoryEntry] = {}
        shared_match_index: dict[str, InventoryEntry] = {}
        hermes_local_match_index: dict[tuple[str, str], InventoryEntry] = {}
        excluded_hermes_names = _excluded_hermes_names(harness_scans)

        for store_package in store_scan.packages:
            package = store_package.package
            if _is_excluded_hermes_store_package(
                name=package.declared_name,
                package_dir=package.root_path.name,
                origin_harness=store_package.origin_harness,
                excluded_hermes_names=excluded_hermes_names,
            ):
                continue
            entry = InventoryEntry(
                skill_ref=f"shared:{package.root_path.name}",
                name=package.declared_name,
                description=package.description,
                kind="managed",
                source=package.source,
                current_revision=package.revision,
                recorded_revision=store_package.recorded_revision,
                source_ref=store_package.recorded_source_ref,
                source_path=store_package.recorded_source_path,
                package_dir=package.root_path.name,
                package_path=package.root_path,
                origin_harness=store_package.origin_harness,
                files=package.relative_files,
            )
            entry.add_sighting(
                InventorySighting(
                    kind="shared",
                    harness=None,
                    label="Shared Store",
                    scope=None,
                    path=package.root_path,
                    revision=package.revision,
                    source=package.source,
                )
            )
            entries.append(entry)
            shared_path_index[package.resolved_path] = entry
            shared_match_index[_managed_entry_key(entry)] = entry
            if store_package.origin_harness == "hermes":
                hermes_local_match_index[_hermes_local_match_key(entry)] = entry

        unmanaged_entries: dict[str, InventoryEntry] = {}

        for scan in harness_scans:
            for observation in scan.skills:
                shared_entry = shared_path_index.get(observation.package.resolved_path)
                sighting = InventorySighting(
                    kind="harness",
                    harness=observation.harness,
                    label=observation.label,
                    scope=observation.scope,
                    path=observation.package.root_path,
                    revision=observation.package.revision,
                    source=observation.package.source,
                )
                if shared_entry is not None:
                    shared_entry.add_sighting(sighting)
                    continue
                shared_match = shared_match_index.get(_observation_match_key(observation.package))
                if (
                    shared_match is None
                    and scan.harness == "hermes"
                    and observation.package.source.kind == "harness-local"
                ):
                    shared_match = hermes_local_match_index.get(
                        _hermes_local_observation_match_key(observation.package)
                    )
                if shared_match is not None:
                    shared_match.add_sighting(sighting)
                    continue

                key = _unmanaged_entry_key(
                    observation.package.declared_name,
                    observation.package.source,
                    observation.package.revision,
                )
                entry = unmanaged_entries.get(key)
                if entry is None:
                    entry = InventoryEntry(
                        skill_ref=f"unmanaged:{key}",
                        name=observation.package.declared_name,
                        description=observation.package.description,
                        kind="unmanaged",
                        source=observation.package.source,
                        current_revision=observation.package.revision,
                        files=observation.package.relative_files,
                    )
                    unmanaged_entries[key] = entry
                entry.add_sighting(sighting)

        entries.extend(unmanaged_entries.values())
        sort_entries(entries)
        return cls(
            columns=columns,
            harness_scans=harness_scans,
            store_issues=store_scan.issues,
            entries=tuple(entries),
        )

    def find(self, skill_ref: str) -> InventoryEntry | None:
        return self._by_ref.get(skill_ref)

    def entries_by_kind(self, kind: EntryKind) -> tuple[InventoryEntry, ...]:
        return tuple(entry for entry in self.entries if entry.kind == kind)


def _excluded_hermes_names(harness_scans: tuple[SkillsHarnessScan, ...]) -> set[str]:
    names: set[str] = set()
    for scan in harness_scans:
        if scan.harness == "hermes":
            names.update(scan.excluded_skill_names)
    return names


def _is_excluded_hermes_store_package(
    *,
    name: str,
    package_dir: str,
    origin_harness: str | None,
    excluded_hermes_names: set[str],
) -> bool:
    if origin_harness != "hermes":
        return False
    # A manifest entry records a package that is already managed by the shared
    # store, even when its originating Hermes installation is remote or absent
    # on this machine. Only explicitly identified Hermes-owned packages should
    # be hidden from the shared inventory.
    return name in excluded_hermes_names or package_dir in excluded_hermes_names


def _unmanaged_entry_key(declared_name: str, source: SourceDescriptor, revision: str) -> str:
    if source.is_source_backed:
        return stable_id("unmanaged", source.kind, source.locator, declared_name, revision)
    return stable_id("unmanaged", declared_name, revision)


def _managed_entry_key(entry: InventoryEntry) -> str:
    if entry.source.kind == "centralized":
        return stable_id("managed-centralized", entry.name, entry.current_revision or "")
    return stable_id("managed", entry.source.kind, entry.source.locator, entry.name, entry.current_revision or "")


def _observation_match_key(package) -> str:
    if package.source.is_source_backed:
        return stable_id("managed", package.source.kind, package.source.locator, package.declared_name, package.revision)
    return stable_id("managed-centralized", package.declared_name, package.revision)


def _hermes_local_match_key(entry: InventoryEntry) -> tuple[str, str]:
    return (entry.name.casefold(), (entry.package_dir or "").casefold())


def _hermes_local_observation_match_key(package) -> tuple[str, str]:
    return (package.declared_name.casefold(), package.root_path.name.casefold())
