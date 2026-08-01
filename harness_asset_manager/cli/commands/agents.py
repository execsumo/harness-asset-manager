"""``harnessam agents …`` — the CLI mirror of ``/api/agents``.

The agents services return dataclasses rather than dicts (the HTTP layer maps them
into pydantic models), so this module owns the same mapping for ``--json``. The keys
match the API response so both surfaces stay copy-pasteable.
"""

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
    print_table,
    truncate,
)
from ..support import (
    CliError,
    add_confirmation_flag,
    add_harness_flag,
    confirm,
    read_text_argument,
)


def register(subparsers, common: argparse.ArgumentParser) -> None:
    parser = subparsers.add_parser("agents", help="Inspect and bind subagents across harnesses.")
    group = parser.add_subparsers(dest="agents_command", required=True)

    listing = group.add_parser("list", parents=[common], help="Show the agents/harness matrix.")
    listing.set_defaults(handler=list_agents)

    show = group.add_parser("show", parents=[common], help="Show one agent in detail.")
    show.add_argument("ref")
    show.set_defaults(handler=show_agent)

    create = group.add_parser("create", parents=[common], help="Create an agent in the store.")
    create.add_argument("--name", required=True)
    create.add_argument("--description", required=True)
    create.add_argument("--prompt", help="Agent prompt body.")
    create.add_argument("--prompt-file", help="Read the prompt from a file ('-' for stdin).")
    create.add_argument("--tool", action="append", dest="tools", default=[], help="Repeatable tool name.")
    create.set_defaults(handler=create_agent)

    update = group.add_parser("update", parents=[common], help="Update an agent in the store.")
    update.add_argument("ref")
    update.add_argument("--name")
    update.add_argument("--description")
    update.add_argument("--prompt")
    update.add_argument("--prompt-file", help="Read the prompt from a file ('-' for stdin).")
    update.add_argument(
        "--tool",
        action="append",
        dest="tools",
        default=None,
        help="Repeatable tool name; passing any replaces the whole list.",
    )
    update.set_defaults(handler=update_agent)

    delete = group.add_parser("delete", parents=[common], help="Delete an agent and its bindings.")
    delete.add_argument("ref")
    add_confirmation_flag(delete)
    delete.set_defaults(handler=delete_agent)

    enable = group.add_parser("enable", parents=[common], help="Bind an agent into one harness.")
    enable.add_argument("ref")
    add_harness_flag(enable)
    enable.set_defaults(handler=enable_agent)

    disable = group.add_parser("disable", parents=[common], help="Unbind an agent from one harness.")
    disable.add_argument("ref")
    add_harness_flag(disable)
    disable.set_defaults(handler=disable_agent)

    set_harnesses = group.add_parser(
        "set-harnesses", parents=[common], help="Bind an agent to exactly this set of harnesses."
    )
    set_harnesses.add_argument("ref")
    set_harnesses.add_argument(
        "--harness",
        action="append",
        dest="harnesses",
        default=[],
        help="Repeatable; omit entirely to unbind everywhere.",
    )
    set_harnesses.set_defaults(handler=set_agent_harnesses)

    adopt = group.add_parser("adopt", parents=[common], help="Take a harness-owned agent into the store.")
    adopt.add_argument("ref")
    adopt.add_argument(
        "--on-conflict",
        choices=("keep_store", "replace_store"),
        default=None,
        help="How to resolve a slug that already exists in the store.",
    )
    adopt.set_defaults(handler=adopt_agent)

    adopt_all = group.add_parser("adopt-all", parents=[common], help="Adopt every unmanaged agent.")
    adopt_all.set_defaults(handler=adopt_all_agents)


def list_agents(container: "BackendContainer", args: argparse.Namespace) -> int:
    inventory = container.agents_inventory.build()
    if args.json_output:
        print_json(
            {
                "columns": [
                    {"harness": column.id, "label": column.label, "installed": column.installed}
                    for column in inventory.columns
                ],
                "entries": [
                    {
                        "ref": entry.ref,
                        "name": entry.name,
                        "description": entry.description,
                        "kind": entry.kind,
                        "harnessPath": str(entry.harness_path) if entry.harness_path else None,
                        "bindings": [
                            {"harness": binding.harness, "state": binding.state, "detail": binding.detail}
                            for binding in entry.bindings
                        ],
                        "actions": {"canAdopt": entry.can_adopt, "canDelete": entry.can_delete},
                    }
                    for entry in inventory.entries
                ],
                "issues": [{"name": issue.name, "reason": issue.reason} for issue in inventory.issues],
            }
        )
        return 0

    headers = ["REF", "NAME", "KIND", *[column.id for column in inventory.columns]]
    rows = []
    for entry in inventory.entries:
        states = {binding.harness: binding.state for binding in entry.bindings}
        rows.append(
            [
                truncate(entry.ref, 34),
                truncate(entry.name, 28),
                entry.kind,
                *[glyph(str(states.get(column.id, "disabled"))) for column in inventory.columns],
            ]
        )
    print_matrix(headers, rows, empty="No agents found.")
    if inventory.issues:
        print()
        for issue in inventory.issues:
            print(f"issue: {issue.name}: {issue.reason}")
    return 0


def show_agent(container: "BackendContainer", args: argparse.Namespace) -> int:
    detail = _require_detail(container, args.ref)
    if args.json_output:
        print_json(_detail_payload(detail))
        return 0
    print_fields(
        [
            ("ref", detail.ref),
            ("name", detail.name),
            ("description", detail.description),
            ("tools", ", ".join(detail.tools) or "(inherits all)"),
            ("store path", detail.store_path),
        ]
    )
    print()
    print_table(
        ["HARNESS", "STATE", "METHOD", "PATH"],
        [
            [harness.harness, harness.state, harness.install_method, str(harness.path)]
            for harness in detail.harnesses
        ],
    )
    if detail.configuration:
        print()
        print_table(["KEY", "VALUE"], [[key, value] for key, value in detail.configuration])
    return 0


