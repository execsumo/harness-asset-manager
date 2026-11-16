"""Ownership of the harness default-policy settings that adopting a denylist touches.

A denylist only works as the sole policy when the harness stops prompting for
unlisted actions, so enabling a permission may set a harness-wide default (Claude
``permissions.defaultMode``, Antigravity ``toolPermission``, Cursor ``approvalMode``,
Codex ``default_permissions`` and ``approval_policy``). Enable never overwrites a
value the user already set. What it found and what it wrote are recorded per
harness, outside the harness config, so disable restores exactly what was there
instead of guessing ownership from the current value.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from harness_asset_manager.atomic_files import atomic_write_text, file_lock

PolicyKey = tuple[str, ...]
# Dotted key -> {"previous": value it held before enable (absent when unset),
#                "written": value the app wrote (absent when the app left it alone)}
PolicyRecord = dict[str, dict[str, object]]

CURRENT_DEFAULT_POLICY_VERSION = 1

_ABSENT = object()


def default_policy_path(permissions_manifest: Path) -> Path:
    return permissions_manifest.with_name("default-policy.json")


def _get(document: Mapping[str, object], key: PolicyKey) -> object:
    node: object = document
    for part in key:
        if not isinstance(node, Mapping) or part not in node:
            return _ABSENT
        node = node[part]
    return node


def _set(document: dict[str, object], key: PolicyKey, value: object) -> None:
    node = document
    for part in key[:-1]:
        child = node.get(part)
        if not isinstance(child, dict):
            child = {}
            node[part] = child
        node = child
    node[key[-1]] = value


def _pop(document: dict[str, object], key: PolicyKey) -> None:
    node: object = document
    for part in key[:-1]:
        if not isinstance(node, dict):
            return
        node = node.get(part)
    if isinstance(node, dict):
        node.pop(key[-1], None)


def claim_default_policy(
    document: dict[str, object],
    key: PolicyKey,
    value: object,
    record: PolicyRecord,
    *,
    legacy: bool,
    allowed: bool = True,
) -> bool:
    """Set ``key`` to ``value`` unless the user owns it. Returns whether the app owns it.

    ``legacy`` means rules the app wrote before ownership was recorded are already in
    the file. Enable used to set the default unconditionally then, so a current value
    equal to the app's is the app's own write.
    """
    dotted = ".".join(key)
    entry = record.get(dotted)
    current = _get(document, key)
    if entry is not None and "written" in entry:
        # The app introduced this key; re-enable re-applies it.
        if current != value:
            _set(document, key, value)
        entry["written"] = value
        return True
    if current is _ABSENT:
        if not allowed:
            return False
        _set(document, key, value)
        record[dotted] = {"written": value}
        return True
    if entry is None and legacy and current == value:
        record[dotted] = {"written": value}
        return True
    record[dotted] = {"previous": current}
    return False


def owns_default_policy(record: PolicyRecord, key: PolicyKey) -> bool:
    return "written" in record.get(".".join(key), {})


def release_default_policy(document: dict[str, object], record: PolicyRecord) -> None:
    """Restore every default the app wrote, unless the user has changed it since."""
    for dotted, entry in record.items():
        if "written" not in entry:
            continue
        key = tuple(dotted.split("."))
        if _get(document, key) != entry["written"]:
            continue
        if "previous" in entry:
            _set(document, key, entry["previous"])
        else:
            _pop(document, key)


class DefaultPolicyStore:
    """Per-harness default-policy records, next to the permissions manifest."""

    def __init__(self, path: Path) -> None:
        self.path = path

    @property
    def _lock_path(self) -> Path:
        return self.path.with_suffix(".lock")

    def get(self, harness: str) -> PolicyRecord | None:
        record = self._load().get(harness)
        if not isinstance(record, dict):
            return None
        return {
            str(key): dict(entry)
            for key, entry in record.items()
            if isinstance(entry, dict)
        }

    def put(self, harness: str, record: PolicyRecord) -> None:
        with file_lock(self._lock_path):
            harnesses = self._load()
            harnesses[harness] = record
            self._write(harnesses)

    def clear(self, harness: str) -> None:
        with file_lock(self._lock_path):
            harnesses = self._load()
            if harnesses.pop(harness, None) is not None:
                self._write(harnesses)

    def _load(self) -> dict[str, object]:
        if not self.path.is_file():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        harnesses = payload.get("harnesses") if isinstance(payload, dict) else None
        return dict(harnesses) if isinstance(harnesses, dict) else {}

    def _write(self, harnesses: Mapping[str, object]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self.path,
            json.dumps(
                {"version": CURRENT_DEFAULT_POLICY_VERSION, "harnesses": dict(harnesses)},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )


__all__ = [
    "DefaultPolicyStore",
    "PolicyKey",
    "PolicyRecord",
    "claim_default_policy",
    "default_policy_path",
    "owns_default_policy",
    "release_default_policy",
]
