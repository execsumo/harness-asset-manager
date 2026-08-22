from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from harness_asset_manager.application.drift import DriftKind
from harness_asset_manager.application.drift import (
    classify_drift as _classify_drift_by_baseline,
)
from harness_asset_manager.atomic_files import atomic_write_text, file_lock
from harness_asset_manager.hashing import hash_file, hash_text
from harness_asset_manager.portable_paths import from_portable_path, to_portable_path

LEDGER_VERSION = 1


@dataclass(frozen=True)
class AgentBindingRecord:
    """Evidence that Harness Asset Manager once bound ``slug`` into ``harness``.

    A **cache, never a source of truth.** ``is_enabled()`` keeps deriving from the
    filesystem; this only adds the one fact the filesystem cannot retain — that a
    binding existed here, and what the store held at the moment it was made. Without
    it a clobbered binding and a name collision are the same observation.
    """

    harness: str
    target: Path
    linked_at: float
    store_sha256: str | None = None
    # renders harnesses only: what we wrote out, plus enough stat to skip re-hashing it.
    rendered_sha256: str | None = None
    rendered_size: int | None = None
    rendered_mtime_ns: int | None = None

    def to_dict(self, *, home: Path | None = None) -> dict[str, object]:
        return {
            "target": to_portable_path(self.target, home=home),
            "linkedAt": self.linked_at,
            "storeSha256": self.store_sha256,
            "renderedSha256": self.rendered_sha256,
            "renderedSize": self.rendered_size,
            "renderedMtimeNs": self.rendered_mtime_ns,
        }


# slug -> harness -> record
AgentBindingLedgerState = dict[str, dict[str, AgentBindingRecord]]


class AgentBindingLedger:
    """``bindings.json``: which agents we linked where, and against what content.

    Modelled on ``SlashCommandSyncStateStore``, which solves the same problem for
    slash commands. Every read path is total: an absent, truncated, or malformed file
    loads as "no records", and a record that fails validation is dropped rather than
    raising. That is invariant 4 of ``plan-auto-adoption.md`` — losing the ledger must
    degrade to the pre-ledger behaviour (prompt the user), never to a destructive
    default.
    """

    def __init__(
        self,
        path: Path,
        *,
        home: Path | None = None,
        extra_local_roots: tuple[Path, ...] = (),
    ) -> None:
        self.path = path
        self.home = home
        self.extra_local_roots = extra_local_roots

    @property
    def lock_path(self) -> Path:
        return self.path.with_suffix(".lock")

    # -- reads --------------------------------------------------------------

    def load(self) -> AgentBindingLedgerState:
        if not self.path.is_file():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # Truncated or corrupt: behave exactly as if we had never recorded anything.
            return {}
        if not isinstance(payload, dict):
            return {}
        agents_payload = payload.get("agents")
        if not isinstance(agents_payload, dict):
            return {}
        state: AgentBindingLedgerState = {}
        for slug, harness_payload in agents_payload.items():
            if not isinstance(slug, str) or not isinstance(harness_payload, dict):
                continue
            records: dict[str, AgentBindingRecord] = {}
            for harness, raw_record in harness_payload.items():
                record = _parse_record(
                    str(harness),
                    raw_record,
                    home=self.home,
                    extra_local_roots=self.extra_local_roots,
                )
                if record is not None:
                    records[record.harness] = record
            if records:
                state[slug] = records
        return state

    def record_for(self, slug: str, harness: str) -> AgentBindingRecord | None:
        return self.load().get(slug, {}).get(harness)

    # -- writes -------------------------------------------------------------

    def write(self, state: AgentBindingLedgerState) -> None:
        payload = {
            "version": LEDGER_VERSION,
            "agents": {
                slug: {
                    harness: record.to_dict(home=self.home)
                    for harness, record in sorted(records.items())
                }
                for slug, records in sorted(state.items())
                if records
            },
        }
        atomic_write_text(self.path, json.dumps(payload, indent=2, sort_keys=True) + "\n")

    def upsert(self, slug: str, record: AgentBindingRecord) -> None:
        with file_lock(self.lock_path):
            state = self.load()
            records = dict(state.get(slug, {}))
            records[record.harness] = record
            state[slug] = records
            self.write(state)

    def forget(self, slug: str, harness: str) -> None:
        with file_lock(self.lock_path):
            state = self.load()
            records = dict(state.get(slug, {}))
            if records.pop(harness, None) is None:
                return
            if records:
                state[slug] = records
            else:
                state.pop(slug, None)
            self.write(state)

    def forget_slug(self, slug: str) -> None:
        with file_lock(self.lock_path):
            state = self.load()
            if state.pop(slug, None) is None:
                return
            self.write(state)

    def rebaseline(self, slug: str, harnesses: tuple[str, ...], store_sha256: str) -> None:
        """Re-record the store hash for bindings that are **still live**.

        Called after Harness Asset Manager itself writes the store file. A live binding
        is a symlink, so the harness is already reading the new content — re-baselining
        keeps a later clobber classifiable as one-sided.

        The caller decides liveness, and that restriction is the whole safety argument:
        re-baselining an *already clobbered* binding would make an independent store
        edit look like "the store never moved", turning a genuine two-sided conflict
        into an automatic adopt that discards the store edit.
        """
        if not harnesses:
            return
        with file_lock(self.lock_path):
            state = self.load()
            records = dict(state.get(slug, {}))
            changed = False
            for harness in harnesses:
                record = records.get(harness)
                if record is None or record.store_sha256 == store_sha256:
                    continue
                records[harness] = AgentBindingRecord(
                    harness=record.harness,
                    target=record.target,
                    linked_at=record.linked_at,
                    store_sha256=store_sha256,
                    rendered_sha256=record.rendered_sha256,
                    rendered_size=record.rendered_size,
                    rendered_mtime_ns=record.rendered_mtime_ns,
                )
                changed = True
            if not changed:
                return
            state[slug] = records
            self.write(state)


