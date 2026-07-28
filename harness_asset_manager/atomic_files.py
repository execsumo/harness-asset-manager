from __future__ import annotations

import fcntl
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def atomic_write_text(path: Path, content: str, *, follow_symlinks: bool = False) -> None:
    """Write ``content`` to ``path`` via a temp file and ``os.replace``.

    ``os.replace`` onto a symlink **destroys the symlink** and leaves a regular file
    in its place — the same mechanism by which a harness's own atomic editor breaks a
    binding we created. So the default refuses a symlink destination outright: any
    future caller pointed at a binding path fails loudly instead of silently orphaning
    the store entry.

    ``follow_symlinks=True`` is the opt-in for the legitimate case — writing a
    harness-owned config file that the *user* has symlinked into a dotfiles repo. There
    we resolve the link and replace the real file behind it, so their symlink survives.
    """
    if path.is_symlink():
        if not follow_symlinks:
            raise ValueError(
                f"refusing to atomically write over the symlink at {path}: "
                "os.replace would destroy the link. Pass follow_symlinks=True to "
                "write through it instead."
            )
        path = Path(os.path.realpath(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


@contextmanager
def file_lock(lock_path: Path) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "w") as lock_fd:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
