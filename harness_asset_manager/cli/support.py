"""Argument plumbing shared by the asset commands."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


class CliError(Exception):
    """A user-facing refusal — printed as ``error: <message>`` with exit code 1."""


def asset_flags() -> argparse.ArgumentParser:
    """Flags every asset command accepts, attached via ``parents=``."""
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit the raw JSON payload instead of a table.",
    )
    parent.add_argument("--state-dir", help="Isolate this run in one directory (config, data, state) so nothing else is touched.")
    return parent


def add_harness_flag(parser: argparse.ArgumentParser, *, help: str = "Harness id (e.g. claude, codex).") -> None:
    parser.add_argument("--harness", required=True, help=help)


def add_target_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--target",
        required=True,
        choices=("enabled", "disabled"),
        help="State to apply to every interactive harness cell.",
    )


def add_confirmation_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt (required when stdin is not a terminal).",
    )


def confirm(action: str, *, assume_yes: bool) -> None:
    """Gate a destructive command behind a prompt, or ``--yes`` when scripted."""
    if assume_yes:
        return
    if not sys.stdin.isatty():
        raise CliError(f"refusing to {action} without confirmation; pass --yes to proceed non-interactively")
    answer = input(f"{action}? [y/N] ").strip().lower()
    if answer not in {"y", "yes"}:
        raise CliError("aborted")


def read_text_argument(inline: str | None, path: str | None, *, label: str) -> str:
    """Resolve a body given as ``--x`` or ``--x-file`` (``-`` reads stdin)."""
    if inline is not None and path is not None:
        raise CliError(f"pass either --{label} or --{label}-file, not both")
    if inline is not None:
        return inline
    if path is None:
        raise CliError(f"--{label} or --{label}-file is required")
    if path == "-":
        return sys.stdin.read()
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as error:
        raise CliError(f"cannot read --{label}-file {path}: {error}") from error


def parse_json_argument(raw: str | None, *, label: str) -> dict[str, object] | None:
    """Parse a JSON object passed on the command line (``@file`` reads a file)."""
    if raw is None:
        return None
    text = raw
    if raw.startswith("@"):
        source = raw[1:]
        if source == "-":
            text = sys.stdin.read()
        else:
            try:
                text = Path(source).read_text(encoding="utf-8")
            except OSError as error:
                raise CliError(f"cannot read {label} file {source}: {error}") from error
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as error:
        raise CliError(f"{label} is not valid JSON: {error}") from error
    if not isinstance(parsed, dict):
        raise CliError(f"{label} must be a JSON object")
    return parsed


__all__ = [
    "CliError",
    "add_confirmation_flag",
    "add_harness_flag",
    "add_target_flag",
    "asset_flags",
    "confirm",
    "parse_json_argument",
    "read_text_argument",
]
