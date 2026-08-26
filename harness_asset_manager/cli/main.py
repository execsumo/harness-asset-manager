from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
from typing import TYPE_CHECKING, Callable

from harness_asset_manager import __version__
from harness_asset_manager.platform_context import _isolate_state_dir_environment
from harness_asset_manager.runtime.browser import maybe_open_browser
from harness_asset_manager.runtime.process import (
    is_owned_runtime_process,
    terminate_process,
)
from harness_asset_manager.runtime.startup import (
    startup_timeout_seconds,
    wait_for_health,
)
from harness_asset_manager.runtime.state import (
    RuntimeState,
    clear_runtime_state,
    load_runtime_state,
    runtime_log_path,
    write_runtime_state,
)

from . import commands
from .support import CliError, asset_flags

if TYPE_CHECKING:
    from harness_asset_manager.application import BackendContainer

AssetHandler = Callable[["BackendContainer", argparse.Namespace], int]

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
RUNTIME_COMMANDS = {"serve", "start", "stop", "status"}
COMMANDS = RUNTIME_COMMANDS | commands.GROUP_NAMES


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="harness-asset-manager",
        description=(
            "Run the local harness-asset-manager app, or manage harness assets headlessly "
            "from the command line."
        ),
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser("serve", help="Run the app server in the foreground.")
    add_server_options(serve_parser)

    start_parser = subparsers.add_parser("start", help="Launch one managed background app instance.")
    add_server_options(start_parser)

    stop_parser = subparsers.add_parser("stop", help="Stop the managed background app instance.")
    stop_parser.add_argument("--state-dir", help="Isolate this run in one directory (config, data, state) so nothing else is touched.")

    status_parser = subparsers.add_parser("status", help="Show status for the managed background instance.")
    status_parser.add_argument("--state-dir", help="Isolate this run in one directory (config, data, state) so nothing else is touched.")

    common = asset_flags()


    commands.register(subparsers, common)

    return parser


def add_server_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", default=DEFAULT_PORT, type=int)
    parser.add_argument(
        "--frontend-dist",
        default=None,
        help="Override the frontend build directory for this launch.",
    )
    parser.add_argument(
        "--open-browser",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Open the browser automatically after startup.",
    )
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help=(
            "Permit binding a non-loopback --host. WARNING: the API has no authentication; "
            "anyone who can reach the port can mutate local harness config."
        ),
    )
    parser.add_argument("--state-dir", help="Isolate this run in one directory (config, data, state) so nothing else is touched.")
    parser.add_argument("--socket-fd", type=int, help=argparse.SUPPRESS)


def normalize_argv(argv: list[str] | None) -> list[str]:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        return ["serve"]
    first = args[0]
    if first in COMMANDS or first in {"-h", "--help", "--version"}:
        return args
    return ["serve", *args]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(normalize_argv(argv))
    handler = getattr(args, "handler", None)
    if handler is not None:
        return run_asset_command(handler, args)
    if args.command == "start":
        return start_command(args)
    if args.command == "stop":
        return stop_command(args)
    if args.command == "status":
        return status_command(args)
    return serve_command(args)


