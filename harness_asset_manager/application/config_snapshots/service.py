from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from harness_asset_manager.atomic_files import atomic_write_text
from harness_asset_manager.harness import (
    ConfigSubtreeBindingProfile,
    HarnessDefinition,
    supported_harness_definitions,
)
from harness_asset_manager.paths import AppPaths
from harness_asset_manager.platform_context import resolve_platform_context

from .model import ConfigSnapshot, HarnessConfigTarget, SnapshotTrigger
from .redaction import redact_secrets


class ConfigSnapshotService:
    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths
        self.configs_root = paths.configs_dir

    def resolve_target_configs(
        self, harnesses: Sequence[HarnessDefinition] | None = None
    ) -> tuple[HarnessConfigTarget, ...]:
        """Resolve all target user-level native config files across supported harnesses."""
        definitions = harnesses or supported_harness_definitions()
        context = resolve_platform_context()
        targets: list[HarnessConfigTarget] = []
        seen_paths: set[Path] = set()

        for definition in definitions:
            for binding_key, profile in definition.bindings.items():
                if isinstance(profile, ConfigSubtreeBindingProfile):
                    try:
                        resolved_path = profile.config_path_resolver(context)
                        if resolved_path not in seen_paths:
                            seen_paths.add(resolved_path)
                            targets.append(
                                HarnessConfigTarget(
                                    harness=definition.harness,
                                    label=definition.label,
                                    config_name=resolved_path.name,
                                    path=resolved_path,
                                    file_format=profile.file_format,
                                )
                            )
                    except Exception:
                        continue

                    # Also check discovery/alternate resolvers for user configs
                    for resolver in profile.discovery_config_path_resolvers:
                        try:
                            resolved_path = resolver(context)
                            # Only include files in home directory (user-level configs)
                            if (
                                resolved_path.is_relative_to(context.home)
                                and resolved_path not in seen_paths
                            ):
                                seen_paths.add(resolved_path)
                                targets.append(
                                    HarnessConfigTarget(
                                        harness=definition.harness,
                                        label=definition.label,
                                        config_name=resolved_path.name,
                                        path=resolved_path,
                                        file_format=profile.file_format,
                                    )
                                )
                        except Exception:
                            continue

        return tuple(targets)

    def compute_sha256(self, path: Path) -> str | None:
        """Compute SHA-256 hash of a file if it exists."""
        if not path.is_file():
            return None
        hasher = hashlib.sha256()
        try:
            hasher.update(path.read_bytes())
            return hasher.hexdigest()
        except OSError:
            return None

    def get_latest_snapshot(self, harness: str, config_name: str) -> ConfigSnapshot | None:
        """Find the most recent snapshot for a given harness config file."""
        harness_dir = self.configs_root / harness
        if not harness_dir.is_dir():
            return None

        snapshots = self.list_snapshots(harness=harness)
        matching = [s for s in snapshots if s.config_name == config_name]
        if not matching:
            return None
        return max(matching, key=lambda s: s.timestamp)

    def capture_snapshot(
        self,
        target: HarnessConfigTarget,
        trigger: SnapshotTrigger,
        force: bool = False,
    ) -> ConfigSnapshot | None:
        """Capture a snapshot of a harness config file if changed or forced."""
        if not target.path.is_file():
            return None

        current_hash = self.compute_sha256(target.path)
        if not current_hash:
            return None

        latest = self.get_latest_snapshot(target.harness, target.config_name)
        if not force and latest and latest.sha256 == current_hash:
            # Content hasn't changed since latest snapshot
            return None

        now = datetime.now(timezone.utc)
        timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        snapshot_id = f"{target.config_name}.{timestamp_str}.{trigger}"

        harness_dir = self.configs_root / target.harness
        harness_dir.mkdir(parents=True, exist_ok=True)

        snapshot_path = harness_dir / f"{snapshot_id}.snapshot"

        try:
            content = target.path.read_text(encoding="utf-8")
        except Exception:
            return None

        atomic_write_text(snapshot_path, content)

        # Also update the canonical baseline file (e.g. ~/.harness-asset-manager/configs/claude/settings.json)
        canonical_path = harness_dir / target.config_name
        atomic_write_text(canonical_path, content)

        return ConfigSnapshot(
            snapshot_id=snapshot_id,
            harness=target.harness,
            config_name=target.config_name,
            timestamp=now.isoformat(),
            trigger=trigger,
            sha256=current_hash,
            snapshot_path=snapshot_path,
            original_path=target.path,
        )

    def capture_all_external_changes(self) -> tuple[ConfigSnapshot, ...]:
        """Scan all user-level native configs and capture snapshots for any external changes."""
        targets = self.resolve_target_configs()
        captured: list[ConfigSnapshot] = []
        for target in targets:
            snapshot = self.capture_snapshot(target, trigger="external", force=False)
            if snapshot:
                captured.append(snapshot)
        return tuple(captured)

    def list_snapshots(self, harness: str | None = None) -> tuple[ConfigSnapshot, ...]:
        """List all captured snapshots, optionally filtered by harness."""
        if not self.configs_root.is_dir():
            return ()

        harness_dirs = (
            [self.configs_root / harness]
            if harness
            else [d for d in self.configs_root.iterdir() if d.is_dir()]
        )

        snapshots: list[ConfigSnapshot] = []
        for h_dir in harness_dirs:
            if not h_dir.is_dir():
                continue
            h_name = h_dir.name
            for file_path in h_dir.glob("*.snapshot"):
                parts = file_path.stem.rsplit(".", 2)
                if len(parts) == 3:
                    config_name, timestamp_raw, trigger_raw = parts
                    sha256_hash = self.compute_sha256(file_path) or ""
                    snapshots.append(
                        ConfigSnapshot(
                            snapshot_id=file_path.stem,
                            harness=h_name,
                            config_name=config_name,
                            timestamp=timestamp_raw,
                            trigger=trigger_raw,  # type: ignore
                            sha256=sha256_hash,
                            snapshot_path=file_path,
                            original_path=file_path,
                        )
                    )

        return tuple(sorted(snapshots, key=lambda s: s.timestamp, reverse=True))
