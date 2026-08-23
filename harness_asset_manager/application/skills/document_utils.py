from __future__ import annotations

from pathlib import Path
from typing import Mapping


def read_skill_document_markdown(package_root: Path | None) -> str | None:
    body, _ = read_skill_document_and_metadata(package_root)
    return body


def read_skill_document_and_metadata(package_root: Path | None) -> tuple[str | None, list[dict[str, str]]]:
    if package_root is None:
        return None, []

    skill_path = package_root / "SKILL.md"
    if not skill_path.is_file():
        return None, []

    document = skill_path.read_text(encoding="utf-8").strip()
    if not document:
        return None, []
    return parse_skill_document(document)


def parse_skill_document(document: str) -> tuple[str | None, list[dict[str, str]]]:
    lines = document.splitlines()
    if lines[:1] != ["---"]:
        return (document.strip() or None), []

    metadata: list[dict[str, str]] = []
    body_start_index: int | None = None
    i = 1
    while i < len(lines):
        raw_line = lines[i]
        if raw_line.strip() == "---":
            body_start_index = i + 1
            break
        if ":" not in raw_line:
            i += 1
            continue
        key, raw_value = raw_line.split(":", 1)
        value = raw_value.strip()
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
        metadata.append({"key": key.strip(), "value": value})

    if body_start_index is not None:
        body = "\n".join(lines[body_start_index:]).strip() or None
    else:
        body = document.strip() or None

    return body, metadata


def strip_frontmatter(document: str) -> str | None:
    body, _ = parse_skill_document(document)
    return body


def render_skill_document(
    *,
    body: str,
    metadata: list[dict[str, str]] | list[tuple[str, str]] | Mapping[str, str] | None = None,
) -> str:
    metadata_entries: list[tuple[str, str]] = []
    if metadata is not None:
        if isinstance(metadata, list):
            for entry in metadata:
                if isinstance(entry, dict):
                    k = str(entry.get("key", "")).strip()
                    v = str(entry.get("value", ""))
                    if k:
                        metadata_entries.append((k, v))
                elif isinstance(entry, (tuple, list)) and len(entry) == 2:
                    k = str(entry[0]).strip()
                    v = str(entry[1])
                    if k:
                        metadata_entries.append((k, v))
        elif isinstance(metadata, Mapping):
            for k, v in metadata.items():
                if str(k).strip():
                    metadata_entries.append((str(k).strip(), str(v)))

    if not metadata_entries:
        return body.strip() + "\n" if body.strip() else ""

    lines = ["---"]
    for key, value in metadata_entries:
        if value == "":
            lines.append(f'{key}: ""')
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines) + "\n\n" + body.strip() + "\n"


def _normalize_metadata_scalar(value: str) -> str:
    normalized = value.strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {"'", '"'}:
        return normalized[1:-1].strip()
    return normalized


__all__ = [
    "parse_skill_document",
    "read_skill_document_and_metadata",
    "read_skill_document_markdown",
    "render_skill_document",
    "strip_frontmatter",
]
