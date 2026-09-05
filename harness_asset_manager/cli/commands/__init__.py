"""Asset command groups for the CLI.

Each module registers one top-level group and attaches a ``handler`` default to every
leaf subparser. ``cli.main`` builds the backend container once, then calls that
handler with ``(container, args)`` — the same container the HTTP server uses, so the
CLI and the app agree on state without one having to be running for the other.
"""

from __future__ import annotations

import argparse

from . import (
    agents,
    bootstrap,
    configs,
    hooks,
    mcp,
    permissions,
    refresh,
    settings,
    skills,
    slash_commands,
)

# ``normalize_argv`` prepends ``serve`` to anything it does not recognize as a command,
# so every group registered below has to appear here or ``harnessam skills list`` would
# be parsed as ``serve skills list``.
GROUP_NAMES = frozenset(
    {
        "agents",
        "bootstrap",
        "commands",
        "configs",
        "health",
        "hooks",
        "mcp",
        "permissions",
        "refresh",
        "settings",
        "skills",
    }
)



def register(subparsers, common: argparse.ArgumentParser) -> None:
    for module in _MODULES:
        module.register(subparsers, common)


__all__ = ["GROUP_NAMES", "register"]
_MODULES = (bootstrap, skills, agents, mcp, hooks, permissions, slash_commands, settings, refresh, configs)