def create_agent(container: "BackendContainer", args: argparse.Namespace) -> int:
    prompt = read_text_argument(args.prompt, args.prompt_file, label="prompt")
    agent = container.agents_store.create(
        name=args.name,
        description=args.description,
        prompt=prompt,
        tools=tuple(args.tools),
    )
    container.invalidation.invalidate_all()
    if args.json_output:
        print_json(_detail_payload(_require_detail(container, agent.slug)))
        return 0
    print(f"created agent {agent.slug}")
    return 0


def update_agent(container: "BackendContainer", args: argparse.Namespace) -> int:
    prompt = None
    if args.prompt is not None or args.prompt_file is not None:
        prompt = read_text_argument(args.prompt, args.prompt_file, label="prompt")
    if args.name is None and args.description is None and prompt is None and args.tools is None:
        raise CliError("nothing to update; pass at least one of --name, --description, --prompt, --tool")
    agent = container.agents_store.update(
        args.ref,
        name=args.name,
        description=args.description,
        prompt=prompt,
        tools=tuple(args.tools) if args.tools is not None else None,
    )
    container.invalidation.invalidate_all()
    if args.json_output:
        print_json(_detail_payload(_require_detail(container, agent.slug)))
        return 0
    print(f"updated agent {agent.slug}")
    return 0


def delete_agent(container: "BackendContainer", args: argparse.Namespace) -> int:
    confirm(f"delete agent {args.ref}", assume_yes=args.yes)
    container.agents_mutations.delete(args.ref)
    container.invalidation.invalidate_all()
    if args.json_output:
        print_json({"ok": True})
        return 0
    print(f"deleted agent {args.ref}")
    return 0


def enable_agent(container: "BackendContainer", args: argparse.Namespace) -> int:
    container.agents_mutations.enable(args.ref, args.harness)
    container.invalidation.invalidate_all()
    if args.json_output:
        print_json({"ok": True})
        return 0
    print(f"enabled {args.ref} for {args.harness}")
    return 0


def disable_agent(container: "BackendContainer", args: argparse.Namespace) -> int:
    container.agents_mutations.disable(args.ref, args.harness)
    container.invalidation.invalidate_all()
    if args.json_output:
        print_json({"ok": True})
        return 0
    print(f"disabled {args.ref} for {args.harness}")
    return 0


def set_agent_harnesses(container: "BackendContainer", args: argparse.Namespace) -> int:
    succeeded, failed = container.agents_mutations.set_harnesses(args.ref, list(args.harnesses))
    container.invalidation.invalidate_all()
    payload = {
        "ok": not failed,
        "succeeded": succeeded,
        "failed": [{"harness": harness, "error": error} for harness, error in failed],
    }
    if args.json_output:
        print_json(payload)
        return 0 if not failed else 1
    print(f"bound {args.ref} to {', '.join(succeeded) if succeeded else 'no harnesses'}")
    for harness, error in failed:
        print(f"error: {harness}: {error}")
    return 0 if not failed else 1


def adopt_agent(container: "BackendContainer", args: argparse.Namespace) -> int:
    # Deferred: a module-scope application import would slow every `harnessam` run.
    from harness_asset_manager.application.agents import AgentAdoptConflict

    try:
        slug = container.agents_mutations.adopt(args.ref, args.on_conflict)
    except AgentAdoptConflict as conflict:
        raise CliError(
            f"an agent named {conflict.slug} already exists in the store "
            f"({conflict.store_path}); harness copy is {conflict.harness_path}. "
            "Re-run with --on-conflict keep_store or --on-conflict replace_store."
        ) from conflict
    container.invalidation.invalidate_all()
    if args.json_output:
        print_json({"ok": True, "ref": slug})
        return 0
    print(f"adopted {slug}")
    return 0


def adopt_all_agents(container: "BackendContainer", args: argparse.Namespace) -> int:
    result = container.agents_mutations.adopt_all()
    container.invalidation.invalidate_all()
    if args.json_output:
        print_json(
            {
                "ok": True,
                "adopted": list(result.adopted),
                "skipped": [{"ref": ref, "reason": reason} for ref, reason in result.skipped],
            }
        )
        return 0
    print(f"adopted {len(result.adopted)}, skipped {len(result.skipped)}")
    for ref, reason in result.skipped:
        print(f"skipped: {ref}: {reason}")
    return 0


def _require_detail(container: "BackendContainer", ref: str):
    detail = container.agents_inventory.detail(ref)
    if detail is None:
        raise MutationError(f"agent not found: {ref}", status=404)
    return detail


def _detail_payload(detail) -> dict[str, object]:
    return {
        "ref": detail.ref,
        "name": detail.name,
        "description": detail.description,
        "prompt": detail.prompt,
        "tools": list(detail.tools),
        "document": detail.document,
        "storePath": str(detail.store_path),
        "harnesses": [
            {
                "harness": harness.harness,
                "label": harness.label,
                "state": harness.state,
                "detail": harness.detail,
                "path": str(harness.path),
                "installMethod": harness.install_method,
                "installed": harness.installed,
            }
            for harness in detail.harnesses
        ],
        "configuration": [{"key": key, "value": value} for key, value in detail.configuration],
        "canDelete": detail.can_delete,
    }
