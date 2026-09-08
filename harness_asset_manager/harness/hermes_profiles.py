from __future__ import annotations

import re
from pathlib import Path

from harness_asset_manager.errors import MutationError

# Copied verbatim from /usr/local/lib/hermes-agent/hermes_cli/profiles.py
# A Hermes upgrade can extend these.
_RESERVED_NAMES = {"hermes", "default", "test", "tmp", "root", "sudo"}
_HERMES_SUBCOMMANDS = {
    "chat", "model", "gateway", "setup", "whatsapp", "login", "logout", "status", "cron", "doctor",
    "dump", "config", "pairing", "skills", "tools", "mcp", "sessions", "insights", "version", "update",
    "uninstall", "profile", "plugins", "honcho", "acp", "moa", "fallback", "worktree", "browser",
    "secrets", "egress", "migrate", "proxy", "lsp", "slack", "send", "auth", "pause", "resume", "sync",
    "webhook", "peer", "portal", "kanban", "project", "hooks", "verify", "security", "approvals",
    "debug", "backup", "checkpoints", "import", "skin", "console", "bundles", "curator", "pets",
    "journey", "learning", "memory", "computer-use", "monitoring", "claw", "completion", "dashboard",
    "serve", "desktop", "gui", "logs"
}


class HermesProfileNameError(MutationError):
    """Raised when an agent slug maps to an invalid Hermes profile name."""

    def __init__(self, slug: str, attempted_name: str, reason: str) -> None:
        self.slug = slug
        self.attempted_name = attempted_name
        self.reason = reason
        super().__init__(
            f"Cannot map agent '{slug}' to Hermes profile '{attempted_name}': {reason}",
            status=400,
            code="invalid_hermes_profile_name",
        )


def hermes_profile_name(slug: str) -> str:
    """Map a HAM agent slug to a Hermes profile id."""
    # Map dots and any other illegal char to -
    name = re.sub(r'[^a-z0-9_-]', '-', slug.lower())

    # Make the first character legal (alphanumeric)
    while name and not name[0].isalnum():
        name = name[1:]

    if not name:
        raise HermesProfileNameError(slug, "", "mapped name is empty")

    # Truncate to 64 without leaving a trailing separator
    name = name[:64]
    while name and name[-1] in ('_', '-'):
        name = name[:-1]

    if not name:
        raise HermesProfileNameError(slug, "", "mapped name became empty after removing trailing separators")

    if name in _RESERVED_NAMES:
        raise HermesProfileNameError(slug, name, "name is a reserved Hermes profile name")

    if name in _HERMES_SUBCOMMANDS:
        raise HermesProfileNameError(slug, name, "name conflicts with a Hermes subcommand")

    return name


def validate_slug_collisions(slugs: set[str]) -> None:
    """Map a set of slugs and raise when two distinct slugs map to the same profile name."""
    seen: dict[str, str] = {}
    for slug in sorted(slugs):
        try:
            name = hermes_profile_name(slug)
        except HermesProfileNameError:
            continue

        if name in seen:
            raise MutationError(
                f"Slugs '{seen[name]}' and '{slug}' both map to the same Hermes profile name '{name}'",
                status=400,
                code="hermes_profile_name_collision",
            )
        seen[name] = slug


def profiles_root(hermes_root: Path) -> Path:
    return hermes_root / "profiles"


def profile_home(hermes_root: Path, name: str) -> Path:
    return profiles_root(hermes_root) / name


def profile_skills_harnessam_dir(hermes_root: Path, name: str) -> Path:
    return profile_home(hermes_root, name) / "skills" / "harnessam"


def profile_tombstone_path(hermes_root: Path, name: str) -> Path:
    return profiles_root(hermes_root) / ".deleted" / name


def profile_is_tombstoned(hermes_root: Path, name: str) -> bool:
    return profile_tombstone_path(hermes_root, name).exists()
