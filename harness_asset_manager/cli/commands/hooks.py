"""``harnessam hooks …`` — the CLI mirror of ``/api/hooks``."""

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

# Mirrors the Hooks form in the web UI. Harnesses map these categories to their own
# tool names; a raw harness matcher like "Edit" is rejected by every mapper.
EVENTS = ("pre_tool_use", "post_tool_use", "user_prompt_submit", "session_start", "stop", "pre_compact")
MATCH_CATEGORIES = ("any", "shell", "file_read", "file_write", "mcp", "web")


def register(subparsers, common: argparse.ArgumentParser) -> None:
    parser = subparsers.add_parser("hooks", help="Inspect and bind hooks across harnesses.")
    group = parser.add_subparsers(dest="hooks_command", required=True)

    listing = group.add_parser("list", parents=[common], help="Show the hooks/harness matrix.")
    listing.set_defaults(handler=list_hooks)

    show = group.add_parser("show", parents=[common], help="Show one hook in detail.")
    show.add_argument("id")
    show.set_defaults(handler=show_hook)

    create = group.add_parser("create", parents=[common], help="Create a managed hook.")
    create.add_argument("--id", required=True)
    create.add_argument("--event", required=True, choices=EVENTS, help="Lifecycle event the hook fires on.")
    create.add_argument("--command", required=True, help="Shell command the hook runs.")
    create.add_argument(
        "--match",
        default=None,
        choices=MATCH_CATEGORIES,
        help="Tool category the event is filtered to; omit to fire on every tool.",
    )
    create.add_argument("--timeout", type=int, default=None, help="Timeout in seconds.")
    create.add_argument("--description", default="")
    create.set_defaults(handler=create_hook)

    delete = group.add_parser("delete", parents=[common], help="Delete a hook and its bindings.")
    delete.add_argument("id")
    add_confirmation_flag(delete)
    delete.set_defaults(handler=delete_hook)

    enable = group.add_parser("enable", parents=[common], help="Bind a hook into one harness.")
    enable.add_argument("id")
    add_harness_flag(enable)
    enable.set_defaults(handler=enable_hook)

    disable = group.add_parser("disable", parents=[common], help="Unbind a hook from one harness.")
    disable.add_argument("id")
    add_harness_flag(disable)
    disable.set_defaults(handler=disable_hook)

    set_harnesses = group.add_parser(
        "set-harnesses", parents=[common], help="Apply one state to every interactive harness."
    )
    set_harnesses.add_argument("id")
    add_target_flag(set_harnesses)
    set_harnesses.set_defaults(handler=set_hook_harnesses)

    promote = group.add_parser("promote", parents=[common], help="Take a harness-owned hook into the store.")
    promote.add_argument("id")
    promote.add_argument("--observed-harness", help="Harness whose config version to promote.")
    promote.set_defaults(handler=promote_hook)


def list_hooks(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.hooks_queries.list_hooks()
    if args.json_output:
        print_json(payload)
        return 0
    columns = payload["columns"]
    headers = ["ID", "EVENT", "KIND", "STATUS", *[str(column["harness"]) for column in columns]]
    rows = []
    for entry in payload["entries"]:
        states = {sighting["harness"]: sighting["state"] for sighting in entry["sightings"]}
        spec = entry.get("spec") or {}
        rows.append(
            [
                truncate(entry["id"], 30),
                truncate(spec.get("event") or "-", 18),
                entry["kind"],
                entry["enabledStatus"],
                *[glyph(str(states.get(column["harness"], "missing"))) for column in columns],
            ]
        )
    print_matrix(headers, rows, empty="No hooks found.")
    _print_issues(payload)
    return 0


def show_hook(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.hooks_queries.get_hook(args.id)
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
            ("event", spec.get("event")),
            ("command", spec.get("command")),
            ("match", spec.get("match")),
            ("timeout", spec.get("timeout")),
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


def create_hook(container: "BackendContainer", args: argparse.Namespace) -> int:
    # Imported here, not at module scope: pulling in the application package costs
    # ~300ms, and `harnessam status` must not pay it just to print a pid.
    from harness_asset_manager.application.hooks.store import HookSpec

    stored = container.hooks_mutations.create_hook(
        HookSpec(
            id=args.id,
            event=args.event,
            command=args.command,
            match=args.match,
            timeout=args.timeout,
            description=args.description,
        )
    )
    if args.json_output:
        print_json({"ok": True, "hook": stored.to_dict()})
        return 0
    print(f"created hook {stored.id}")
    return 0


def delete_hook(container: "BackendContainer", args: argparse.Namespace) -> int:
    confirm(f"delete hook {args.id}", assume_yes=args.yes)
    payload = container.hooks_mutations.delete_hook(args.id)
    if args.json_output:
        print_json(payload)
        return 0 if payload.get("ok") else 1
    return print_result(payload, message=f"deleted {args.id}")


def enable_hook(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.hooks_mutations.enable_hook(args.id, args.harness)
    if args.json_output:
        print_json(payload)
        return 0
    print(f"enabled {args.id} for {args.harness}")
    return 0


def disable_hook(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.hooks_mutations.disable_hook(args.id, args.harness)
    if args.json_output:
        print_json(payload)
        return 0
    print(f"disabled {args.id} for {args.harness}")
    return 0


def set_hook_harnesses(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.hooks_mutations.set_hook_all_harnesses(args.id, args.target)
    if args.json_output:
        print_json(payload)
        return 0 if payload.get("ok") else 1
    return print_result(payload, message=f"set {args.id} to {args.target}")


def promote_hook(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.hooks_mutations.promote_hook(args.id, observed_harness=args.observed_harness)
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
