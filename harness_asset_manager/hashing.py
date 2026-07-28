from __future__ import annotations

import hashlib
from pathlib import Path

HASH_PREFIX = "sha256"


def hash_bytes(payload: bytes) -> str:
    return f"{HASH_PREFIX}:{hashlib.sha256(payload).hexdigest()}"


def hash_text(payload: str) -> str:
    return hash_bytes(payload.encode("utf-8"))


def hash_file(path: Path) -> str:
    """Content hash of a file, in the prefixed form every ledger on disk stores.

    The prefix is load-bearing: it is what lets a stored hash be recognised as
    ``sha256`` rather than silently compared against a differently-computed digest
    if the algorithm ever changes.
    """
    return hash_bytes(path.read_bytes())


__all__ = ["HASH_PREFIX", "hash_bytes", "hash_file", "hash_text"]
