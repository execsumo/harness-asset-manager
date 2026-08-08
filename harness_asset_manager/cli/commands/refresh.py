"""``harnessam refresh`` — run one read/reconciliation pass for every asset family."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from harness_asset_manager.application import BackendContainer

from ..output import print_json

REFRESHED_FAMILIES = ("skills", "slash_commands", "mcp", "hooks", "permissions", "agents")


def register(subparsers, common: argparse.ArgumentParser) -> None:
    parser = subparsers.add_parser(
        "refresh",
        parents=[common],
        help="Run one inventory and auto-adoption pass for every asset family.",
    )
    parser.set_defaults(handler=refresh_inventories)


def refresh_inventories(container: "BackendContainer", args: argparse.Namespace) -> int:
    """Trigger each query path once; the query services own reconciliation."""
    container.skills_queries.list_skills()
    container.slash_command_queries.list_commands()
    container.mcp_queries.list_servers()
    container.hooks_queries.list_hooks()
    container.permissions_queries.list_permissions()
    container.agents_inventory.build()

    payload = {"refreshed": list(REFRESHED_FAMILIES)}
    if args.json_output:
        print_json(payload)
    else:
        print("refreshed: " + ", ".join(REFRESHED_FAMILIES))
    return 0
