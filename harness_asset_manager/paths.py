from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .env_names import SETTINGS_PATH_ENV, STATE_DIR_ENV, env_get
from .platform_context import PlatformContext, resolve_platform_context

APP_NAME = "harness-asset-manager"

__all__ = ["APP_NAME", "SETTINGS_PATH_ENV", "STATE_DIR_ENV", "AppPaths", "resolve_app_paths"]


@dataclass(frozen=True)
class AppPaths:
    config_dir: Path
    data_dir: Path
    state_dir: Path
    skills_store_root: Path
    skills_store_manifest: Path
    agents_root: Path
    bindings_ledger_path: Path
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
    settings_path = Path(settings_override) if settings_override else config_dir / "settings.json"
    return AppPaths(
        config_dir=config_dir,
        data_dir=data_dir,
        state_dir=state_dir,
        skills_store_root=data_dir / "skills",
        skills_store_manifest=data_dir / "skills-manifest.json",
        agents_root=data_dir / "agents",
        # Resolved from data_dir rather than hardcoded, so it moves with the pending
        # ~/.skill-manager retirement instead of needing a second migration.
        bindings_ledger_path=data_dir / "bindings.json",
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
    state_override = env_get(context.env, STATE_DIR_ENV)

    if context.platform == "macos":
        legacy_dir = context.home / "Library" / "Application Support" / APP_NAME
        default_macos = legacy_dir if legacy_dir.is_dir() else context.home / f".{APP_NAME}"
        config_dir = _xdg_dir(context.env, "XDG_CONFIG_HOME", default_macos)
        data_dir = _xdg_dir(context.env, "XDG_DATA_HOME", default_macos)
        state_dir = (
            Path(state_override)
            if state_override
            else _xdg_dir(context.env, "XDG_STATE_HOME", default_macos)
        )
    else:
        config_dir = _xdg_dir(context.env, "XDG_CONFIG_HOME", context.xdg_config_home / APP_NAME)
        data_dir = _xdg_dir(context.env, "XDG_DATA_HOME", context.xdg_data_home / APP_NAME)
        state_dir = (
            Path(state_override)
            if state_override
            else _xdg_dir(context.env, "XDG_STATE_HOME", context.xdg_state_home / APP_NAME)
        )
    return config_dir, data_dir, state_dir


def _xdg_dir(env: dict[str, str], xdg_key: str, fallback: Path) -> Path:
    override = env.get(xdg_key)
    if override:
        return Path(override) / APP_NAME
    return fallback


def _active_env(env: dict[str, str] | None) -> dict[str, str]:
    active_env = dict(os.environ)
    if env is not None:
        active_env.update(env)
    return active_env
