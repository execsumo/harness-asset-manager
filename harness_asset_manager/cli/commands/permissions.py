"""``harnessam permissions …`` — the CLI mirror of ``/api/permissions``."""

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
)

# Mirrors the Permissions form in the web UI. Constraining these here matters: the
# store accepts any string, but a rule whose scope no harness mapper recognizes is
# written and then never appears in the inventory again.
DECISIONS = ("deny", "allow", "ask")
SCOPES = ("shell", "file_read", "file_write", "web", "mcp", "any")


def register(subparsers, common: argparse.ArgumentParser) -> None:
    parser = subparsers.add_parser("permissions", help="Inspect and bind permission rules across harnesses.")
    group = parser.add_subparsers(dest="permissions_command", required=True)

    listing = group.add_parser("list", parents=[common], help="Show the permissions/harness matrix.")
    listing.set_defaults(handler=list_permissions)

    show = group.add_parser("show", parents=[common], help="Show one permission rule in detail.")
    show.add_argument("id")
    show.set_defaults(handler=show_permission)

    create = group.add_parser("create", parents=[common], help="Create a managed permission rule.")
    create.add_argument("--id", required=True)
    create.add_argument(
        "--decision",
        required=True,
        choices=DECISIONS,
        help="Only 'deny' binds to harnesses today — Harness Asset Manager is denylist-only.",
    )
    create.add_argument(
        "--scope",
        required=True,
        choices=SCOPES,
        help="What the rule governs. A rule with an unlisted scope would never bind.",
    )
    create.add_argument(
        "--pattern",
        default=None,
        help="Interpreted per scope: shell='git push', file_*='~/.zshrc', web='api.example.com', mcp='server/tool'.",
    )
    create.add_argument("--description", default="")
    create.set_defaults(handler=create_permission)

    delete = group.add_parser("delete", parents=[common], help="Delete a permission rule and its bindings.")
    delete.add_argument("id")
    add_confirmation_flag(delete)
    delete.set_defaults(handler=delete_permission)

    enable = group.add_parser("enable", parents=[common], help="Bind a permission rule into one harness.")
    enable.add_argument("id")
    add_harness_flag(enable)
    enable.set_defaults(handler=enable_permission)

    disable = group.add_parser("disable", parents=[common], help="Unbind a permission rule from one harness.")
    disable.add_argument("id")
    add_harness_flag(disable)
    disable.set_defaults(handler=disable_permission)

    set_harnesses = group.add_parser(
        "set-harnesses", parents=[common], help="Apply one state to every interactive harness."
    )
    set_harnesses.add_argument("id")
    add_target_flag(set_harnesses)
    set_harnesses.set_defaults(handler=set_permission_harnesses)

    promote = group.add_parser(
        "promote", parents=[common], help="Take a harness-owned permission rule into the store."
    )
    promote.add_argument("id")
    promote.add_argument("--observed-harness", help="Harness whose config version to promote.")
    promote.set_defaults(handler=promote_permission)


def list_permissions(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.permissions_queries.list_permissions()
    if args.json_output:
        print_json(payload)
        return 0
    columns = payload["columns"]
    headers = ["ID", "DECISION", "SCOPE", "KIND", "STATUS", *[str(column["harness"]) for column in columns]]
    rows = []
    for entry in payload["entries"]:
        states = {sighting["harness"]: sighting["state"] for sighting in entry["sightings"]}
        spec = entry.get("spec") or {}
        rows.append(
            [
                truncate(entry["id"], 30),
                spec.get("decision") or "-",
                truncate(spec.get("scope") or "-", 20),
                entry["kind"],
                entry["enabledStatus"],
                *[glyph(str(states.get(column["harness"], "missing"))) for column in columns],
            ]
        )
    print_matrix(headers, rows, empty="No permission rules found.")
    _print_issues(payload)
    return 0


def show_permission(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.permissions_queries.get_permission(args.id)
    if args.json_output:
        print_json(payload)
        return 0
    spec = payload.get("spec") or {}
    print_fields(
        [
            ("id", payload["id"]),
            ("display name", payload["displayName"]),
            ("kind", payload["kind"]),
            ("status", payload["enabledStatus"]),
            ("decision", spec.get("decision")),
            ("scope", spec.get("scope")),
            ("pattern", spec.get("pattern")),
            ("description", spec.get("description")),
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


def create_permission(container: "BackendContainer", args: argparse.Namespace) -> int:
    # Deferred for the same reason as the hooks spec import: module-scope application
    # imports would slow every `harnessam` invocation, including `status`.
    from harness_asset_manager.application.permissions.store import PermissionSpec

    stored = container.permissions_mutations.create_permission(
        PermissionSpec(
            id=args.id,
            decision=args.decision,
            scope=args.scope,
            pattern=args.pattern,
            description=args.description,
        )
    )
    if args.json_output:
        print_json({"ok": True, "permission": stored.to_dict()})
        return 0
    print(f"created permission {stored.id}")
    return 0


def delete_permission(container: "BackendContainer", args: argparse.Namespace) -> int:
    confirm(f"delete permission {args.id}", assume_yes=args.yes)
    payload = container.permissions_mutations.delete_permission(args.id)
    if args.json_output:
        print_json(payload)
        return 0 if payload.get("ok") else 1
    return print_result(payload, message=f"deleted {args.id}")


def enable_permission(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.permissions_mutations.enable_permission(args.id, args.harness)
    if args.json_output:
        print_json(payload)
        return 0
    print(f"enabled {args.id} for {args.harness}")
    return 0


def disable_permission(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.permissions_mutations.disable_permission(args.id, args.harness)
    if args.json_output:
        print_json(payload)
        return 0
    print(f"disabled {args.id} for {args.harness}")
    return 0


def set_permission_harnesses(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.permissions_mutations.set_permission_all_harnesses(args.id, args.target)
    if args.json_output:
        print_json(payload)
        return 0 if payload.get("ok") else 1
    return print_result(payload, message=f"set {args.id} to {args.target}")


def promote_permission(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.permissions_mutations.promote_permission(
        args.id, observed_harness=args.observed_harness
    )
    if args.json_output:
        print_json(payload)
        return 0 if payload.get("ok", True) else 1
    print(f"promoted {args.id}")
    return 0


def _print_issues(payload: dict[str, object]) -> None:
    issues = payload.get("issues") or []
    if not issues:
        return
    print()
    for issue in issues:
        print(f"issue: {issue.get('name')}: {issue.get('reason')}")
