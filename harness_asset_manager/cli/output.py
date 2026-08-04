"""Rendering helpers shared by the asset commands.

Every asset command speaks two dialects: a plain-text table for a human at a
terminal, and ``--json`` for a script. The JSON dialect is the same payload the
HTTP API returns for the equivalent route, so a script that outgrows the CLI can
move to the API without relearning any shapes.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterable, Sequence
from typing import Any

# Binding/cell states come from four different inventories (skills, MCP, hooks and
# permissions, agents) that name the same handful of ideas slightly differently. One
# glyph table keeps the matrices readable side by side.
CELL_GLYPHS: dict[str, str] = {
    "enabled": "[x]",
    "managed": "[x]",
    "disabled": "[ ]",
    "missing": "[ ]",
    "empty": "[ ]",
    "found": "[~]",
    "unmanaged": "[~]",
    "drifted": "[!]",
    "unsupported": "[-]",
}

LEGEND = "[x] managed here  [ ] not present  [~] present but unmanaged  [!] drifted  [-] unsupported"


def glyph(state: str) -> str:
    return CELL_GLYPHS.get(state, f"[{state[:1]}]")


def print_json(payload: Any) -> None:
    """Write ``payload`` as indented JSON. ``Path`` and friends degrade to ``str``."""
    json.dump(payload, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")


def truncate(value: object, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(limit - 1, 1)] + "…"


def render_table(headers: Sequence[str], rows: Iterable[Sequence[str]]) -> str:
    materialized = [[str(cell) for cell in row] for row in rows]
    if not materialized:
        return ""
    widths = [len(header) for header in headers]
    for row in materialized:
        for index, cell in enumerate(row):
            if index < len(widths):
                widths[index] = max(widths[index], len(cell))
    lines = ["  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)).rstrip()]
    lines.append("  ".join("-" * width for width in widths).rstrip())
    for row in materialized:
        lines.append("  ".join(cell.ljust(widths[index]) for index, cell in enumerate(row)).rstrip())
    return "\n".join(lines)


def print_table(headers: Sequence[str], rows: Iterable[Sequence[str]], *, empty: str = "(none)") -> None:
    table = render_table(headers, rows)
    print(table if table else empty)


def print_matrix(
    headers: Sequence[str],
    rows: Iterable[Sequence[str]],
    *,
    empty: str = "(none)",
    legend: bool = True,
) -> None:
    """A table whose trailing columns are harness cells, followed by the glyph legend."""
    table = render_table(headers, rows)
    if not table:
        print(empty)
        return
    print(table)
    if legend:
        print()
        print(LEGEND)


def print_fields(fields: Sequence[tuple[str, object]]) -> None:
    """Aligned ``key: value`` block used by the ``show`` commands."""
    visible = [(label, value) for label, value in fields if value not in (None, "")]
    if not visible:
        return
    width = max(len(label) for label, _ in visible)
    for label, value in visible:
        print(f"{label.ljust(width)}  {value}")


def print_result(payload: dict[str, object], *, message: str) -> int:
    """Report a mutation whose payload may carry per-harness failures.

    Returns the process exit code: partial failure is a failure, because a script
    that fans a change out to four harnesses needs to hear about the one that did
    not take.
    """
    failed = payload.get("failed") or []
    succeeded = payload.get("succeeded") or []
    if succeeded:
        print(f"{message} ({', '.join(str(item) for item in succeeded)})")
    else:
        print(message)
    if not failed:
        return 0
    for failure in failed:
        harness = failure.get("harness") if isinstance(failure, dict) else None
        error = failure.get("error") if isinstance(failure, dict) else failure
        print(f"error: {harness}: {error}", file=sys.stderr)
    return 1


__all__ = [
    "CELL_GLYPHS",
    "LEGEND",
    "glyph",
    "print_fields",
    "print_json",
    "print_matrix",
    "print_result",
    "print_table",
    "render_table",
    "truncate",
]
