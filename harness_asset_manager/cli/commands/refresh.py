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
    parser.add_argument(
        "--sync-all",
        action="store_true",
        help="Enable auto-adoption and drift reconciliation across all asset families during this pass.",
    )
    parser.set_defaults(handler=refresh_inventories)


def refresh_inventories(container: "BackendContainer", args: argparse.Namespace) -> int:
    """Trigger each query path once; the query services own reconciliation."""
    if getattr(args, "sync_all", False):
        for family in REFRESHED_FAMILIES:
            container.settings_mutations.set_auto_adopt(family, enabled=True)

    container.skills_queries.list_skills()
    container.slash_command_queries.list_commands()
    container.mcp_queries.list_servers()
    container.hooks_queries.list_hooks()
    container.permissions_queries.list_permissions()
    container.agents_inventory.build()

    payload = {
        "refreshed": list(REFRESHED_FAMILIES),
        "syncAll": getattr(args, "sync_all", False),
    }
    if args.json_output:
        print_json(payload)
    else:
        status_msg = "refreshed: " + ", ".join(REFRESHED_FAMILIES)
        if getattr(args, "sync_all", False):
            status_msg += " (sync-all enabled across all families)"
        print(status_msg)
    return 0
