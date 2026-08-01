"""``harnessam mcp …`` — the CLI mirror of ``/api/mcp`` and the MCP marketplace."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from harness_asset_manager.application import BackendContainer

from ..output import (
    glyph,
    print_fields,
    print_json,
    print_matrix,
    print_result,
    print_table,
    truncate,
)
from ..support import (
    add_confirmation_flag,
    add_harness_flag,
    add_target_flag,
    confirm,
    parse_json_argument,
)


def register(subparsers, common: argparse.ArgumentParser) -> None:
    parser = subparsers.add_parser("mcp", help="Inspect and bind MCP servers across harnesses.")
    group = parser.add_subparsers(dest="mcp_command", required=True)

    listing = group.add_parser("list", parents=[common], help="Show the MCP servers/harness matrix.")
    listing.set_defaults(handler=list_servers)

    show = group.add_parser("show", parents=[common], help="Show one MCP server in detail.")
    show.add_argument("name")
    show.set_defaults(handler=show_server)

    install = group.add_parser("install", parents=[common], help="Install an MCP server from the marketplace.")
    install.add_argument("qualified_name", metavar="qualified-name")
    install.set_defaults(handler=install_server)

    uninstall = group.add_parser("uninstall", parents=[common], help="Remove a managed MCP server.")
    uninstall.add_argument("name")
    add_confirmation_flag(uninstall)
    uninstall.set_defaults(handler=uninstall_server)

    enable = group.add_parser("enable", parents=[common], help="Bind an MCP server into one harness.")
    enable.add_argument("name")
    add_harness_flag(enable)
    enable.add_argument("--config", help="JSON object of install config values ('@file' or '@-' to read).")
    enable.set_defaults(handler=enable_server)

    disable = group.add_parser("disable", parents=[common], help="Unbind an MCP server from one harness.")
    disable.add_argument("name")
    add_harness_flag(disable)
    disable.set_defaults(handler=disable_server)

    set_harnesses = group.add_parser(
        "set-harnesses", parents=[common], help="Apply one state to every interactive harness."
    )
    set_harnesses.add_argument("name")
    add_target_flag(set_harnesses)
    set_harnesses.add_argument("--config", help="JSON object of install config values ('@file' or '@-' to read).")
    set_harnesses.set_defaults(handler=set_server_harnesses)

    check = group.add_parser("check", parents=[common], help="Probe an MCP server's availability.")
    check.add_argument("name")
    check.set_defaults(handler=check_availability)

    unmanaged = group.add_parser("unmanaged", parents=[common], help="List MCP servers found in harness configs.")
    unmanaged.set_defaults(handler=list_unmanaged)

    adopt = group.add_parser("adopt", parents=[common], help="Take an unmanaged MCP server into the store.")
    adopt.add_argument("name")
    adopt.add_argument("--observed-harness", help="Harness whose config version to adopt.")
    adopt.add_argument(
        "--harness",
        action="append",
        dest="harnesses",
        default=None,
        help="Repeatable; harnesses to bind after adopting.",
    )
    adopt.set_defaults(handler=adopt_server)

    search = group.add_parser("search", parents=[common], help="Search the MCP marketplace.")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=None)
    search.add_argument("--offset", type=int, default=0)
    search.set_defaults(handler=search_marketplace)

    popular = group.add_parser("popular", parents=[common], help="List popular marketplace MCP servers.")
    popular.add_argument("--limit", type=int, default=None)
    popular.add_argument("--offset", type=int, default=0)
    popular.set_defaults(handler=popular_marketplace)


def list_servers(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.mcp_queries.list_servers()
    if args.json_output:
        print_json(payload)
        return 0
    columns = payload["columns"]
    headers = ["NAME", "KIND", "STATUS", *[str(column["harness"]) for column in columns]]
    rows = []
    for entry in payload["entries"]:
        states = {sighting["harness"]: sighting["state"] for sighting in entry["sightings"]}
        rows.append(
            [
                truncate(entry["name"], 34),
                entry["kind"],
                entry["enabledStatus"],
                *[glyph(str(states.get(column["harness"], "missing"))) for column in columns],
            ]
        )
    print_matrix(headers, rows, empty="No MCP servers found.")
    _print_issues(payload)
    return 0


def show_server(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.mcp_queries.get_server(args.name)
    if args.json_output:
        print_json(payload)
        return 0
    spec = payload.get("spec") or {}
    print_fields(
        [
            ("name", payload["name"]),
            ("display name", payload["displayName"]),
            ("kind", payload["kind"]),
            ("status", payload["enabledStatus"]),
            ("transport", spec.get("transport")),
            ("command", spec.get("command")),
            ("args", " ".join(spec.get("args") or [])),
            ("url", spec.get("url")),
            ("mcp status", (payload.get("mcpStatus") or {}).get("kind")),
            ("reason", (payload.get("mcpStatus") or {}).get("reason")),
        ]
    )
    print()
    print_table(
        ["HARNESS", "STATE", "DETAIL"],
        [
            [sighting["harness"], sighting["state"], sighting.get("driftDetail") or "-"]
            for sighting in payload["sightings"]
        ],
    )
    return 0


def install_server(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.mcp_mutations.install_from_marketplace(args.qualified_name)
    if args.json_output:
        print_json(payload)
        return 0
    print(f"installed {payload['server']['name']}")
    return 0


def uninstall_server(container: "BackendContainer", args: argparse.Namespace) -> int:
    confirm(f"uninstall MCP server {args.name}", assume_yes=args.yes)
    payload = container.mcp_mutations.uninstall_server(args.name)
    if args.json_output:
        print_json(payload)
        return 0 if payload.get("ok") else 1
    return print_result(payload, message=f"uninstalled {args.name}")


def enable_server(container: "BackendContainer", args: argparse.Namespace) -> int:
    config = parse_json_argument(args.config, label="--config")
    payload = container.mcp_mutations.enable_server(args.name, args.harness, config=config)
    if args.json_output:
        print_json(payload)
        return 0
    print(f"enabled {args.name} for {args.harness}")
    return 0


def disable_server(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.mcp_mutations.disable_server(args.name, args.harness)
    if args.json_output:
        print_json(payload)
        return 0
    print(f"disabled {args.name} for {args.harness}")
    return 0


def set_server_harnesses(container: "BackendContainer", args: argparse.Namespace) -> int:
    config = parse_json_argument(args.config, label="--config")
    payload = container.mcp_mutations.set_server_all_harnesses(args.name, args.target, config=config)
    if args.json_output:
        print_json(payload)
        return 0 if payload.get("ok") else 1
    return print_result(payload, message=f"set {args.name} to {args.target}")


def check_availability(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.mcp_queries.check_availability(args.name)
    if args.json_output:
        print_json(payload)
        return 0
    print_fields(
        [
            ("name", payload["name"]),
            ("availability", payload["availabilityStatus"]),
            ("reason", payload.get("availabilityReason")),
        ]
    )
    return 0 if payload["availabilityStatus"] == "available" else 1


def list_unmanaged(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.mcp_queries.list_unmanaged_by_server()
    if args.json_output:
        print_json(payload)
        return 0
    print_table(
        ["NAME", "IDENTICAL", "SEEN IN"],
        [
            [
                truncate(server["name"], 34),
                "yes" if server["identical"] else "no",
                ", ".join(sighting["harness"] for sighting in server["sightings"]),
            ]
            for server in payload["servers"]
        ],
        empty="No unmanaged MCP servers found.",
    )
    _print_issues(payload)
    return 0


def adopt_server(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.mcp_mutations.adopt(
        args.name,
        observed_harness=args.observed_harness,
        harnesses=args.harnesses,
    )
    if args.json_output:
        print_json(payload)
        return 0 if payload.get("ok") else 1
    return print_result(payload, message=f"adopted {args.name}")


def search_marketplace(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.mcp_marketplace_catalog.search_page(
        args.query, limit=args.limit, offset=args.offset
    )
    return _print_marketplace_page(payload, json_output=args.json_output)


def popular_marketplace(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.mcp_marketplace_catalog.popular_page(limit=args.limit, offset=args.offset)
    return _print_marketplace_page(payload, json_output=args.json_output)


def _print_marketplace_page(payload: dict[str, object], *, json_output: bool) -> int:
    if json_output:
        print_json(payload)
        return 0
    print_table(
        ["QUALIFIED NAME", "NAME", "DESCRIPTION"],
        [
            [
                truncate(item.get("qualifiedName"), 40),
                truncate(item.get("displayName"), 24),
                truncate(item.get("description"), 50),
            ]
            for item in (payload.get("items") or [])
        ],
        empty="No marketplace results.",
    )
    return 0


def _print_issues(payload: dict[str, object]) -> None:
    issues = payload.get("issues") or []
    if not issues:
        return
    print()
    for issue in issues:
        print(f"issue: {issue.get('name')}: {issue.get('reason')}")
