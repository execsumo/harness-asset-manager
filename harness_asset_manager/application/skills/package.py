from __future__ import annotations

import hashlib
import os
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
    volatile: bool


@dataclass(frozen=True)
class _PackagePathEntry:
    relative_path: str
    path: Path
    kind: str
    link_stat: os.stat_result
    target_stat: os.stat_result | None = None
    link_target: str | None = None
    resolved_target: str | None = None


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
            signature = _package_metadata_signature(resolved_path)
            with self._condition:
                cached = self._entries.get(resolved_path)
                if (
                    generation == self._generation
                    and cached is not None
                    and cached.signature == signature
                    and not cached.contents.volatile
                ):
                    contents = cached.contents
                else:
                    contents = None

            if contents is None:
                contents, signature = _read_stable_package(
                    resolved_path,
                    initial_signature=signature,
                )

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
    fingerprint, relative_files, _volatile = _fingerprint_package_details(root)
    return fingerprint, relative_files


def _fingerprint_package_details(
    root: Path,
) -> tuple[str, tuple[str, ...], bool]:
    if not root.is_dir():
        raise SkillParseError(f"skill root does not exist: {root}")
    digest = hashlib.sha256()
    relative_files: list[str] = []
    volatile = False
    for entry in _enumerate_package_entries(root):
        relative_files.append(entry.relative_path)
        digest.update(entry.relative_path.encode("utf-8"))
        digest.update(b"\0")
        if entry.kind in {"file", "file-symlink"}:
            try:
                digest.update(entry.path.read_bytes())
            except OSError as error:
                raise SkillParseError(f"unable to read {entry.path}: {error}") from error
        else:
            digest.update(b"harnessam-topology\0")
            digest.update(entry.kind.encode("ascii"))
            digest.update(b"\0")
            if entry.link_target is not None:
                digest.update(entry.link_target.encode("utf-8", errors="surrogateescape"))
                digest.update(b"\0")
            if entry.kind == "special":
                digest.update(str(stat.S_IFMT(entry.link_stat.st_mode)).encode("ascii"))
                digest.update(b"\0")
                digest.update(str(entry.link_stat.st_rdev).encode("ascii"))
        digest.update(b"\0")
        volatile = volatile or entry.kind == "file-symlink"
    if "SKILL.md" not in relative_files:
        raise SkillParseError(f"missing SKILL.md in {root}")
    return digest.hexdigest(), tuple(relative_files), volatile


def _enumerate_package_entries(root: Path) -> tuple[_PackagePathEntry, ...]:
    """Enumerate package entries with lstat, never following directory links."""
    entries: list[_PackagePathEntry] = []

    def walk(directory: Path, prefix: str) -> None:
        try:
            with os.scandir(directory) as iterator:
                children = sorted(iterator, key=lambda child: child.name)
        except OSError as error:
            raise SkillParseError(f"unable to inspect {directory}: {error}") from error
        for child in children:
            if child.name == ".DS_Store":
                continue
            relative_path = f"{prefix}/{child.name}" if prefix else child.name
            path = Path(child.path)
            try:
                link_stat = child.stat(follow_symlinks=False)
            except OSError as error:
                raise SkillParseError(f"unable to inspect {path}: {error}") from error
            if stat.S_ISDIR(link_stat.st_mode):
                walk(path, relative_path)
                continue
            if stat.S_ISREG(link_stat.st_mode):
                entries.append(
                    _PackagePathEntry(
                        relative_path=relative_path,
                        path=path,
                        kind="file",
                        link_stat=link_stat,
                        target_stat=link_stat,
                    )
                )
                continue
            if stat.S_ISLNK(link_stat.st_mode):
                try:
                    link_target = os.readlink(path)
                except OSError as error:
                    raise SkillParseError(f"unable to read link {path}: {error}") from error
                try:
                    target_stat = child.stat(follow_symlinks=True)
                except OSError:
                    target_stat = None
                if target_stat is None:
                    kind = "broken-symlink"
                elif stat.S_ISREG(target_stat.st_mode):
                    kind = "file-symlink"
                elif stat.S_ISDIR(target_stat.st_mode):
                    kind = "directory-symlink"
                else:
                    kind = "special-symlink"
                try:
                    resolved_target = str(path.resolve(strict=False))
                except (OSError, RuntimeError):
                    resolved_target = None
                entries.append(
                    _PackagePathEntry(
                        relative_path=relative_path,
                        path=path,
                        kind=kind,
                        link_stat=link_stat,
                        target_stat=target_stat,
                        link_target=link_target,
                        resolved_target=resolved_target,
                    )
                )
                continue
            entries.append(
                _PackagePathEntry(
                    relative_path=relative_path,
                    path=path,
                    kind="special",
                    link_stat=link_stat,
                )
            )

    walk(root, "")
    return tuple(sorted(entries, key=lambda entry: entry.relative_path))


def _package_metadata_signature(root: Path) -> bytes:
    """Hash topology and per-file metadata without reading package contents."""
    if not root.is_dir():
        raise SkillParseError(f"skill root does not exist: {root}")
    digest = hashlib.sha256()
    relative_files: list[str] = []
    for entry in _enumerate_package_entries(root):
        relative_files.append(entry.relative_path)
        digest.update(entry.relative_path.encode("utf-8"))
        digest.update(b"\0")
        for value in (
            entry.link_stat.st_mode,
            entry.link_stat.st_size,
            entry.link_stat.st_mtime_ns,
            entry.link_stat.st_ctime_ns,
            entry.link_stat.st_dev,
            entry.link_stat.st_ino,
        ):
            digest.update(str(value).encode("ascii"))
            digest.update(b"\0")
        if entry.link_target is not None:
            digest.update(entry.link_target.encode("utf-8", errors="surrogateescape"))
            digest.update(b"\0")
        if entry.resolved_target is not None:
            digest.update(entry.resolved_target.encode("utf-8", errors="surrogateescape"))
            digest.update(b"\0")
        if entry.target_stat is not None and entry.kind != "file":
            for value in (
                entry.target_stat.st_mode,
                entry.target_stat.st_size,
                entry.target_stat.st_mtime_ns,
                entry.target_stat.st_ctime_ns,
                entry.target_stat.st_dev,
                entry.target_stat.st_ino,
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
        fingerprint, relative_files, volatile = _fingerprint_package_details(root)
        following_signature = _package_metadata_signature(root)
        if signature == following_signature:
            return (
                _PackageContents(
                    manifest=manifest,
                    relative_files=relative_files,
                    revision=fingerprint,
                    volatile=volatile,
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