def build_record(
    *,
    harness: str,
    store_path: Path,
    rendered_path: Path | None = None,
    now: float | None = None,
) -> AgentBindingRecord:
    """Snapshot the evidence for a binding we just made.

    ``rendered_path`` is passed only for ``renders`` harnesses (Codex), where the
    harness copy is a real file we wrote rather than a symlink into the store.
    """
    rendered_sha256: str | None = None
    rendered_size: int | None = None
    rendered_mtime_ns: int | None = None
    if rendered_path is not None:
        try:
            stat = rendered_path.stat()
            rendered_sha256 = hash_file(rendered_path)
            rendered_size = stat.st_size
            rendered_mtime_ns = stat.st_mtime_ns
        except OSError:
            rendered_sha256 = None
    return AgentBindingRecord(
        harness=harness,
        target=store_path,
        linked_at=time.time() if now is None else now,
        store_sha256=_safe_hash(store_path),
        rendered_sha256=rendered_sha256,
        rendered_size=rendered_size,
        rendered_mtime_ns=rendered_mtime_ns,
    )


def classify_drift(
    *,
    record: AgentBindingRecord | None,
    harness_sha256: str | None,
    store_sha256: str | None,
) -> DriftKind:
    """The decision table of ``plan-auto-adoption.md`` §4, as a pure function.

    Thin wrapper over the family-agnostic table in ``application.drift``: this is
    only the agents-specific step of turning a ``record`` into the baseline hash
    that table actually compares against. Deliberately has no filesystem access and
    takes no action — Stage 2 only names what happened. Whether a classification is
    *acted on* is a separate decision, made by a caller that knows about user
    settings and destructive operations.
    """
    baseline_sha256 = record.store_sha256 if record is not None else None
    return _classify_drift_by_baseline(
        baseline_sha256=baseline_sha256,
        harness_sha256=harness_sha256,
        store_sha256=store_sha256,
    )


def _safe_hash(path: Path) -> str | None:
    try:
        return hash_file(path)
    except OSError:
        return None


def _parse_record(
    harness: str,
    raw_record: object,
    *,
    home: Path | None = None,
    extra_local_roots: tuple[Path, ...] = (),
) -> AgentBindingRecord | None:
    if not isinstance(raw_record, dict) or not harness:
        return None
    target_raw = raw_record.get("target")
    linked_at = raw_record.get("linkedAt")
    if not isinstance(target_raw, str) or not isinstance(linked_at, (int, float)):
        return None
    target = from_portable_path(target_raw, home=home, extra_local_roots=extra_local_roots)
    if target is None:
        return None
    return AgentBindingRecord(
        harness=harness,
        target=target,
        linked_at=float(linked_at),
        store_sha256=_optional_str(raw_record.get("storeSha256")),
        rendered_sha256=_optional_str(raw_record.get("renderedSha256")),
        rendered_size=_optional_int(raw_record.get("renderedSize")),
        rendered_mtime_ns=_optional_int(raw_record.get("renderedMtimeNs")),
    )


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


__all__ = [
    "AgentBindingLedger",
    "AgentBindingLedgerState",
    "AgentBindingRecord",
    "DriftKind",
    "LEDGER_VERSION",
    "build_record",
    "classify_drift",
    "hash_file",
    "hash_text",
]
