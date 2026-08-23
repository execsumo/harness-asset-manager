from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from .env_names import SETTINGS_PATH_ENV, STATE_DIR_ENV, env_get
from .platform_context import PlatformContext, resolve_platform_context

APP_NAME = "harnessam"
LEGACY_APP_NAME = "harness-asset-manager"

__all__ = [
    "APP_NAME",
    "LEGACY_APP_NAME",
    "SETTINGS_PATH_ENV",
    "STATE_DIR_ENV",
    "AppPaths",
    "resolve_app_paths",
]


@dataclass(frozen=True)
class AppPaths:
    config_dir: Path
    data_dir: Path
    state_dir: Path
    skills_store_root: Path
    skills_store_manifest: Path
    agents_root: Path
    bindings_ledger_path: Path
    asset_tags_path: Path
    agents_audit_path: Path
    agents_conflicts_root: Path
    agents_reconcile_lock_path: Path
    mutation_audit_path: Path
    marketplace_cache_root: Path
    mcp_store_manifest: Path
    hooks_store_manifest: Path
    permissions_store_manifest: Path
    slash_command_store_root: Path
    slash_command_commands_dir: Path
    slash_command_sync_state_path: Path
    settings_path: Path
    runtime_state_path: Path
    server_log_path: Path
    configs_dir: Path


def resolve_app_paths(env: dict[str, str] | None = None) -> AppPaths:
    active_env = _active_env(env)
    context = resolve_platform_context(active_env)
    config_dir, data_dir, state_dir = _base_dirs(context)
    settings_override = env_get(active_env, SETTINGS_PATH_ENV)
    settings_path = Path(settings_override) if settings_override else data_dir / "settings.json"
    return AppPaths(
        config_dir=config_dir,
        data_dir=data_dir,
        state_dir=state_dir,
        skills_store_root=data_dir / "skills",
        skills_store_manifest=data_dir / "skills-manifest.json",
        agents_root=data_dir / "agents",
        # Resolved from data_dir rather than hardcoded, so store migrations move the
        # complete central store without another family-specific path.
        bindings_ledger_path=data_dir / "bindings.json",
        asset_tags_path=data_dir / "asset-tags.json",
        agents_audit_path=data_dir / "agents-audit.json",
        # A subdirectory, deliberately: AgentStore.scan() globs the agents root's top
        # level only, so a preserved conflict copy can never be read back as an agent.
        agents_conflicts_root=data_dir / "agents" / "conflicts",
        agents_reconcile_lock_path=data_dir / "agents-reconcile.lock",
        mutation_audit_path=data_dir / "audit.log",
        marketplace_cache_root=data_dir / "marketplace",
        mcp_store_manifest=data_dir / "mcp" / "manifest.json",
        hooks_store_manifest=data_dir / "hooks" / "manifest.json",
        permissions_store_manifest=data_dir / "permissions" / "manifest.json",
        slash_command_store_root=data_dir / "slash-commands",
        slash_command_commands_dir=data_dir / "slash-commands" / "commands",
        slash_command_sync_state_path=data_dir / "slash-commands" / "sync-state.json",
        settings_path=settings_path,
        runtime_state_path=state_dir / "runtime.json",
        server_log_path=state_dir / "server.log",
        configs_dir=data_dir / "configs",
    )


def _base_dirs(context: PlatformContext) -> tuple[Path, Path, Path]:
    # --state-dir / STATE_DIR_ENV is documented (README, --help) as isolating a run so
    # CI or a throwaway sandbox never touches the real store. That promise only holds if
    # it overrides all three base dirs, not just the runtime-state one: data_dir holds
    # settings.json, every asset family's manifests, and skill/agent files. Collapsing
    # all three into one directory when the override is set mirrors
    # the macOS default below, where they already collapse to one directory absent any
    # XDG override — this is that same shape, requested explicitly instead of by default.
    state_override = env_get(context.env, STATE_DIR_ENV)
    if state_override:
        override_dir = Path(state_override)
        return override_dir, override_dir, override_dir

    if context.platform == "macos":
        default_macos = _resolve_default_store(
            context.home,
            context.home / "Library" / "Application Support" / LEGACY_APP_NAME,
        )
        config_dir = _xdg_dir(context.env, "XDG_CONFIG_HOME", default_macos)
        data_dir = _xdg_dir(context.env, "XDG_DATA_HOME", default_macos)
        state_dir = _xdg_dir(context.env, "XDG_STATE_HOME", default_macos)
    else:
        explicit_xdg = any(
            context.env.get(key)
            for key in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME")
        )
        default_linux = (
            context.home / f".{APP_NAME}"
            if explicit_xdg
            else _resolve_linux_default_store(context.home, context.xdg_data_home / APP_NAME)
        )
        config_dir = _xdg_dir(
            context.env,
            "XDG_CONFIG_HOME",
            default_linux,
        )
        data_dir = _xdg_dir(
            context.env,
            "XDG_DATA_HOME",
            default_linux,
        )
        state_dir = _xdg_dir(
            context.env,
            "XDG_STATE_HOME",
            default_linux,
        )
    return config_dir, data_dir, state_dir


def _resolve_default_store(home: Path, legacy_application_support: Path) -> Path:
    """Return the short store path, migrating the previous name once if needed."""
    is_macos = legacy_application_support.parent.name == "Application Support"
    new_store = home / f".{APP_NAME}" if is_macos else home / APP_NAME
    legacy_candidates = (
        (legacy_application_support, home / f".{LEGACY_APP_NAME}")
        if is_macos
        else (legacy_application_support,)
    )
    if new_store.exists():
        return new_store
    for legacy_store in legacy_candidates:
        if not legacy_store.is_dir() or legacy_store.is_symlink():
            continue
        try:
            new_store.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(legacy_store), str(new_store))
            # Existing harness bindings can contain absolute links into the old
            # store. Keep a compatibility alias so those links continue resolving
            # while the canonical location is the new short path.
            legacy_store.symlink_to(new_store, target_is_directory=True)
            return new_store
        except OSError:
            if new_store.exists():
                return new_store
            return legacy_store
    return new_store


def _resolve_linux_default_store(home: Path, previous_store: Path) -> Path:
    """Use one hidden Linux store, migrating the former XDG data store."""
    new_store = home / f".{APP_NAME}"
    legacy_stores = (previous_store, previous_store.parent / LEGACY_APP_NAME)
    if new_store.exists():
        return new_store
    for legacy_store in legacy_stores:
        if not legacy_store.is_dir() or legacy_store.is_symlink():
            continue
        try:
            new_store.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(legacy_store), str(new_store))
            legacy_store.symlink_to(new_store, target_is_directory=True)
            return new_store
        except OSError:
            if new_store.exists():
                return new_store
            return legacy_store
    return new_store


def _xdg_dir(env: dict[str, str], xdg_key: str, fallback: Path) -> Path:
    override = env.get(xdg_key)
    if override:
        root = Path(override)
        return _migrate_store(root / APP_NAME, root / LEGACY_APP_NAME)
    return fallback


def _migrate_store(new_store: Path, legacy_store: Path) -> Path:
    if new_store.exists() or not legacy_store.is_dir() or legacy_store.is_symlink():
        return new_store
    try:
        new_store.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(legacy_store), str(new_store))
        legacy_store.symlink_to(new_store, target_is_directory=True)
        return new_store
    except OSError:
        return new_store if new_store.exists() else legacy_store


def _active_env(env: dict[str, str] | None) -> dict[str, str]:
    active_env = dict(os.environ)
    if env is not None:
        active_env.update(env)
    return active_env
