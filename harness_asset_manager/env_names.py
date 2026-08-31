"""Environment variable names, and the legacy spelling each one replaced.

The project was renamed from ``skill-manager`` to ``harness-asset-manager``, but the
``SKILL_MANAGER_*`` env vars were missed. Renaming them outright would silently break
any machine that already exports one — the old name would simply stop being read, with
no error, and the override would look like it had never been set.

So every name here is read **new-first, legacy-second**. Callers pass the new name and
:func:`env_get` derives the legacy spelling from it, which keeps the pairing mechanical
rather than a second list to maintain. The legacy names are supported for one release.
"""

from __future__ import annotations

from typing import Mapping

ENV_PREFIX = "HARNESS_ASSET_MANAGER_"
LEGACY_ENV_PREFIX = "SKILL_MANAGER_"

# Paths
SETTINGS_PATH_ENV = f"{ENV_PREFIX}SETTINGS_PATH"
STATE_DIR_ENV = f"{ENV_PREFIX}STATE_DIR"
TRUSTED_HOSTS_ENV = f"{ENV_PREFIX}TRUSTED_HOSTS"

# Per-harness managed roots
CLAUDE_ROOT_ENV = f"{ENV_PREFIX}CLAUDE_ROOT"
CODEX_ROOT_ENV = f"{ENV_PREFIX}CODEX_ROOT"
AGY_ROOT_ENV = f"{ENV_PREFIX}AGY_ROOT"
CURSOR_ROOT_ENV = f"{ENV_PREFIX}CURSOR_ROOT"
OPENCODE_ROOT_ENV = f"{ENV_PREFIX}OPENCODE_ROOT"
HERMES_ROOT_ENV = f"{ENV_PREFIX}HERMES_ROOT"
HERMES_HOME_ENV = f"{ENV_PREFIX}HERMES_HOME"
FACTORY_ROOT_ENV = f"{ENV_PREFIX}FACTORY_ROOT"

# Marketplace endpoints
MARKETPLACE_BASE_URL_ENV = f"{ENV_PREFIX}MARKETPLACE_BASE_URL"
MCP_REGISTRY_BASE_URL_ENV = f"{ENV_PREFIX}MCP_REGISTRY_BASE_URL"
CLIS_DEV_BASE_URL_ENV = f"{ENV_PREFIX}CLIS_DEV_BASE_URL"


def legacy_name(name: str) -> str:
    """The ``SKILL_MANAGER_*`` spelling of a ``HARNESS_ASSET_MANAGER_*`` name."""
    if not name.startswith(ENV_PREFIX):
        return name
    return LEGACY_ENV_PREFIX + name[len(ENV_PREFIX) :]


def env_get(env: Mapping[str, str], name: str, default: str | None = None) -> str | None:
    """``env.get(name, default)``, falling back to the legacy name when unset.

    Mirrors ``dict.get`` exactly, including returning an explicitly-set empty string
    rather than the default — callers such as ``configured_marketplace_base_url``
    normalize empty values themselves, and swallowing them here would change behaviour.
    """
    if name in env:
        return env[name]
    legacy = legacy_name(name)
    if legacy in env:
        return env[legacy]
    return default


#: Every name this module owns, new and legacy — for tests that need a hermetic env.
ALL_ENV_NAMES: tuple[str, ...] = tuple(
    name
    for new_name in (
        SETTINGS_PATH_ENV,
        STATE_DIR_ENV,
        TRUSTED_HOSTS_ENV,
        CLAUDE_ROOT_ENV,
        CODEX_ROOT_ENV,
        AGY_ROOT_ENV,
        CURSOR_ROOT_ENV,
        OPENCODE_ROOT_ENV,
        HERMES_ROOT_ENV,
        HERMES_HOME_ENV,
        FACTORY_ROOT_ENV,
        MARKETPLACE_BASE_URL_ENV,
        MCP_REGISTRY_BASE_URL_ENV,
        CLIS_DEV_BASE_URL_ENV,
    )
    for name in (new_name, legacy_name(new_name))
)


__all__ = [
    "ALL_ENV_NAMES",
    "AGY_ROOT_ENV",
    "CLAUDE_ROOT_ENV",
    "CLIS_DEV_BASE_URL_ENV",
    "CODEX_ROOT_ENV",
    "CURSOR_ROOT_ENV",
    "ENV_PREFIX",
    "HERMES_HOME_ENV",
    "FACTORY_ROOT_ENV",
    "HERMES_ROOT_ENV",
    "LEGACY_ENV_PREFIX",
    "MARKETPLACE_BASE_URL_ENV",
    "MCP_REGISTRY_BASE_URL_ENV",
    "OPENCODE_ROOT_ENV",
    "SETTINGS_PATH_ENV",
    "STATE_DIR_ENV",
    "TRUSTED_HOSTS_ENV",
    "env_get",
    "legacy_name",
]
