"""``harnessam snapshots …`` — the CLI mirror of ``/api/config-snapshots``.

The bare ``harnessam snapshot`` command predates this group and stays as it was; it
is the same capture that ``snapshots capture`` performs.
"""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from harness_asset_manager.application import BackendContainer

from ..output import print_json, print_table, truncate


def register(subparsers, common: argparse.ArgumentParser) -> None:
    parser = subparsers.add_parser("snapshots", help="Inspect and capture native harness config snapshots.")
    group = parser.add_subparsers(dest="snapshots_command", required=True)

    listing = group.add_parser("list", parents=[common], help="List captured config snapshots.")
    listing.add_argument("--harness", default=None, help="Only snapshots for this harness.")
    listing.set_defaults(handler=list_snapshots)

    capture = group.add_parser("capture", parents=[common], help="Capture a snapshot of every native config.")
    capture.set_defaults(handler=capture_snapshots)


def list_snapshots(container: "BackendContainer", args: argparse.Namespace) -> int:
    snapshots = container.config_snapshots.list_snapshots(harness=args.harness)
    if args.json_output:
        print_json(
            {
                "snapshots": [
                    {
                        "snapshot_id": snapshot.snapshot_id,
                        "harness": snapshot.harness,
                        "config_name": snapshot.config_name,
                        "timestamp": snapshot.timestamp,
                        "trigger": snapshot.trigger,
                        "sha256": snapshot.sha256,
                        "snapshot_path": str(snapshot.snapshot_path),
                    }
                    for snapshot in snapshots
                ]
            }
        )
        return 0
    print_table(
        ["HARNESS", "CONFIG", "TIMESTAMP", "TRIGGER", "SHA256"],
        [
            [
                snapshot.harness,
                truncate(snapshot.config_name, 28),
                snapshot.timestamp,
                snapshot.trigger,
                snapshot.sha256[:12],
            ]
            for snapshot in snapshots
        ],
        empty="No snapshots captured yet.",
    )
    return 0


def capture_snapshots(container: "BackendContainer", args: argparse.Namespace) -> int:
    captured = []
    for target in container.config_snapshots.resolve_target_configs():
        snapshot = container.config_snapshots.capture_snapshot(target, trigger="manual", force=True)
        if snapshot is not None:
            captured.append(snapshot)
    if args.json_output:
        print_json(
            {
                "ok": True,
                "captured_count": len(captured),
                "captured": [snapshot.snapshot_id for snapshot in captured],
            }
        )
        return 0
    print(f"Captured {len(captured)} harness config snapshots under {container.paths.configs_dir}:")
    for snapshot in captured:
        print(f"  - [{snapshot.harness}] {snapshot.config_name} -> {snapshot.snapshot_path.name}")
    return 0
