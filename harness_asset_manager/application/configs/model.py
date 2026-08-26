from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class ConfigRecord:
    sourceFile: str
    preferences: Mapping[str, Any]
    capturedAt: str
    revision: str

@dataclass(frozen=True)
class ManifestSchema:
    version: int
    configs: Mapping[str, ConfigRecord] = field(default_factory=dict)
