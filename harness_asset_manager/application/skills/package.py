from __future__ import annotations

import hashlib
import stat
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from threading import Condition

from .identity import SkillRef, SourceDescriptor


class SkillParseError(ValueError):
    """Raised when a skill folder cannot be parsed safely."""


@dataclass(frozen=True)
class SkillManifest:
    declared_name: str
    description: str
    source_kind: str | None
    source_locator: str | None


@dataclass(frozen=True)
class SkillPackage:
    declared_name: str
    description: str
    root_path: Path
    resolved_path: Path
    relative_files: tuple[str, ...]
    revision: str
    source: SourceDescriptor

    @property
    def ref(self) -> SkillRef:
        return SkillRef(source=self.source, declared_name=self.declared_name)


@dataclass(frozen=True)
class _PackageContents:
    manifest: SkillManifest
    relative_files: tuple[str, ...]
    revision: str


@dataclass(frozen=True)
class _PackageCacheEntry:
    signature: bytes
    contents: _PackageContents
    validation_cycle: int


class SkillPackageCache:
    """Thread-safe parsed-package cache keyed by a package's resolved identity.

    A read-model snapshot allocates one validation cycle and shares it across the
    store and every harness adapter. Each distinct package tree is therefore
    inspected at most once per snapshot, including when several harness roots are
    symlinks to the same shared package. A new cycle re-stats every file in the
    tree, but unchanged packages avoid all content reads and manifest parsing.
    """

    def __init__(self, *, max_entries: int = 2048) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be positive")
        self.max_entries = max_entries
        self._entries: OrderedDict[Path, _PackageCacheEntry] = OrderedDict()
        self._condition = Condition()
        self._inflight: set[Path] = set()
        self._generation = 0
        self._next_validation_cycle = 0

    def new_validation_cycle(self) -> int:
        with self._condition:
            self._next_validation_cycle += 1
            return self._next_validation_cycle

    def parse(
        self,
        root: Path,
        *,
        default_source: SourceDescriptor,
        validation_cycle: int | None = None,
    ) -> SkillPackage:
        resolved_path = root.resolve(strict=False)

        with self._condition:
            while True:
                cached = self._entries.get(resolved_path)
                if (
                    validation_cycle is not None
                    and cached is not None
                    and cached.validation_cycle == validation_cycle
                ):
                    self._entries.move_to_end(resolved_path)
                    return _materialize_package(
                        cached.contents,
                        root=root,
                        resolved_path=resolved_path,
                        default_source=default_source,
                    )
                if resolved_path not in self._inflight:
                    self._inflight.add(resolved_path)
                    generation = self._generation
                    break
                self._condition.wait()

        try:
            signature = _package_metadata_signature(root)
            with self._condition:
                cached = self._entries.get(resolved_path)
                if (
                    generation == self._generation
                    and cached is not None
                    and cached.signature == signature
                ):
                    contents = cached.contents
                else:
                    contents = None

            if contents is None:
                contents, signature = _read_stable_package(root, initial_signature=signature)

            with self._condition:
                if generation == self._generation:
                    self._entries[resolved_path] = _PackageCacheEntry(
                        signature=signature,
                        contents=contents,
                        validation_cycle=(
                            validation_cycle if validation_cycle is not None else -1
                        ),
                    )
                    self._entries.move_to_end(resolved_path)
                    while len(self._entries) > self.max_entries:
                        self._entries.popitem(last=False)
        finally:
            with self._condition:
                self._inflight.discard(resolved_path)
                self._condition.notify_all()

        return _materialize_package(
            contents,
            root=root,
            resolved_path=resolved_path,
            default_source=default_source,
        )

    def invalidate(self) -> None:
        with self._condition:
            self._generation += 1
            self._entries.clear()
            self._condition.notify_all()


def find_skill_roots(root: Path) -> tuple[Path, ...]:
    if not root.exists() or not root.is_dir():
        return ()
    return tuple(sorted(path for path in root.iterdir() if path.is_dir() and (path / "SKILL.md").is_file()))


def fingerprint_package(root: Path) -> tuple[str, tuple[str, ...]]:
    if not root.is_dir():
        raise SkillParseError(f"skill root does not exist: {root}")
    digest = hashlib.sha256()
    relative_files: list[str] = []
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        if path.name == ".DS_Store":
            continue
        relative_path = path.relative_to(root).as_posix()
        relative_files.append(relative_path)
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    if "SKILL.md" not in relative_files:
        raise SkillParseError(f"missing SKILL.md in {root}")
    return digest.hexdigest(), tuple(relative_files)


def _package_metadata_signature(root: Path) -> bytes:
    """Hash topology and per-file metadata without reading package contents."""
    if not root.is_dir():
        raise SkillParseError(f"skill root does not exist: {root}")
    digest = hashlib.sha256()
    relative_files: list[str] = []
    for path in sorted(candidate for candidate in root.rglob("*") if candidate.is_file()):
        if path.name == ".DS_Store":
            continue
        relative_path = path.relative_to(root).as_posix()
        relative_files.append(relative_path)
        try:
            link_stat = path.lstat()
            target_stat = path.stat()
        except OSError as error:
            raise SkillParseError(f"unable to inspect {path}: {error}") from error
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        for value in (
            link_stat.st_mode,
            link_stat.st_size,
            link_stat.st_mtime_ns,
            link_stat.st_ctime_ns,
            link_stat.st_dev,
            link_stat.st_ino,
        ):
            digest.update(str(value).encode("ascii"))
            digest.update(b"\0")
        if stat.S_ISLNK(link_stat.st_mode):
            for value in (
                target_stat.st_mode,
                target_stat.st_size,
                target_stat.st_mtime_ns,
                target_stat.st_ctime_ns,
                target_stat.st_dev,
                target_stat.st_ino,
            ):
                digest.update(str(value).encode("ascii"))
                digest.update(b"\0")
    if "SKILL.md" not in relative_files:
        raise SkillParseError(f"missing SKILL.md in {root}")
    return digest.digest()


