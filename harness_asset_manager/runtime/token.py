from __future__ import annotations

import os
import secrets

from harness_asset_manager.paths import AppPaths, resolve_app_paths


def resolve_api_token(paths: AppPaths | None = None, env: dict[str, str] | None = None) -> str:
    """Read the API bearer token from env or store, generating and persisting if absent."""
    active_env = env if env is not None else os.environ
    override = active_env.get("HARNESSAM_API_TOKEN", "").strip()
    if override:
        return override

    resolved_paths = paths if paths is not None else resolve_app_paths(env)
    token_path = resolved_paths.api_token_path

    if token_path.is_file():
        try:
            token = token_path.read_text(encoding="utf-8").strip()
            if token:
                return token
        except OSError:
            pass

    return rotate_api_token(resolved_paths)


def rotate_api_token(paths: AppPaths) -> str:
    """Generate a new secure API token and persist it with 0600 permissions."""
    token = secrets.token_urlsafe(32)
    path = paths.api_token_path
    path.parent.mkdir(parents=True, exist_ok=True)
    payload_bytes = (token + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(str(path), flags, 0o600)
    try:
        with open(fd, "wb", closefd=False) as f:
            f.write(payload_bytes)
            f.flush()
    finally:
        os.close(fd)
    path.chmod(0o600)
    return token
