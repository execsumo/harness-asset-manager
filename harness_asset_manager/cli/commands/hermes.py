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

_NOT_DETECTED = (
    "Hermes not detected; nothing to do. "
    "Looked for a virtualenv under <hermes-root>/hermes-agent/venv."
)


def compat_status_command(container, args: argparse.Namespace) -> int:
    from harness_asset_manager.runtime.hermes_compat import status
    print(status(container.hermes_root))
    return 0


def compat_install_command(container, args: argparse.Namespace) -> int:
    """Install or refresh the sidecar.

    "Hermes is not installed" is a normal outcome, not a failure — HAM supports
    machines without Hermes — so it exits 0. Only a real write failure exits 1,
    which keeps this usable in a dotfiles bootstrap script.
    """
    from harness_asset_manager.runtime.hermes_compat import apply_hermes_compat, status
    if status(container.hermes_root) == "not-detected":
        print(_NOT_DETECTED)
        return 0
    if apply_hermes_compat(container.hermes_root):
        print("Installed.")
        return 0
    print("Failed to install the Hermes compatibility sidecar.")
    return 1


def compat_remove_command(container, args: argparse.Namespace) -> int:
    from harness_asset_manager.runtime.hermes_compat import remove_hermes_compat, status
    if status(container.hermes_root) == "not-detected":
        print(_NOT_DETECTED)
        return 0
    if remove_hermes_compat(container.hermes_root):
        print("Removed.")
        return 0
    print("Failed to remove the Hermes compatibility sidecar.")
    return 1
