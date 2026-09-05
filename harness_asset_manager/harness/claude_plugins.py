from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harness_asset_manager.portable_paths import is_sync_artifact

from .contracts import FileTreeDiscoveryRoot, ResolutionContext


def resolve_candidate_install_path(raw_path: str, home: Path) -> Path | None:
    """Resolve an installPath safely and check if it exists as a directory."""
    raw_path = raw_path.strip()
    if not raw_path:
        return None

    if raw_path.startswith("~"):
        candidate = home / raw_path.lstrip("~").lstrip("/\\")
    else:
        candidate = Path(raw_path)
        if not candidate.is_dir():
            # Check portability: if recorded under a different home but contains .claude
            try:
                parts = candidate.parts
                if ".claude" in parts:
                    idx = parts.index(".claude")
                    remapped = home / Path(*parts[idx:])
                    if remapped.is_dir():
                        candidate = remapped
            except Exception:
                pass

    try:
        resolved = candidate.resolve(strict=False)
        if resolved.is_dir():
            return resolved
    except (OSError, RuntimeError):
        return None
    return None


def _find_plugin_skill_roots(install_path: Path) -> list[Path]:
    """Find skill directories within an install path safely without traversing into decoys."""
    manifest_candidates = [
        install_path / ".claude-plugin" / "plugin.json",
        install_path / "plugin.json",
    ]
    manifest_data: dict[str, Any] | None = None
    for mf in manifest_candidates:
        if mf.is_file():
            try:
                content = json.loads(mf.read_text(encoding="utf-8"))
                if isinstance(content, dict):
                    manifest_data = content
                    break
            except Exception:
                pass

    candidate_skill_roots: list[Path] = []

    if manifest_data is not None and "skills" in manifest_data:
        declared = manifest_data["skills"]
        targets: list[str] = []
        if isinstance(declared, str):
            targets = [declared]
        elif isinstance(declared, list):
            targets = [t for t in declared if isinstance(t, str)]

        for target_str in targets:
            target_str = target_str.strip()
            if not target_str:
                continue
            try:
                target_path = (install_path / target_str).resolve(strict=False)
                # Ensure target does not traverse outside install_path
                target_path.relative_to(install_path)
            except (ValueError, OSError):
                continue

            if not target_path.exists():
                continue
            if target_path.is_file() and target_path.name == "SKILL.md":
                candidate_skill_roots.append(target_path.parent)
            elif target_path.is_dir():
                if (target_path / "SKILL.md").is_file():
                    candidate_skill_roots.append(target_path)
                try:
                    for child in sorted(target_path.iterdir(), key=lambda p: p.name):
                        if not is_sync_artifact(child.name) and child.is_dir() and (child / "SKILL.md").is_file():
                            candidate_skill_roots.append(child)
                except OSError:
                    pass
    else:
        # Standard plugin layout: <installPath>/skills/<skill-dir>/SKILL.md
        skills_dir = install_path / "skills"
        if skills_dir.is_dir():
            if (skills_dir / "SKILL.md").is_file():
                candidate_skill_roots.append(skills_dir)
            try:
                for child in sorted(skills_dir.iterdir(), key=lambda p: p.name):
                    if not is_sync_artifact(child.name) and child.is_dir() and (child / "SKILL.md").is_file():
                        candidate_skill_roots.append(child)
            except OSError:
                pass
        elif (install_path / "SKILL.md").is_file():
            candidate_skill_roots.append(install_path)

    # Deduplicate candidate paths while preserving order
    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in candidate_skill_roots:
        try:
            resolved = path.resolve(strict=False)
            if resolved.is_dir() and (resolved / "SKILL.md").is_file() and resolved not in seen:
                seen.add(resolved)
                deduped.append(resolved)
        except (OSError, RuntimeError):
            continue
    return deduped


def resolve_claude_plugin_roots(context: ResolutionContext) -> tuple[FileTreeDiscoveryRoot, ...]:
    """Discover skill roots from Claude's installed_plugins.json registry.

    Reads ~/.claude/plugins/installed_plugins.json relative to active context home.
    Tolerates missing/malformed registry files and inaccessible paths.
    """
    registry_path = context.home / ".claude" / "plugins" / "installed_plugins.json"
    if not registry_path.is_file():
        return ()

    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except Exception:
        return ()

    if not isinstance(data, dict):
        return ()

    plugins_map = data.get("plugins")
    if not isinstance(plugins_map, dict):
        return ()

    discovered_roots: list[FileTreeDiscoveryRoot] = []
    seen_install_paths: set[Path] = set()
    seen_skill_paths: set[Path] = set()

    for plugin_key, raw_records in sorted(plugins_map.items(), key=lambda item: str(item[0])):
        plugin_key_str = str(plugin_key).strip()
        if not plugin_key_str:
            continue

        records: list[dict[str, Any]]
        if isinstance(raw_records, dict):
            records = [raw_records]
        elif isinstance(raw_records, list):
            records = [r for r in raw_records if isinstance(r, dict)]
        else:
            continue

        # Filter to records with an existing directory installPath
        candidates: list[tuple[dict[str, Any], Path]] = []
        for rec in records:
            raw_install_path = rec.get("installPath")
            if not isinstance(raw_install_path, str) or not raw_install_path.strip():
                continue
            resolved_path = resolve_candidate_install_path(raw_install_path, context.home)
            if resolved_path is not None:
                candidates.append((rec, resolved_path))

        if not candidates:
            continue

        # Prefer active installed entries over stale cache versions:
        # Sort candidates by (lastUpdated or installedAt, version) descending
        candidates.sort(
            key=lambda item: (
                str(item[0].get("lastUpdated") or item[0].get("installedAt") or ""),
                str(item[0].get("version") or ""),
            ),
            reverse=True,
        )

        active_rec, install_path = candidates[0]
        if install_path in seen_install_paths:
            continue
        seen_install_paths.add(install_path)

        version = str(active_rec.get("version") or "").strip()
        provenance = f"{plugin_key_str}@{version}" if version else plugin_key_str
        label = f"Claude Plugin ({provenance})"

        skill_dirs = _find_plugin_skill_roots(install_path)
        for skill_dir in skill_dirs:
            if skill_dir in seen_skill_paths:
                continue
            seen_skill_paths.add(skill_dir)

            discovered_roots.append(
                FileTreeDiscoveryRoot(
                    kind="plugin-root",
                    scope="plugin",
                    label=label,
                    path_resolver=lambda _ctx, p=skill_dir: p,
                    locator_prefix=provenance,
                )
            )

    return tuple(discovered_roots)
