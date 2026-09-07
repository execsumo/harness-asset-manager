from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .identity import SourceDescriptor
from .package import SkillPackage


@dataclass(frozen=True)
class SkillObservation:
    harness: str
    label: str
    scope: str
    package: SkillPackage
    detail: str = ""


@dataclass(frozen=True)
class SkillLinkIssue:
    """A managed-category link that cannot be represented as a package scan."""

    package_dir: str
    harness: str
    label: str
    scope: str
    path: Path
    detail: Literal["broken-link", "stale-link", "detached-link"]
    source: SourceDescriptor


@dataclass(frozen=True)
class StorePackageObservation:
    package: SkillPackage
    recorded_revision: str | None = None
    recorded_source_ref: str | None = None
    recorded_source_path: str | None = None
    origin_harness: str | None = None


@dataclass(frozen=True)
class SkillsHarnessScan:
    harness: str
    label: str
    logo_key: str | None
    installed: bool
    skills: tuple[SkillObservation, ...] = ()
    excluded_skill_names: tuple[str, ...] = ()
    link_issues: tuple[SkillLinkIssue, ...] = ()


@dataclass(frozen=True)
class SkillStoreScan:
    packages: tuple[StorePackageObservation, ...] = ()
    issues: tuple[str, ...] = ()


__all__ = [
    "SkillObservation",
    "SkillLinkIssue",
    "SkillStoreScan",
    "SkillsHarnessScan",
    "StorePackageObservation",
]
