from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness_asset_manager.atomic_files import atomic_write_text, file_lock


class AssetArchiveStore:
    """Portable archive flags, keyed by family and stable asset reference."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _load_payload(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def load(self) -> set[str]:
        values = self._load_payload().get("archived")
        if not isinstance(values, list):
            return set()
        return {value for value in values if isinstance(value, str) and ":" in value}

    def is_archived(self, family: str, ref: str) -> bool:
        return f"{family}:{ref}" in self.load()

    def set_archived(self, family: str, ref: str, *, archived: bool) -> None:
        key = f"{family}:{ref}"
        with file_lock(self.path.with_suffix(".lock")):
            payload = self._load_payload()
            raw = payload.get("archived")
            values = {value for value in raw if isinstance(value, str)} if isinstance(raw, list) else set()
            if archived:
                values.add(key)
            else:
                values.discard(key)
            payload.setdefault("version", 1)
            payload["archived"] = sorted(values)
            atomic_write_text(self.path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
