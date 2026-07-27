from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

SnapshotTrigger = Literal["pre_write", "external", "manual"]


@dataclass(frozen=True)
class HarnessConfigTarget:
    harness: str
    label: str
    config_name: str  # e.g., "settings.json", "config.toml"
    path: Path
    file_format: str  # json, toml, yaml, jsonc


@dataclass(frozen=True)
class ConfigSnapshot:
    snapshot_id: str
    harness: str
    config_name: str
    timestamp: str
    trigger: SnapshotTrigger
    sha256: str
    snapshot_path: Path
    original_path: Path
