from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from harness_asset_manager.atomic_files import atomic_write_text


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
        return payload


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
    "write_skill_store_manifest",
]