def _read_stable_package(
    root: Path,
    *,
    initial_signature: bytes,
) -> tuple[_PackageContents, bytes]:
    """Read a package whose metadata is stable across the content read."""
    signature = initial_signature
    for _attempt in range(3):
        skill_path = root / "SKILL.md"
        if not skill_path.is_file():
            raise SkillParseError(f"missing SKILL.md in {root}")
        try:
            content = skill_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise SkillParseError(f"unable to read {skill_path}: {error}") from error
        manifest = parse_skill_manifest_text(content)
        fingerprint, relative_files = fingerprint_package(root)
        following_signature = _package_metadata_signature(root)
        if signature == following_signature:
            return (
                _PackageContents(
                    manifest=manifest,
                    relative_files=relative_files,
                    revision=fingerprint,
                ),
                following_signature,
            )
        signature = following_signature
    raise SkillParseError(f"skill package changed while it was being read: {root}")


def parse_skill_package(root: Path, *, default_source: SourceDescriptor) -> SkillPackage:
    skill_path = root / "SKILL.md"
    if not skill_path.is_file():
        raise SkillParseError(f"missing SKILL.md in {root}")
    content = skill_path.read_text(encoding="utf-8")
    manifest = parse_skill_manifest_text(content)
    fingerprint, relative_files = fingerprint_package(root)
    source = _resolve_source(
        {
            "source_kind": manifest.source_kind or "",
            "source_locator": manifest.source_locator or "",
        },
        default_source=default_source,
    )
    return SkillPackage(
        declared_name=manifest.declared_name,
        description=manifest.description,
        root_path=root,
        resolved_path=root.resolve(),
        relative_files=relative_files,
        revision=fingerprint,
        source=source,
    )


def _materialize_package(
    contents: _PackageContents,
    *,
    root: Path,
    resolved_path: Path,
    default_source: SourceDescriptor,
) -> SkillPackage:
    source = _resolve_source(
        {
            "source_kind": contents.manifest.source_kind or "",
            "source_locator": contents.manifest.source_locator or "",
        },
        default_source=default_source,
    )
    return SkillPackage(
        declared_name=contents.manifest.declared_name,
        description=contents.manifest.description,
        root_path=root,
        resolved_path=resolved_path,
        relative_files=contents.relative_files,
        revision=contents.revision,
        source=source,
    )


def parse_skill_manifest_text(document: str) -> SkillManifest:
    metadata = parse_skill_frontmatter_metadata(document)
    return SkillManifest(
        declared_name=_extract_declared_name(document, metadata),
        description=_normalize_metadata_scalar(metadata.get("description", "")),
        source_kind=_optional_metadata_value(metadata, "source_kind"),
        source_locator=_optional_metadata_value(metadata, "source_locator"),
    )


def parse_skill_frontmatter_metadata(document: str) -> dict[str, str]:
    return _parse_frontmatter(document)


def _resolve_source(metadata: dict[str, str], *, default_source: SourceDescriptor) -> SourceDescriptor:
    source_kind = metadata.get("source_kind", "").strip()
    source_locator = metadata.get("source_locator", "").strip()
    if source_kind and source_locator:
        return SourceDescriptor(kind=source_kind, locator=source_locator)
    return default_source


def _extract_declared_name(document: str, metadata: dict[str, str]) -> str:
    if metadata.get("name", "").strip():
        return _normalize_metadata_scalar(metadata["name"])
    for raw_line in document.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    raise SkillParseError("unable to determine declared skill name")


def _parse_frontmatter(document: str) -> dict[str, str]:
    lines = document.splitlines()
    metadata: dict[str, str] = {}
    if lines[:1] != ["---"]:
        return metadata
    i = 1
    while i < len(lines):
        raw_line = lines[i]
        if raw_line.strip() == "---":
            break
        if ":" not in raw_line:
            i += 1
            continue
        key, value = raw_line.split(":", 1)
        value = value.strip()
        # Handle YAML block scalars (>-, >, |, |-)
        if value in (">-", ">", "|", "|-"):
            join_char = " " if value.startswith(">") else "\n"
            continuation: list[str] = []
            i += 1
            while i < len(lines):
                cont_line = lines[i]
                if cont_line.strip() == "---":
                    break
                if cont_line and not cont_line[0].isspace():
                    break
                continuation.append(cont_line.strip())
                i += 1
            value = join_char.join(part for part in continuation if part)
        else:
            value = _normalize_metadata_scalar(value)
            i += 1
        metadata[key.strip()] = value
    return metadata


def _optional_metadata_value(metadata: dict[str, str], key: str) -> str | None:
    value = _normalize_metadata_scalar(metadata.get(key, ""))
    return value or None


def _normalize_metadata_scalar(value: str) -> str:
    normalized = value.strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {"'", '"'}:
        return normalized[1:-1].strip()
    return normalized
