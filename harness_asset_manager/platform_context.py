from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .env_names import (
    AGY_ROOT_ENV,
    CLAUDE_ROOT_ENV,
    CODEX_ROOT_ENV,
    CURSOR_ROOT_ENV,
    HERMES_HOME_ENV,
    HERMES_ROOT_ENV,
    OPENCODE_ROOT_ENV,
    SETTINGS_PATH_ENV,
    STATE_DIR_ENV,
    env_get,
    legacy_name,
)

PlatformName = Literal["macos", "linux"]


@dataclass(frozen=True)
class PlatformContext:
    platform: PlatformName
    sys_platform: str
    env: dict[str, str]
    home: Path
    xdg_config_home: Path
    xdg_data_home: Path
    xdg_state_home: Path


def resolve_platform_context(
    env: dict[str, str] | None = None,
    *,
    sys_platform: str | None = None,
) -> PlatformContext:
    active_env = dict(os.environ)
    if env is not None:
        active_env.update(env)
    state_dir = env_get(active_env, STATE_DIR_ENV)
    if state_dir:
        active_env = _isolate_state_dir_environment(active_env, state_dir)
    active_sys_platform = sys.platform if sys_platform is None else sys_platform
    platform_name = _platform_name(active_sys_platform)
    home = _path_from_env(active_env, "HOME", Path.home())
    return PlatformContext(
        platform=platform_name,
        sys_platform=active_sys_platform,
        env=active_env,
        home=home,
        xdg_config_home=_path_from_env(active_env, "XDG_CONFIG_HOME", home / ".config"),
        xdg_data_home=_path_from_env(active_env, "XDG_DATA_HOME", home / ".local" / "share"),
        xdg_state_home=_path_from_env(active_env, "XDG_STATE_HOME", home / ".local" / "state"),
    )


def _isolate_state_dir_environment(env: dict[str, str], state_dir: str) -> dict[str, str]:
    """Make a state-dir override cover every path the app can inspect or write.

    ``--state-dir`` is intended for CI and throwaway runs.  Redirecting only HAM's
    store leaves catalog-resolved harness paths under the caller's real home, where
    an inventory pass can still read (and a mutation can still write) real configs.
    Normalize the environment here so direct callers of ``resolve_platform_context``
    get the same isolation guarantees as the CLI.
    """
    isolated = dict(env)
    isolated_root = str(Path(state_dir))
    isolated["HOME"] = isolated_root
    isolated["XDG_CONFIG_HOME"] = isolated_root
    isolated["XDG_DATA_HOME"] = isolated_root
    isolated["XDG_STATE_HOME"] = isolated_root

    # Explicit path overrides must not escape the requested isolation root.  The
    # Hermes-native HERMES_HOME variable is included because catalog resolution
    # intentionally supports it alongside our namespaced override.
    for name in (
        SETTINGS_PATH_ENV,
        CLAUDE_ROOT_ENV,
        CODEX_ROOT_ENV,
        AGY_ROOT_ENV,
        CURSOR_ROOT_ENV,
        OPENCODE_ROOT_ENV,
        HERMES_ROOT_ENV,
        HERMES_HOME_ENV,
        "HERMES_HOME",
    ):
        isolated.pop(name, None)
        isolated.pop(legacy_name(name), None)
    isolated[STATE_DIR_ENV] = isolated_root
    return isolated


def _platform_name(sys_platform: str) -> PlatformName:
    if sys_platform == "darwin":
        return "macos"
    if sys_platform.startswith("linux"):
        return "linux"
    raise RuntimeError(f"unsupported platform: {sys_platform}")


def _path_from_env(env: dict[str, str], key: str, fallback: Path) -> Path:
    value = env.get(key)
    return Path(value) if value else fallback


__all__ = ["PlatformContext", "PlatformName", "resolve_platform_context"]
