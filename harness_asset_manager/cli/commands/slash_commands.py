"""``harnessam commands …`` — the CLI mirror of ``/api/slash-commands``."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from harness_asset_manager.application import BackendContainer
from harness_asset_manager.errors import MutationError

from ..output import print_fields, print_json, print_table, truncate
from ..support import add_confirmation_flag, confirm, read_text_argument


def register(subparsers, common: argparse.ArgumentParser) -> None:
    parser = subparsers.add_parser("commands", help="Manage slash commands and their harness targets.")
    group = parser.add_subparsers(dest="slash_command", required=True)

    listing = group.add_parser("list", parents=[common], help="List slash commands and their sync status.")
    listing.set_defaults(handler=list_commands)

    targets = group.add_parser("targets", parents=[common], help="List the available slash command targets.")
    targets.set_defaults(handler=list_targets)

    show = group.add_parser("show", parents=[common], help="Show one slash command in detail.")
    show.add_argument("name")
    show.set_defaults(handler=show_command)

    create = group.add_parser("create", parents=[common], help="Create a slash command and sync it.")
    create.add_argument("--name", required=True)
    create.add_argument("--description", required=True)
    create.add_argument("--prompt", help="Command prompt body.")
    create.add_argument("--prompt-file", help="Read the prompt from a file ('-' for stdin).")
    create.add_argument(
        "--target",
        action="append",
        dest="targets",
        default=None,
        help="Repeatable target id; omit for the default target set.",
    )
    create.set_defaults(handler=create_command)

    update = group.add_parser("update", parents=[common], help="Update a slash command and re-sync it.")
    update.add_argument("name")
    update.add_argument("--description", required=True)
    update.add_argument("--prompt", help="Command prompt body.")
    update.add_argument("--prompt-file", help="Read the prompt from a file ('-' for stdin).")
    update.add_argument("--target", action="append", dest="targets", default=None, help="Repeatable target id.")
    update.set_defaults(handler=update_command)

    sync = group.add_parser("sync", parents=[common], help="Re-render a slash command into its targets.")
    sync.add_argument("name")
    sync.add_argument("--target", action="append", dest="targets", default=None, help="Repeatable target id.")
    sync.set_defaults(handler=sync_command)

    delete = group.add_parser("delete", parents=[common], help="Delete a slash command and its renders.")
    delete.add_argument("name")
    add_confirmation_flag(delete)
    delete.set_defaults(handler=delete_command)


def list_commands(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.slash_command_queries.list_commands()
    if args.json_output:
        print_json(payload)
        return 0
    print_table(
        ["NAME", "DESCRIPTION", "SYNCED TO"],
        [
            [
                truncate(command["name"], 28),
                truncate(command["description"], 44),
                ", ".join(
                    entry["target"] for entry in command["syncTargets"] if entry["status"] == "synced"
                )
                or "-",
            ]
            for command in payload["commands"]
        ],
        empty="No slash commands found.",
    )
    reviews = payload.get("reviewCommands") or []
    if reviews:
        print()
        print_table(
            ["REVIEW", "KIND", "TARGET", "PATH"],
            [
                [truncate(review["name"], 28), review["kind"], review["target"], review["path"]]
                for review in reviews
            ],
        )
    return 0


def list_targets(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.slash_command_queries.list_commands()
    if args.json_output:
        print_json({"targets": payload["targets"], "defaultTargets": payload["defaultTargets"]})
        return 0
    print_table(
        ["TARGET", "LABEL", "ENABLED", "AVAILABLE", "OUTPUT DIR"],
        [
            [
                target["id"],
                truncate(target["label"], 22),
                "yes" if target["enabled"] else "no",
                "yes" if target["available"] else "no",
                target["outputDir"],
            ]
            for target in payload["targets"]
        ],
    )
    return 0


def show_command(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.slash_command_queries.get_command(args.name)
    if payload is None:
        raise MutationError(f"unknown slash command: {args.name}", status=404)
    if args.json_output:
        print_json(payload)
        return 0
    print_fields([("name", payload["name"]), ("description", payload["description"])])
    print()
    print_table(
        ["TARGET", "STATUS", "PATH"],
        [
            [entry["target"], entry["status"], entry["path"]]
            for entry in payload["syncTargets"]
        ],
    )
    print()
    print(payload["prompt"])
    return 0


def create_command(container: "BackendContainer", args: argparse.Namespace) -> int:
    prompt = read_text_argument(args.prompt, args.prompt_file, label="prompt")
    payload = container.slash_command_mutations.create_command(
        name=args.name,
        description=args.description,
        prompt=prompt,
        targets=args.targets,
    )
    return _print_sync_result(payload, json_output=args.json_output, message=f"created /{args.name}")


def update_command(container: "BackendContainer", args: argparse.Namespace) -> int:
    prompt = read_text_argument(args.prompt, args.prompt_file, label="prompt")
    payload = container.slash_command_mutations.update_command(
        args.name,
        description=args.description,
        prompt=prompt,
        targets=args.targets,
    )
    return _print_sync_result(payload, json_output=args.json_output, message=f"updated /{args.name}")


def sync_command(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.slash_command_mutations.sync_command(args.name, targets=args.targets)
    return _print_sync_result(payload, json_output=args.json_output, message=f"synced /{args.name}")


def delete_command(container: "BackendContainer", args: argparse.Namespace) -> int:
    confirm(f"delete slash command /{args.name}", assume_yes=args.yes)
    payload = container.slash_command_mutations.delete_command(args.name)
    return _print_sync_result(payload, json_output=args.json_output, message=f"deleted /{args.name}")


def _print_sync_result(payload: dict[str, object], *, json_output: bool, message: str) -> int:
    if json_output:
        print_json(payload)
        return 0 if payload.get("ok") else 1
    print(message)
    entries = payload.get("sync") or []
    print_table(
        ["TARGET", "STATUS", "PATH"],
        [[entry["target"], entry["status"], entry.get("path") or "-"] for entry in entries],
        empty="(no targets selected)",
    )
    for entry in entries:
        if entry.get("error"):
            print(f"error: {entry['target']}: {entry['error']}")
    return 0 if payload.get("ok") else 1
