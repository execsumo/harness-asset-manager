from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path

from harness_asset_manager.atomic_files import atomic_write_text


def normalize_enabled_harnesses(value: object) -> tuple[str, ...]:
    """Coerce recorded binding intent into a sorted, de-duplicated tuple.

    Total by design, matching every other read path in the store: a malformed or
    partially-corrupt value degrades to "no recorded intent" (or to just the usable
    entries) rather than raising. Losing intent costs the user a re-enable click;
    raising here would make an unreadable manifest take down the whole inventory.
    """
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(sorted({item for item in value if isinstance(item, str) and item}))


@dataclass(frozen=True)
class SkillStoreEntry:
    package_dir: str
    declared_name: str
    source_kind: str
    source_locator: str
    revision: str
    source_ref: str | None = None
    source_path: str | None = None
    origin_harness: str | None = None
    # Which harnesses this package was last bound into, as *recorded intent*.
    #
    # Deliberately not a source of truth for display: ``linked_harnesses()`` keeps
    # deriving enablement from the filesystem, because that is the only thing that
    # tells you what a harness will actually read right now. This records the one
    # fact the filesystem cannot carry across machines — that a human once chose
    # this package for this harness — so a synced store can *propose* rebuilding
    # those bindings on a device whose disk has never had them.
    #
    # Sorted and de-duplicated on both read and write so the manifest stays stable
    # under git (a dotfiled store is diffed by humans).
    enabled_harnesses: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "packageDir": self.package_dir,
            "declaredName": self.declared_name,
            "sourceKind": self.source_kind,
            "sourceLocator": self.source_locator,
            "revision": self.revision,
        }
        if self.source_ref is not None:
            payload["sourceRef"] = self.source_ref
        if self.source_path is not None:
            payload["sourcePath"] = self.source_path
        if self.origin_harness is not None:
            payload["originHarness"] = self.origin_harness
        # Omitted when empty so stores that never bind a package keep byte-identical
        # manifests to the pre-intent format.
        if self.enabled_harnesses:
            payload["enabledHarnesses"] = list(self.enabled_harnesses)
        return payload

    def with_binding(self, harness: str, *, bound: bool) -> SkillStoreEntry:
        """Return a copy with ``harness`` added to / removed from recorded intent.

        Returns ``self`` unchanged when the intent already matches, so callers can
        skip a manifest write on a no-op toggle.
        """
        updated = normalize_enabled_harnesses(
            [h for h in self.enabled_harnesses if h != harness] + ([harness] if bound else [])
        )
        if updated == self.enabled_harnesses:
            return self
        return replace(self, enabled_harnesses=updated)


@dataclass(frozen=True)
class SkillStoreManifest:
    entries: tuple[SkillStoreEntry, ...]

    def to_dict(self) -> dict[str, object]:
        return {"entries": [entry.to_dict() for entry in self.entries]}


def load_skill_store_manifest(path: Path) -> SkillStoreManifest:
    if not path.is_file():
        return SkillStoreManifest(entries=())
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return SkillStoreManifest(entries=())
    if not isinstance(payload, dict):
        return SkillStoreManifest(entries=())
    raw_entries = payload.get("entries", [])
    if not isinstance(raw_entries, list):
        return SkillStoreManifest(entries=())
    entries: list[SkillStoreEntry] = []
    for item in raw_entries:
        if not isinstance(item, dict):
            continue
        try:
            entries.append(
                SkillStoreEntry(
                    package_dir=str(item["packageDir"]),
                    declared_name=str(item["declaredName"]),
                    source_kind=str(item["sourceKind"]),
                    source_locator=str(item["sourceLocator"]),
                    revision=str(item["revision"]),
                    source_ref=item.get("sourceRef") if isinstance(item.get("sourceRef"), str) else None,
                    source_path=item.get("sourcePath") if isinstance(item.get("sourcePath"), str) else None,
                    origin_harness=item.get("originHarness") if isinstance(item.get("originHarness"), str) else None,
                    enabled_harnesses=normalize_enabled_harnesses(item.get("enabledHarnesses")),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return SkillStoreManifest(entries=tuple(entries))


def write_skill_store_manifest(path: Path, manifest: SkillStoreManifest) -> None:
    atomic_write_text(
        path,
        json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2) + "\n",
    )


__all__ = [
    "SkillStoreEntry",
    "SkillStoreManifest",
    "load_skill_store_manifest",
    "normalize_enabled_harnesses",
    "write_skill_store_manifest",
]
