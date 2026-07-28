from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from .atomic_files import atomic_write_text, file_lock


def load_settings_document(path: Path) -> dict[str, object]:
    """The whole settings file, or an empty document if it is absent or unusable.

    Total by design: settings are a preference file, and a malformed one must fall
    back to defaults rather than take the app down.
    """
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def update_settings_document(
    path: Path, mutate: Callable[[dict[str, object]], None]
) -> dict[str, object]:
    """Read-modify-write the settings file, **preserving keys we do not own.**

    Every store that writes settings.json shares this, because they share the file:
    a store that serialises only its own keys silently deletes every other store's.
    Same lock path for all of them, so the read-modify-write is serialised.
    """
    with file_lock(settings_lock_path(path)):
        document = load_settings_document(path)
        mutate(document)
        atomic_write_text(path, json.dumps(document, indent=2, sort_keys=True) + "\n")
        return document


def settings_lock_path(path: Path) -> Path:
    return path.with_suffix(".lock")


__all__ = ["load_settings_document", "settings_lock_path", "update_settings_document"]
