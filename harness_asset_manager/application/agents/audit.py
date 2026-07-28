from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence

from harness_asset_manager.atomic_files import atomic_write_text, file_lock

AuditAction = Literal["relinked", "adopted", "conflict_preserved", "refused"]
VALID_ACTIONS: set[str] = {"relinked", "adopted", "conflict_preserved", "refused"}


@dataclass(frozen=True)
class AuditEntry:
    at: float
    ref: str
    harness: str
    action: AuditAction
    detail: str

    def to_dict(self) -> dict[str, object]:
        return {
            "at": self.at,
            "ref": self.ref,
            "harness": self.harness,
            "action": self.action,
            "detail": self.detail,
        }


class AgentAuditLog:
    """Surfaces automatic binding repair decisions in the UI.

    Invariant 5 of plan-auto-adoption.md: silent repair is nearly as bad as silent breakage.
    This log is strictly a record, never an input to a decision.
    """

    def __init__(self, path: Path, limit: int = 200) -> None:
        self.path = path
        self.limit = limit

    @property
    def lock_path(self) -> Path:
        return self.path.with_suffix(".lock")

    def append(self, entries: Sequence[AuditEntry]) -> None:
        if not entries:
            return
        with file_lock(self.lock_path):
            existing = self.load()
            combined = existing + list(entries)
            if len(combined) > self.limit:
                combined = combined[-self.limit :]
            payload = {
                "version": 1,
                "entries": [entry.to_dict() for entry in combined],
            }
            atomic_write_text(self.path, json.dumps(payload, indent=2) + "\n")

    def load(self) -> list[AuditEntry]:
        if not self.path.is_file():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        if not isinstance(payload, dict):
            return []
        raw_entries = payload.get("entries")
        if not isinstance(raw_entries, list):
            return []
        entries: list[AuditEntry] = []
        for raw in raw_entries:
            parsed = _parse_audit_entry(raw)
            if parsed is not None:
                entries.append(parsed)
        return entries

    def recent(self) -> tuple[AuditEntry, ...]:
        """Return audit entries newest first. Total on all error paths."""
        try:
            return tuple(reversed(self.load()))
        except Exception:
            return ()


def _parse_audit_entry(raw: object) -> AuditEntry | None:
    if not isinstance(raw, dict):
        return None
    at = raw.get("at")
    ref = raw.get("ref")
    harness = raw.get("harness")
    action = raw.get("action")
    detail = raw.get("detail")
    if (
        not isinstance(at, (int, float))
        or isinstance(at, bool)
        or not isinstance(ref, str)
        or not isinstance(harness, str)
        or not isinstance(action, str)
        or action not in VALID_ACTIONS
        or not isinstance(detail, str)
    ):
        return None
    return AuditEntry(
        at=float(at),
        ref=ref,
        harness=harness,
        action=action,  # type: ignore[arg-type]
        detail=detail,
    )


__all__ = ["AgentAuditLog", "AuditAction", "AuditEntry"]
