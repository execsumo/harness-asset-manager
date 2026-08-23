from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness_asset_manager.atomic_files import atomic_write_text, file_lock

ASSET_TAG_SCHEMA_VERSION = 1


class AssetTagStore:
    """Persistent storage for asset tags (``data/asset-tags.json``).

    Follows the three store-portability invariants:
    1. Keys are ``<family>:<ref>`` — no device-local absolute paths.
    2. Total reads: absent, truncated, or corrupt JSON degrades to an empty map
       without raising an exception out of ``load()``.
    3. Writes are atomic with file-locking and round-trip preservation of unknown keys.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    @property
    def lock_path(self) -> Path:
        return self.path.with_suffix(".lock")

    def load(self) -> dict[str, list[str]]:
        """Total read: returns all tags mapping ``<family>:<ref>`` -> list of tags."""
        if not self.path.is_file():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        if not isinstance(payload, dict):
            return {}
        tags_payload = payload.get("tags")
        if not isinstance(tags_payload, dict):
            return {}
        result: dict[str, list[str]] = {}
        for key, raw_tags in tags_payload.items():
            if not isinstance(key, str) or ":" not in key or not isinstance(raw_tags, list):
                continue
            string_tags = [t for t in raw_tags if isinstance(t, str)]
            if string_tags:
                result[key] = string_tags
        return result

    def get_tags(self, key: str) -> list[str]:
        """Return the tags associated with an asset key, or an empty list."""
        return list(self.load().get(key, []))

    def set_tags(self, key: str, tags: list[str]) -> list[str]:
        """Replace the tag set for a single asset key atomically.

        Preserves unknown top-level keys and tags for other asset keys.
        If ``tags`` is empty, the key is removed from the store.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with file_lock(self.lock_path):
            payload: dict[str, Any] = {}
            if self.path.is_file():
                try:
                    loaded = json.loads(self.path.read_text(encoding="utf-8"))
                    if isinstance(loaded, dict):
                        payload = loaded
                except (OSError, ValueError):
                    payload = {}

            if "version" not in payload:
                payload["version"] = ASSET_TAG_SCHEMA_VERSION

            raw_tags = payload.get("tags")
            if not isinstance(raw_tags, dict):
                raw_tags = {}
                payload["tags"] = raw_tags

            if tags:
                raw_tags[key] = list(tags)
            else:
                raw_tags.pop(key, None)

            atomic_write_text(self.path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
            return list(tags)
