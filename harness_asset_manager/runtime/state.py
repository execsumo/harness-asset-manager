from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from harness_asset_manager.paths import resolve_app_paths


@dataclass(frozen=True)
class RuntimeState:
    pid: int
    host: str
    port: int
    base_url: str
    version: str
    executable: str
    started_at: float


def runtime_state_path(env: dict[str, str] | None = None) -> Path:
    return resolve_app_paths(env).runtime_state_path


def runtime_log_path(env: dict[str, str] | None = None) -> Path:
    return resolve_app_paths(env).server_log_path


def load_runtime_state(env: dict[str, str] | None = None) -> RuntimeState | None:
    path = runtime_state_path(env)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        return RuntimeState(
            pid=int(payload["pid"]),
            host=str(payload["host"]),
            port=int(payload["port"]),
            base_url=str(payload["base_url"]),
            version=str(payload["version"]),
            executable=str(payload["executable"]),
            started_at=float(payload.get("started_at", time.time())),
        )
    except (OSError, ValueError, KeyError, TypeError):
        return None


def write_runtime_state(state: RuntimeState, env: dict[str, str] | None = None) -> Path:
    path = runtime_state_path(env)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload_bytes = (json.dumps(asdict(state), indent=2, sort_keys=True) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(str(path), flags, 0o600)
    try:
        with open(fd, "wb", closefd=False) as f:
            f.write(payload_bytes)
            f.flush()
    finally:
        os.close(fd)
    path.chmod(0o600)
    return path


def clear_runtime_state(env: dict[str, str] | None = None) -> None:
    path = runtime_state_path(env)
    if path.exists():
        path.unlink()
