from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness_asset_manager.atomic_files import atomic_write_text, file_lock

from .model import ConfigRecord, ManifestSchema

MANIFEST_SCHEMA_VERSION = 1


class ConfigStore:
    """Persistent storage for configuration snapshots (``configs/manifest.json``).

    Follows the store-portability invariants:
    1. Total reads: absent, truncated, or corrupt JSON degrades to an empty map.
    2. Writes are atomic with file-locking and round-trip preservation of unknown keys.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    @property
    def lock_path(self) -> Path:
        return self.path.with_suffix(".lock")

    def load(self) -> ManifestSchema:
        """Total read: returns the parsed manifest."""
        if not self.path.is_file():
            return ManifestSchema(version=MANIFEST_SCHEMA_VERSION, configs={})
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return ManifestSchema(version=MANIFEST_SCHEMA_VERSION, configs={})
            
        if not isinstance(payload, dict):
            return ManifestSchema(version=MANIFEST_SCHEMA_VERSION, configs={})
            
        version = payload.get("version", MANIFEST_SCHEMA_VERSION)
        configs_payload = payload.get("configs", {})
        if not isinstance(configs_payload, dict):
            configs_payload = {}
            
        configs = {}
        for harness, data in configs_payload.items():
            if not isinstance(data, dict):
                continue
            configs[harness] = ConfigRecord(
                sourceFile=data.get("sourceFile", ""),
                preferences=data.get("preferences", {}),
                capturedAt=data.get("capturedAt", ""),
                revision=data.get("revision", "")
            )
            
        return ManifestSchema(version=version, configs=configs)

    def write_config(self, harness: str, record: ConfigRecord) -> None:
        """Writes or updates a config record for a harness."""
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
                payload["version"] = MANIFEST_SCHEMA_VERSION

            raw_configs = payload.get("configs")
            if not isinstance(raw_configs, dict):
                raw_configs = {}
                payload["configs"] = raw_configs

            raw_configs[harness] = {
                "sourceFile": record.sourceFile,
                "preferences": dict(record.preferences),
                "capturedAt": record.capturedAt,
                "revision": record.revision,
            }

            atomic_write_text(self.path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
