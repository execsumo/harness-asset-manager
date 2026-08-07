from __future__ import annotations

import inspect
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harness_asset_manager.atomic_files import file_lock

AuditOutcome = str
PathSpec = tuple[Path, bool]

_DEFAULT_READ_LIMIT_BYTES = 1024 * 1024

_SAFE_PARAMETER_NAMES = {
    "action",
    "enabled",
    "family",
    "harness",
    "harnesses",
    "id",
    "name",
    "observed_harness",
    "on_conflict",
    "qualified_name",
    "ref",
    "skill_ref",
    "source_kind",
    "source_locator",
    "target",
    "targets",
}


@dataclass(frozen=True)
class _PathState:
    kind: str
    size: int
    modified_ns: int
    link_target: str | None = None


class MutationPathTracker:
    """Find paths actually changed within small, family-specific filesystem scopes.

    A path spec's boolean selects recursive traversal. Harness binding directories are
    scanned one level deep; the managed snapshot directory is small and recursive.
    File contents are never read, which keeps secrets out of both memory and the log.
    """

    def __init__(self, resolve_paths: Callable[[], tuple[PathSpec, ...]]) -> None:
        self._resolve_paths = resolve_paths

    def snapshot(self) -> dict[Path, _PathState]:
        states: dict[Path, _PathState] = {}
        for root, recursive in self._resolve_paths():
            self._capture(root, recursive=recursive, states=states)
        return states

    def changed_paths(
        self,
        before: Mapping[Path, _PathState],
        after: Mapping[Path, _PathState],
    ) -> tuple[str, ...]:
        changed = {path for path in set(before) | set(after) if before.get(path) != after.get(path)}
        # If a changed directory contains a more precise changed entry, report the
        # entry rather than both it and its parent directory.
        precise = {
            path
            for path in changed
            if not (
                self._kind(path, before, after) == "directory"
                and any(other != path and other.is_relative_to(path) for other in changed)
            )
        }
        return tuple(str(path) for path in sorted(precise, key=str))

    def _capture(
        self,
        path: Path,
        *,
        recursive: bool,
        states: dict[Path, _PathState],
    ) -> None:
        state = _path_state(path)
        if state is None:
            return
        states[path] = state
        if state.kind != "directory":
            return
        try:
            children = tuple(path.iterdir())
        except OSError:
            return
        for child in children:
            child_state = _path_state(child)
            if child_state is None:
                continue
            states[child] = child_state
            if recursive and child_state.kind == "directory":
                self._capture(child, recursive=True, states=states)

    @staticmethod
    def _kind(
        path: Path,
        before: Mapping[Path, _PathState],
        after: Mapping[Path, _PathState],
    ) -> str | None:
        state = after.get(path) or before.get(path)
        return state.kind if state is not None else None


