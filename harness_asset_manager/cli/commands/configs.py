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
        ("HARNESS", "KEYS", "CAPTURED"),
        [
            (harness, str(len(record["preferences"])), str(record["capturedAt"]))
            for harness, record in sorted(payload.items())
        ],
        empty="(nothing captured — run `harnessam configs capture`)",
    )
    return 0


def capture_configs(container: BackendContainer, args: argparse.Namespace) -> int:
    container.configs_mutations.capture(explicit=args.explicit)
    payload = container.configs_queries.list_configs()
    if args.json_output:
        print_json(payload)
        return 0
    print_table(
        ("HARNESS", "KEYS"),
        [(harness, str(len(record["preferences"]))) for harness, record in sorted(payload.items())],
    )
    return 0


def restore_config(container: BackendContainer, args: argparse.Namespace) -> int:
    container.configs_mutations.restore(args.harness)
    if args.json_output:
        print_json({"harness": args.harness, "restored": True})
        return 0
    print(f"restored {args.harness}")
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
