"""``harnessam bootstrap`` — bootstrap synced store assets onto this device."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

from ..output import print_json, print_table
from ..support import confirm

if TYPE_CHECKING:
    from harness_asset_manager.application import BackendContainer
    from harness_asset_manager.application.bootstrap import BootstrapPlan


def register(subparsers: argparse._SubParsersAction, common: argparse.ArgumentParser) -> None:
    parser = subparsers.add_parser(
        "bootstrap",
        parents=[common],
        help="Bootstrap synced assets from store onto this device by creating local bindings.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print bootstrap plan without mutating any files.",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Apply all linkable bindings non-interactively without confirmation.",
    )
    parser.add_argument(
        "--include-conflicts",
        action="store_true",
        help="Include occupied/conflicting targets when applying bootstrap.",
    )
    parser.set_defaults(handler=run_bootstrap)


def _print_plan_table(plan: BootstrapPlan) -> None:
    headers = ["FAMILY", "ASSET", "HARNESS", "ACTION", "TARGET / REASON"]
    rows: list[list[str]] = []
    for a in plan.actions:
        if a.action == "link":
            detail = str(a.target)
        elif a.action == "conflict":
            detail = f"{a.target} ({a.detail or a.reason})"
        else:
            detail = a.detail or (a.reason or "")
        rows.append([a.family, a.display_name, a.harness, a.action.upper(), detail])

    print_table(headers, rows)
    print(
        f"\nPlan: {len(plan.linkable)} to link, {len(plan.conflicts)} conflict(s), "
        f"{len(plan.skipped)} skipped."
    )


def run_bootstrap(container: BackendContainer, args: argparse.Namespace) -> int:
    plan = container.bootstrap_planner.plan()

    if getattr(args, "dry_run", False):
        if getattr(args, "json_output", False):
            print_json(plan.to_dict())
        else:
            _print_plan_table(plan)
        return 0

    to_apply = list(plan.linkable)
    if getattr(args, "include_conflicts", False):
        to_apply.extend(plan.conflicts)

    if not to_apply:
        if getattr(args, "json_output", False):
            print_json(
                {
                    "results": [],
                    "appliedCount": 0,
                    "failedCount": 0,
                    "message": "Nothing to bootstrap",
                }
            )
        else:
            print("Nothing to bootstrap: all assets are already linked or uninstalled on this device.")
        return 0

    if not getattr(args, "json_output", False):
        _print_plan_table(plan)
        print()

    confirm("Bootstrap these bindings", assume_yes=getattr(args, "yes", False))

    results = container.bootstrap_applier.apply(
        to_apply, allow_conflicts=getattr(args, "include_conflicts", False)
    )
    applied_count = sum(1 for r in results if r.status == "applied")
    failed_count = sum(1 for r in results if r.status == "failed")

    if getattr(args, "json_output", False):
        print_json(
            {
                "results": [r.to_dict() for r in results],
                "appliedCount": applied_count,
                "failedCount": failed_count,
            }
        )
    else:
        print()
        for r in results:
            if r.status == "applied":
                print(f"  ✓ [{r.family}] {r.ref} -> {r.harness} ({r.target})")
            else:
                print(f"  ✗ [{r.family}] {r.ref} -> {r.harness}: {r.error}")
        print(f"\nBootstrapped {applied_count} binding(s) ({failed_count} failed).")

    return 1 if failed_count > 0 else 0
