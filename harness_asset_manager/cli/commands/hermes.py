from __future__ import annotations

import argparse


def register(subparsers, common: argparse.ArgumentParser) -> None:
    parser = subparsers.add_parser("hermes", help="Manage Hermes integrations.", parents=[common])
    sub = parser.add_subparsers(dest="subcommand", required=True)

    compat_parser = sub.add_parser("compat", help="Manage the Hermes compatibility sidecar.")
    compat_sub = compat_parser.add_subparsers(dest="action", required=True)

    status_parser = compat_sub.add_parser("status", help="Check if the compatibility sidecar is installed.")
    status_parser.set_defaults(handler=compat_status_command)

    install_parser = compat_sub.add_parser("install", help="Install or refresh the compatibility sidecar.")
    install_parser.set_defaults(handler=compat_install_command)

    remove_parser = compat_sub.add_parser("remove", help="Remove the compatibility sidecar.")
    remove_parser.set_defaults(handler=compat_remove_command)

def compat_status_command(container, args: argparse.Namespace) -> int:
    from harness_asset_manager.runtime.hermes_compat import status
    print(status(container.hermes_root))
    return 0

def compat_install_command(container, args: argparse.Namespace) -> int:
    from harness_asset_manager.runtime.hermes_compat import apply_hermes_compat
    if apply_hermes_compat(container.hermes_root):
        print("Installed.")
        return 0
    else:
        print("Failed to install or not required.")
        return 1

def compat_remove_command(container, args: argparse.Namespace) -> int:
    from harness_asset_manager.runtime.hermes_compat import remove_hermes_compat
    if remove_hermes_compat(container.hermes_root):
        print("Removed.")
        return 0
    else:
        print("Failed to remove.")
        return 1
