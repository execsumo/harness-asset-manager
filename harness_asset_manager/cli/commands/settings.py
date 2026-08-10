"""``harnessam settings …`` — the CLI mirror of ``/api/settings`` plus ``harnessam health``."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from harness_asset_manager.application import BackendContainer

from ..output import print_fields, print_json, print_table
from ..support import CliError


def register(subparsers, common: argparse.ArgumentParser) -> None:
    parser = subparsers.add_parser("settings", help="Read and change app settings.")
    group = parser.add_subparsers(dest="settings_command", required=True)

    show = group.add_parser("show", parents=[common], help="Show storage paths and harness support.")
    show.set_defaults(handler=show_settings)

    harness = group.add_parser("harness", parents=[common], help="Enable or disable support for a harness.")
    harness.add_argument("harness")
    _add_toggle(harness)
    harness.set_defaults(handler=set_harness_support)

    auto_adopt = group.add_parser(
        "auto-adopt", parents=[common], help="Enable or disable automatic repair of drifted bindings."
    )
    auto_adopt.add_argument(
        "family",
        choices=("agents", "skills", "slash_commands", "mcp", "hooks", "permissions"),
    )
    _add_toggle(auto_adopt)
    auto_adopt.set_defaults(handler=set_auto_adopt)

    auto_adopt_defaults = group.add_parser(
        "auto-adopt-defaults",
        parents=[common],
        help="Choose harnesses enabled after automatic adoption.",
    )
    auto_adopt_defaults.add_argument(
        "family",
        choices=("agents", "skills", "slash_commands", "mcp", "hooks", "permissions"),
    )
    defaults_group = auto_adopt_defaults.add_mutually_exclusive_group(required=True)
    defaults_group.add_argument("--harness", action="append", dest="harnesses")
    defaults_group.add_argument("--clear", action="store_true")
    auto_adopt_defaults.set_defaults(handler=set_auto_adopt_defaults)

    health = subparsers.add_parser("health", parents=[common], help="Print a health summary and exit.")
    health.set_defaults(handler=show_health)


def _add_toggle(parser: argparse.ArgumentParser) -> None:
    toggle = parser.add_mutually_exclusive_group(required=True)
    toggle.add_argument("--enable", action="store_true")
    toggle.add_argument("--disable", action="store_true")


def _enabled(args: argparse.Namespace) -> bool:
    if args.enable == args.disable:  # argparse already rejects this; belt and braces.
        raise CliError("pass exactly one of --enable or --disable")
    return bool(args.enable)


def show_settings(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.settings_queries.get_settings()
    if args.json_output:
        print_json(payload)
        return 0
    storage = payload["storage"]
    print_fields(
        [
            ("platform", storage["platform"]),
            ("config dir", storage["configDir"]),
            ("data dir", storage["dataDir"]),
            ("state dir", storage["stateDir"]),
            ("skills store", storage["skillsStorePath"]),
            ("settings file", storage["settingsPath"]),
        ]
    )
    print()
    print_table(
        ["HARNESS", "LABEL", "SUPPORTED", "INSTALLED", "MANAGED LOCATION"],
        [
            [
                harness["harness"],
                harness["label"],
                "yes" if harness["supportEnabled"] else "no",
                "yes" if harness["installed"] else "no",
                harness.get("managedLocation") or "-",
            ]
            for harness in payload["harnesses"]
        ],
    )
    auto_adopt = payload["autoAdopt"]
    print()
    print(
        "auto-adopt: "
        + ", ".join(f"{family}={'on' if enabled else 'off'}" for family, enabled in auto_adopt.items())
    )
    print(
        "auto-adopt defaults: "
        + ", ".join(
            f"{family}={','.join(harnesses) or '-'}"
            for family, harnesses in payload.get("autoAdoptHarnesses", {}).items()
        )
    )
    return 0


def set_harness_support(container: "BackendContainer", args: argparse.Namespace) -> int:
    enabled = _enabled(args)
    payload = container.settings_mutations.set_harness_support(args.harness, enabled)
    if args.json_output:
        print_json(payload)
        return 0
    print(f"{'enabled' if enabled else 'disabled'} support for {args.harness}")
    return 0


def set_auto_adopt(container: "BackendContainer", args: argparse.Namespace) -> int:
    enabled = _enabled(args)
    payload = container.settings_mutations.set_auto_adopt(args.family, enabled)
    if args.json_output:
        print_json(payload)
        return 0
    print(f"{'enabled' if enabled else 'disabled'} auto-adopt for {args.family}")
    return 0


def set_auto_adopt_defaults(container: "BackendContainer", args: argparse.Namespace) -> int:
    harnesses = [] if args.clear else list(args.harnesses or [])
    payload = container.settings_mutations.set_auto_adopt_harnesses(args.family, harnesses)
    if args.json_output:
        print_json(payload)
        return 0
    configured = payload["autoAdoptHarnesses"][args.family]
    print(f"auto-adopt defaults for {args.family}: {', '.join(configured) or '-'}")
    return 0


def show_health(container: "BackendContainer", args: argparse.Namespace) -> int:
    payload = container.skills_queries.health()
    payload["homeDir"] = str(container.harness_kernel.context.home)
    if args.json_output:
        print_json(payload)
        return 0
    print_fields([(key, value) for key, value in payload.items() if not isinstance(value, (dict, list))])
    return 0
