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
    """Split a `SKILL.md` into its body and its ordered frontmatter entries.

    Entries are ``{key, value}`` pairs. A value containing a newline is a **verbatim
    block** — everything that followed the colon, indentation and all — and
    ``render_skill_document`` writes it back unchanged. That is what lets nested maps,
    lists, lists of maps, and literal (``|``) scalars survive an edit; before, they
    parsed as an empty scalar and their indented lines were dropped.

    Folded scalars (``>``, ``>-``) are the deliberate exception: they fold to a single
    line, because re-emitting one as a plain scalar is equivalent YAML and it keeps
    long descriptions editable as a single field.
    """
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
        inline = raw_value.strip()
        i += 1
        continuation, i = _read_indented_block(lines, i)

        if inline in (">", ">-"):
            # Folded: one logical line, indentation is not content.
            value = " ".join(part.strip() for part in continuation if part.strip())
        elif continuation:
            # Everything else that carries indented lines is structure — a map, a
            # list, or a literal scalar. Indentation is semantic, so keep it, and
            # keep the inline marker (`|`, `|-`) that says what the block is.
            value = "\n".join([raw_value.rstrip(), *continuation])
        else:
            value = _normalize_metadata_scalar(inline)
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
        if "\n" in value:
            # A verbatim block: `value` is everything that followed the colon,
            # already carrying its own indentation. Re-emitted untouched.
            lines.append(f"{key}:{value}")
        elif value == "":
            lines.append(f'{key}: ""')
        else:
            lines.append(f"{key}: {_quote_if_needed(value)}")
    lines.append("---")
    return "\n".join(lines) + "\n\n" + body.strip() + "\n"


def _read_indented_block(lines: list[str], start: int) -> tuple[list[str], int]:
    """Consume the indented lines belonging to the key that ends at ``start``.

    Returns them **unstripped** — for a map or a list the indentation is the
    structure, so stripping it is exactly the data loss this exists to prevent.
    """
    block: list[str] = []
    index = start
    while index < len(lines):
        line = lines[index]
        if line.strip() == "---":
            break
        if line and not line[0].isspace():
            break
        block.append(line)
        index += 1
    # Trailing blank lines belong to nothing; leaving them in would grow the block
    # by one line on every round trip.
    while block and not block[-1].strip():
        block.pop()
        index -= 1
    return block, index


def _normalize_metadata_scalar(value: str) -> str:
    """Unwrap a quoted scalar so the editor shows the value, not its quoting."""
    normalized = value.strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {"'", '"'}:
        inner = normalized[1:-1].strip()
        if normalized[0] == '"':
            return inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner.replace("''", "'")
    return normalized


def _quote_if_needed(value: str) -> str:
    """Re-quote a scalar that cannot be written plain.

    The parser unwraps quotes so the editor shows the value; writing it back plain
    is only safe when YAML would read it the same way. A description holding
    ``toolkit: paper discovery`` is the case that bites — unquoted, the second colon
    makes the line a nested mapping and the file stops parsing.

    Deliberately narrow: a value that merely *looks* like a flow collection
    (``[linux, macos]``) is left alone, because quoting it would turn a list into a
    string. Only outright-invalid plain scalars are quoted.
    """
    unsafe = (
        value != value.strip()
        or ": " in value
        or value.endswith(":")
        or " #" in value
        or value.startswith("#")
    )
    if not unsafe:
        return value
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


__all__ = [
    "parse_skill_document",
    "read_skill_document_and_metadata",
    "read_skill_document_markdown",
    "render_skill_document",
    "strip_frontmatter",
]
