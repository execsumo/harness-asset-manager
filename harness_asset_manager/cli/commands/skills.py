"""``harnessam skills …`` — the CLI mirror of ``/api/skills`` and the skills marketplace."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from harness_asset_manager.application import BackendContainer
from harness_asset_manager.errors import MutationError

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
)


def register(subparsers, common: argparse.ArgumentParser) -> None:
    parser = subparsers.add_parser("skills", help="Inspect and bind Skills across harnesses.")
    group = parser.add_subparsers(dest="skills_command", required=True)

    listing = group.add_parser("list", parents=[common], help="Show the skills/harness matrix.")
    listing.set_defaults(handler=list_skills)

    show = group.add_parser("show", parents=[common], help="Show one skill in detail.")
    show.add_argument("ref")
    show.set_defaults(handler=show_skill)

    enable = group.add_parser("enable", parents=[common], help="Bind a skill into one harness.")
    enable.add_argument("ref")
    add_harness_flag(enable)
    enable.set_defaults(handler=enable_skill)

    disable = group.add_parser("disable", parents=[common], help="Unbind a skill from one harness.")
    disable.add_argument("ref")
    add_harness_flag(disable)
    disable.set_defaults(handler=disable_skill)

    set_harnesses = group.add_parser(
        "set-harnesses", parents=[common], help="Apply one state to every interactive harness."
    )
    set_harnesses.add_argument("ref")
    add_target_flag(set_harnesses)
    set_harnesses.set_defaults(handler=set_skill_harnesses)

    manage = group.add_parser("manage", parents=[common], help="Take an unmanaged skill into the store.")
    manage.add_argument("ref")
    manage.set_defaults(handler=manage_skill)

    manage_all = group.add_parser("manage-all", parents=[common], help="Take every unmanaged skill into the store.")
    manage_all.set_defaults(handler=manage_all_skills)

    unmanage = group.add_parser("unmanage", parents=[common], help="Stop managing a skill, leaving it in place.")
    unmanage.add_argument("ref")
    unmanage.set_defaults(handler=unmanage_skill)

    update = group.add_parser("update", parents=[common], help="Re-fetch a managed skill from its source.")
    update.add_argument("ref")
    update.set_defaults(handler=update_skill)

    delete = group.add_parser("delete", parents=[common], help="Delete a managed skill and its bindings.")
    delete.add_argument("ref")
    add_confirmation_flag(delete)
    delete.set_defaults(handler=delete_skill)

    install = group.add_parser("install", parents=[common], help="Install a skill from the marketplace.")
    install.add_argument("install_token", metavar="install-token", help="Install token from `skills search`.")
    install.set_defaults(handler=install_skill)

    search = group.add_parser("search", parents=[common], help="Search the skills marketplace.")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=None)
    search.add_argument("--offset", type=int, default=0)
    search.set_defaults(handler=search_marketplace)

    popular = group.add_parser("popular", parents=[common], help="List popular marketplace skills.")
    popular.add_argument("--limit", type=int, default=None)
    popular.add_argument("--offset", type=int, default=0)
    popular.set_defaults(handler=popular_marketplace)


def list_skills(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.skills_queries.list_skills()
    if args.json_output:
        print_json(payload)
        return 0
    columns = payload["harnessColumns"]
    headers = ["REF", "NAME", "STATUS", *[str(column["harness"]) for column in columns]]
    rows = []
    for row in payload["rows"]:
        cells = {cell["harness"]: cell["state"] for cell in row["cells"]}
        rows.append(
            [
                truncate(row["skillRef"], 40),
                truncate(row["name"], 28),
                row["displayStatus"],
                *[glyph(str(cells.get(column["harness"], "empty"))) for column in columns],
            ]
        )
    print_matrix(headers, rows, empty="No skills found.")
    summary = payload["summary"]
    print()
    print(f"{summary['managed']} managed, {summary['unmanaged']} unmanaged")
    return 0


def show_skill(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.skills_queries.get_skill_detail(args.ref)
    if payload is None:
        raise MutationError(f"unknown skill ref: {args.ref}", status=404)
    if args.json_output:
        print_json(payload)
        return 0
    print_fields(
        [
            ("ref", payload["skillRef"]),
            ("name", payload["name"]),
            ("status", payload["displayStatus"]),
            ("description", payload["description"]),
            ("attention", payload.get("attentionMessage")),
        ]
    )
    print()
    print_table(
        ["HARNESS", "LABEL", "STATE"],
        [[cell["harness"], cell["label"], cell["state"]] for cell in payload["harnessCells"]],
    )
    locations = payload.get("locations") or []
    if locations:
        print()
        print_table(
            ["LOCATION", "SCOPE", "PATH"],
            [[loc["label"], loc.get("scope") or "-", loc.get("path") or "-"] for loc in locations],
        )
    return 0


def enable_skill(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.skills_mutations.enable_skill(args.ref, args.harness)
    if args.json_output:
        print_json(payload)
        return 0
    print(f"enabled {args.ref} for {args.harness}")
    return 0


def disable_skill(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.skills_mutations.disable_skill(args.ref, args.harness)
    if args.json_output:
        print_json(payload)
        return 0
    print(f"disabled {args.ref} for {args.harness}")
    return 0


def set_skill_harnesses(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.skills_mutations.set_skill_all_harnesses(args.ref, args.target)
    if args.json_output:
        print_json(payload)
        return 0 if payload.get("ok") else 1
    return print_result(payload, message=f"set {args.ref} to {args.target}")


def manage_skill(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.skills_mutations.manage_skill(args.ref)
    if args.json_output:
        print_json(payload)
        return 0
    print(f"managing {args.ref}")
    return 0


def manage_all_skills(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.skills_mutations.manage_all_skills()
    if args.json_output:
        print_json(payload)
        return 0 if payload.get("ok") else 1
    print(f"managed {payload['managedCount']}, skipped {payload['skippedCount']}")
    failures = payload.get("failures") or []
    for failure in failures:
        print(f"error: {failure['skillRef']}: {failure['error']}")
    return 0 if not failures else 1


def unmanage_skill(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.skills_mutations.unmanage_skill(args.ref)
    if args.json_output:
        print_json(payload)
        return 0
    print(f"stopped managing {args.ref}")
    return 0


def update_skill(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.skills_mutations.update_skill(args.ref)
    if args.json_output:
        print_json(payload)
        return 0
    print(f"updated {args.ref}")
    return 0


def delete_skill(container: "BackendContainer", args: argparse.Namespace) -> int:
    confirm(f"delete skill {args.ref}", assume_yes=args.yes)
    payload = container.skills_mutations.delete_skill(args.ref)
    if args.json_output:
        print_json(payload)
        return 0
    print(f"deleted {args.ref}")
    return 0


def install_skill(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.skills_marketplace_installs.install_skill(args.install_token)
    if args.json_output:
        print_json(payload)
        return 0
    print(f"installed {args.install_token}")
    return 0


def search_marketplace(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.skills_marketplace_queries.search_page(
        args.query, limit=args.limit, offset=args.offset
    )
    return _print_marketplace_page(payload, json_output=args.json_output)


def popular_marketplace(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.skills_marketplace_queries.popular_page(limit=args.limit, offset=args.offset)
    return _print_marketplace_page(payload, json_output=args.json_output)


def _print_marketplace_page(payload: dict[str, object], *, json_output: bool) -> int:
    if json_output:
        print_json(payload)
        return 0
    items = payload.get("items") or []
    print_table(
        ["INSTALL TOKEN", "NAME", "DESCRIPTION"],
        [
            [
                truncate(item.get("installToken") or item.get("id") or "", 44),
                truncate(item.get("name"), 26),
                truncate(item.get("description"), 52),
            ]
            for item in items
        ],
        empty="No marketplace results.",
    )
    return 0