def run_asset_command(handler: AssetHandler, args: argparse.Namespace) -> int:
    """Run one asset command against a freshly built backend container.

    The container is built here rather than in each handler so every command gets the
    same store migrations, harness resolution and ``--state-dir`` handling the server
    gets. Stores serialize their own writes with ``flock``, so this is safe to run
    while the app is serving; the server's read models carry a one-second TTL and pick
    the change up on their next request.
    """
    from harness_asset_manager.application import build_backend_container
    from harness_asset_manager.errors import MarketplaceUpstreamError, MutationError

    env = runtime_env(getattr(args, "state_dir", None))
    try:
        container = build_backend_container(env)
    except (CliError, MutationError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    try:
        return handler(container, args)
    except (CliError, MutationError, MarketplaceUpstreamError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except (BrokenPipeError, KeyboardInterrupt):
        # `harnessam skills list | head` and Ctrl-C are both ordinary, not crashes.
        return 130
    finally:
        # Marketplace metadata refreshes run on a thread pool; without this the process
        # waits on them at exit even though nothing is going to read the result.
        try:
            container.skills_marketplace_catalog.close()
        except Exception:  # pragma: no cover - shutdown is best-effort
            pass


def guard_remote_host(args: argparse.Namespace) -> int | None:
    """Refuse non-loopback binds unless the operator opted in with --allow-remote."""
    from harness_asset_manager.api.guards import is_loopback_host

    if is_loopback_host(args.host):
        return None
    if not args.allow_remote:
        print(
            f"error: refusing to bind non-loopback host {args.host!r}.\n"
            "The harness-asset-manager API has no authentication and can mutate local files. "
            "Pass --allow-remote only on a network you fully trust.",
            file=sys.stderr,
        )
        return 2
    print(
        f"WARNING: serving the unauthenticated harness-asset-manager API on {args.host!r}; "
        "anyone who can reach this port can mutate local harness configuration.",
        file=sys.stderr,
    )
    return None


def serve_command(args: argparse.Namespace) -> int:
    from harness_asset_manager.application import build_backend_container
    from harness_asset_manager.runtime.server import serve_foreground

    refusal = guard_remote_host(args)
    if refusal is not None:
        return refusal
    env = runtime_env(args.state_dir)
    container = build_backend_container(env)
    prebound_socket = socket.socket(fileno=args.socket_fd) if args.socket_fd is not None else None
    return serve_foreground(
        container,
        host=args.host,
        port=args.port,
        frontend_dist=args.frontend_dist,
        open_browser=args.open_browser,
        allow_remote=args.allow_remote,
        prebound_socket=prebound_socket,
    )


def start_command(args: argparse.Namespace) -> int:
    from harness_asset_manager.runtime.server import bind_socket

    refusal = guard_remote_host(args)
    if refusal is not None:
        return refusal
    env = runtime_env(args.state_dir)
    existing = load_runtime_state(env)
    if existing is not None and is_owned_runtime_process(existing):
        print(f"harness-asset-manager is already running at {existing.base_url} (pid {existing.pid})")
        maybe_open_browser(existing.base_url, enabled=args.open_browser)
        return 0
    if existing is not None:
        clear_runtime_state(env)

    socket_handle, actual_host, port = bind_socket(args.host, args.port)
    url = f"http://{actual_host}:{port}"
    log_path = runtime_log_path(env)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = self_command(
        "serve",
        "--host",
        args.host,
        "--port",
        str(port),
        "--socket-fd",
        str(socket_handle.fileno()),
        "--no-open-browser",
        *(["--allow-remote"] if args.allow_remote else []),
        *frontend_dist_args(args.frontend_dist),
        *state_dir_args(args.state_dir),
    )
    try:
        with log_path.open("ab") as log_file:
            process = subprocess.Popen(
                command,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                cwd=os.getcwd(),
                env=env,
                pass_fds=(socket_handle.fileno(),),
                start_new_session=True,
            )
    finally:
        socket_handle.close()
    timeout_seconds = startup_timeout_seconds()
    if not wait_for_health(url, timeout_seconds=timeout_seconds):
        terminate_process(process.pid)
        print(
            f"harness-asset-manager failed to start within {timeout_seconds:.0f} seconds. See log: {log_path}",
            file=sys.stderr,
        )
        return 1

    write_runtime_state(
        RuntimeState(
            pid=process.pid,
            host=args.host,
            port=port,
            base_url=url,
            version=__version__,
            executable=sys.executable,
            started_at=time.time(),
        ),
        env,
    )
    print(f"harness-asset-manager started at {url} (pid {process.pid})")
    maybe_open_browser(url, enabled=args.open_browser)
    return 0


def stop_command(args: argparse.Namespace) -> int:
    env = runtime_env(args.state_dir)
    state = load_runtime_state(env)
    if state is None:
        print("harness-asset-manager is not running.")
        return 0
    if not is_owned_runtime_process(state):
        clear_runtime_state(env)
        print("No managed harness-asset-manager background instance is running.")
        return 0
    terminate_process(state.pid)
    clear_runtime_state(env)
    print(f"Stopped harness-asset-manager at {state.base_url} (pid {state.pid})")
    return 0


def status_command(args: argparse.Namespace) -> int:
    env = runtime_env(args.state_dir)
    state = load_runtime_state(env)
    if state is None:
        print("harness-asset-manager is not running.")
        return 0
    if not is_owned_runtime_process(state):
        clear_runtime_state(env)
        print("harness-asset-manager is not running.")
        return 0
    print(f"harness-asset-manager is running at {state.base_url} (pid {state.pid})")
    return 0


def runtime_env(state_dir: str | None) -> dict[str, str]:
    env = dict(os.environ)
    if state_dir:
        env = _isolate_state_dir_environment(env, state_dir)
    return env


def self_command(*args: str) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    return [sys.executable, "-m", "harness_asset_manager", *args]


def frontend_dist_args(frontend_dist: str | None) -> list[str]:
    if not frontend_dist:
        return []
    return ["--frontend-dist", frontend_dist]


def state_dir_args(state_dir: str | None) -> list[str]:
    if not state_dir:
        return []
    return ["--state-dir", state_dir]
