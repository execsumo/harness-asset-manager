"""``harnessam configs …`` — the CLI mirror of ``/api/configs``."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from harness_asset_manager.application import BackendContainer

from ..output import print_fields, print_json, print_table


def register(subparsers, common: argparse.ArgumentParser) -> None:
    parser = subparsers.add_parser("configs", help="Manage portable harness preferences.")
    group = parser.add_subparsers(dest="configs_command", required=True)

    listing = group.add_parser("list", parents=[common], help="Show captured preferences per harness.")
    listing.set_defaults(handler=list_configs)

    capture = group.add_parser(
        "capture",
        parents=[common],
        help="Extract preferences from every harness config into the manifest.",
    )
    capture.add_argument(
        "--explicit",
        action="store_true",
        help="Capture even where the local config has diverged from the manifest.",
    )
    capture.set_defaults(handler=capture_configs)

    restore = group.add_parser(
        "restore", parents=[common], help="Merge managed preferences back into a live config."
    )
    restore.add_argument("harness")
    restore.set_defaults(handler=restore_config)

    enable = group.add_parser(
        "enable", parents=[common], help="Enable managing a harness's config."
    )
    enable.add_argument("harness")
    enable.set_defaults(handler=enable_config)

    disable = group.add_parser(
        "disable", parents=[common], help="Disable managing a harness's config."
    )
    disable.add_argument("harness")
    disable.set_defaults(handler=disable_config)

    diff = group.add_parser(
        "diff", parents=[common], help="Compare a harness's live config against the manifest."
    )
    diff.add_argument("harness")
    diff.set_defaults(handler=diff_config)


def list_configs(container: BackendContainer, args: argparse.Namespace) -> int:
    payload = container.configs_queries.list_configs()
    if args.json_output:
        print_json(payload)
        return 0
    print_table(
        ("HARNESS", "STATUS", "KEYS", "DRIFT"),
        [
            (
                harness,
                "Managed" if record["managed"] else "Not managed",
                str(record["keyCount"]),
                str(record["driftState"])
            )
            for harness, record in sorted(payload.items())
        ],
        empty="(no harness bindings found)",
    )
    return 0


def capture_configs(container: BackendContainer, args: argparse.Namespace) -> int:
    container.configs_mutations.capture(explicit=args.explicit)
    payload = container.configs_queries.list_configs()
    if args.json_output:
        print_json(payload)
        return 0
    print_table(
        ("HARNESS", "STATUS", "KEYS", "DRIFT"),
        [
            (
                harness,
                "Managed" if record["managed"] else "Not managed",
                str(record["keyCount"]),
                str(record["driftState"])
            )
            for harness, record in sorted(payload.items())
        ],
    )
    return 0


def restore_config(container: BackendContainer, args: argparse.Namespace) -> int:
    container.configs_mutations.restore(args.harness)
    if args.json_output:
        print_json({"harness": args.harness, "restored": True})
        return 0
    print(f"restored {args.harness}")
    return 0


def enable_config(container: BackendContainer, args: argparse.Namespace) -> int:
    container.configs_mutations.enable(args.harness)
    if args.json_output:
        print_json({"harness": args.harness, "enabled": True})
        return 0
    print(f"enabled {args.harness}")
    return 0


def disable_config(container: BackendContainer, args: argparse.Namespace) -> int:
    container.configs_mutations.disable(args.harness)
    if args.json_output:
        print_json({"harness": args.harness, "disabled": True})
        return 0
    print(f"disabled {args.harness}")
    return 0


def diff_config(container: BackendContainer, args: argparse.Namespace) -> int:
    payload = container.configs_queries.get_diff(args.harness)
    if args.json_output:
        print_json(payload)
        return 0
    # The key lists carry the whole answer; an empty one is omitted rather than
    # printed as an empty row.
    print_fields(
        (
            ("state", payload["state"]),
            ("missing", ", ".join(payload["missing"])),
            ("extra", ", ".join(payload["extra"])),
            ("changed", ", ".join(payload["changed"])),
        )
    )
    return 0