class MutationAuditJournal:
    """Append-only JSON Lines journal shared by the HTTP API and headless CLI."""

    def __init__(
        self,
        path: Path,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = path
        self._now = now or (lambda: datetime.now(timezone.utc))

    @property
    def lock_path(self) -> Path:
        return self.path.with_suffix(self.path.suffix + ".lock")

    def append(
        self,
        *,
        family: str,
        operation: str,
        parameters: Mapping[str, object],
        target_paths: tuple[str, ...],
        outcome: AuditOutcome,
        error_type: str | None = None,
    ) -> None:
        event: dict[str, object] = {
            "version": 1,
            "timestamp": self._now().astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "family": family,
            "operation": operation,
            "parameters": dict(parameters),
            "targetPaths": list(target_paths),
            "outcome": outcome,
        }
        if error_type is not None:
            event["errorType"] = error_type
        line = json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with file_lock(self.lock_path):
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(line)
                stream.flush()
                os.fsync(stream.fileno())

    def read_recent(
        self,
        limit: int = 100,
        *,
        max_bytes: int = _DEFAULT_READ_LIMIT_BYTES,
    ) -> tuple[dict[str, object], ...]:
        if limit <= 0 or not self.path.is_file():
            return ()
        if max_bytes <= 0:
            return ()
        try:
            with self.path.open("rb") as stream:
                stream.seek(0, os.SEEK_END)
                end = stream.tell()
                start = max(0, end - max_bytes)
                stream.seek(start)
                payload = stream.read(max_bytes)
        except OSError:
            return ()

        # A bounded tail may begin in the middle of a line. Drop that fragment;
        # a concurrently appended trailing fragment is rejected by JSON parsing.
        if start:
            separator = payload.find(b"\n")
            if separator < 0:
                return ()
            payload = payload[separator + 1 :]

        events: list[dict[str, object]] = []
        for line in reversed(payload.splitlines()):
            try:
                event = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(event, dict):
                events.append(event)
                if len(events) == limit:
                    break
        return tuple(reversed(events))


class AuditedMutationService:
    """Transparent proxy that journals selected public methods on a domain service."""

    def __init__(
        self,
        service: object,
        *,
        family: str,
        methods: set[str] | None = None,
        journal: MutationAuditJournal,
        path_tracker: MutationPathTracker,
        record_noop: bool = True,
    ) -> None:
        object.__setattr__(self, "_service", service)
        object.__setattr__(self, "_family", family)
        object.__setattr__(
            self,
            "_methods",
            frozenset(methods if methods is not None else _public_methods(service)),
        )
        object.__setattr__(self, "_journal", journal)
        object.__setattr__(self, "_path_tracker", path_tracker)
        object.__setattr__(self, "_record_noop", record_noop)

    def __getattr__(self, name: str) -> Any:
        value = getattr(self._service, name)
        if name not in self._methods or not callable(value):
            return value

        def audited(*args: object, **kwargs: object) -> object:
            before = self._path_tracker.snapshot()
            parameters = _safe_parameters(value, args, kwargs)
            try:
                result = value(*args, **kwargs)
            except Exception as error:
                after = self._path_tracker.snapshot()
                self._append_safely(
                    operation=name,
                    parameters=parameters,
                    target_paths=self._path_tracker.changed_paths(before, after),
                    outcome="failed",
                    error_type=error.__class__.__name__,
                )
                raise
            after = self._path_tracker.snapshot()
            target_paths = self._path_tracker.changed_paths(before, after)
            if self._record_noop or target_paths:
                self._append_safely(
                    operation=name,
                    parameters=parameters,
                    target_paths=target_paths,
                    outcome=_result_outcome(result),
                )
            return result

        return audited

    def __setattr__(self, name: str, value: object) -> None:
        if name.startswith("_"):
            object.__setattr__(self, name, value)
            return
        setattr(self._service, name, value)

    def _append_safely(self, **event: object) -> None:
        # A completed config mutation must never be reported as failed merely because
        # its audit disk is full; reporting failure invites an unsafe retry.
        try:
            self._journal.append(family=self._family, **event)  # type: ignore[arg-type]
        except OSError:
            return


def _path_state(path: Path) -> _PathState | None:
    try:
        stat = path.lstat()
    except OSError:
        return None
    if path.is_symlink():
        try:
            target = os.readlink(path)
        except OSError:
            target = None
        return _PathState("symlink", stat.st_size, stat.st_mtime_ns, target)
    if path.is_dir():
        return _PathState("directory", stat.st_size, stat.st_mtime_ns)
    return _PathState("file", stat.st_size, stat.st_mtime_ns)


def _public_methods(service: object) -> set[str]:
    return {
        name
        for name in dir(service)
        if not name.startswith("_") and callable(getattr(service, name, None))
    }


def _safe_parameters(
    method: Callable[..., object],
    args: tuple[object, ...],
    kwargs: Mapping[str, object],
) -> dict[str, object]:
    try:
        bound = inspect.signature(method).bind_partial(*args, **kwargs)
    except (TypeError, ValueError):
        return {}
    safe: dict[str, object] = {}
    for name, value in bound.arguments.items():
        if name in _SAFE_PARAMETER_NAMES:
            normalized = _safe_value(value)
            if normalized is not None:
                safe[name] = normalized
            continue
        if name in {"spec", "command", "request", "req"}:
            identity = _object_identity(value)
            if identity is not None:
                safe["subject"] = identity
    return safe


def _safe_value(value: object) -> object | None:
    if isinstance(value, (str, bool, int, float)) or value is None:
        return value
    if isinstance(value, (list, tuple, set)) and all(isinstance(item, str) for item in value):
        return list(value)
    return None


def _object_identity(value: object) -> str | None:
    for attribute in ("id", "slug", "name", "asset_type"):
        candidate = getattr(value, attribute, None)
        if isinstance(candidate, str) and candidate:
            return candidate
    return None


def _result_outcome(result: object) -> AuditOutcome:
    if isinstance(result, Mapping) and result.get("ok") is False:
        succeeded = result.get("succeeded")
        return "partial" if isinstance(succeeded, list) and succeeded else "refused"
    failed = getattr(result, "failed", None)
    succeeded = getattr(result, "succeeded", None)
    if failed:
        return "partial" if succeeded else "refused"
    skipped = getattr(result, "skipped", None)
    adopted = getattr(result, "adopted", None)
    if skipped:
        return "partial" if adopted else "refused"
    if isinstance(result, tuple) and len(result) == 2 and result[1]:
        return "partial" if result[0] else "refused"
    return "succeeded"


__all__ = [
    "AuditedMutationService",
    "MutationAuditJournal",
    "MutationPathTracker",
]
