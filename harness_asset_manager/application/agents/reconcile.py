from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from harness_asset_manager.atomic_files import atomic_write_text, file_lock
from harness_asset_manager.hashing import hash_file

from .adapters import AgentHarnessAdapter, TargetResolver
from .audit import AgentAuditLog, AuditEntry
from .ledger import AgentBindingLedger, AgentBindingRecord, build_record, classify_drift
from .store import AgentStore


@dataclass(frozen=True)
class ReconcileOutcome:
    actions: tuple[AuditEntry, ...]
    issues: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class _DriftInfo:
    harness_id: str
    adapter: AgentHarnessAdapter
    binding_path: Path
    record: AgentBindingRecord
    kind: str
    harness_sha256: str
    store_path: Path
    store_sha256: str | None


class AgentReconcileService:
    """Auto-repairs provably-safe agent binding drift.

    Runs on list requests. Must be cheap, idempotent, and take no action it cannot
    prove is safe.
    """

    def __init__(
        self,
        store: AgentStore,
        resolve: TargetResolver,
        ledger: AgentBindingLedger,
        audit: AgentAuditLog,
        conflicts_root: Path,
        is_enabled: Callable[[], bool],
        lock_path: Path,
    ) -> None:
        self.store = store
        self._resolve = resolve
        self.ledger = ledger
        self.audit = audit
        self.conflicts_root = conflicts_root
        self._is_enabled = is_enabled
        self.lock_path = lock_path

    def reconcile(self) -> ReconcileOutcome:
        if not self._is_enabled():
            return ReconcileOutcome((), ())

        with file_lock(self.lock_path):
            state = self.ledger.load()
            if not state:
                return ReconcileOutcome((), ())

            targets, adapters = self._resolve()
            supported_target_ids = {t.id for t in targets if t.supports_agents}

            actions: list[AuditEntry] = []
            issues: list[tuple[str, str]] = []

            for slug, slug_records in state.items():
                drifted: list[_DriftInfo] = []
                has_two_sided_conflict = False

                for harness_id, record in slug_records.items():
                    if harness_id not in supported_target_ids or harness_id not in adapters:
                        continue
                    adapter = adapters[harness_id]
                    if adapter.renders:
                        # Skip Codex entirely (Invariant 3)
                        continue

                    binding_path = adapter.binding_path(slug)
                    if binding_path.is_symlink():
                        # Intact symlink -> skip (no hashing)
                        continue
                    if not binding_path.exists() or not binding_path.is_file():
                        # Missing, dangling, or non-file -> skip
                        continue

                    # Real file -> hash it and store file, classify drift
                    harness_sha256 = _safe_hash(binding_path)
                    store_path = self.store.path_for(slug)
                    store_sha256 = _safe_hash(store_path)

                    kind = classify_drift(
                        record=record,
                        harness_sha256=harness_sha256,
                        store_sha256=store_sha256,
                    )

                    if kind == "two_sided_conflict":
                        has_two_sided_conflict = True
                        break
                    elif kind in ("clobber_clean", "clobber_one_sided") and harness_sha256 is not None:
                        drifted.append(
                            _DriftInfo(
                                harness_id=harness_id,
                                adapter=adapter,
                                binding_path=binding_path,
                                record=record,
                                kind=kind,
                                harness_sha256=harness_sha256,
                                store_path=store_path,
                                store_sha256=store_sha256,
                            )
                        )

                # Decision step per slug
                if has_two_sided_conflict or not drifted:
                    # Do nothing for this whole slug. Emit no issue here, record nothing in audit log.
                    continue

                clean_items = [d for d in drifted if d.kind == "clobber_clean"]
                one_sided_items = [d for d in drifted if d.kind == "clobber_one_sided"]

                if len(one_sided_items) == 0:
                    # All clobber_clean -> relink each
                    now = time.time()
                    for item in clean_items:
                        current_hash = _safe_hash(item.binding_path)
                        if current_hash != item.store_sha256:
                            actions.append(
                                AuditEntry(
                                    at=now,
                                    ref=slug,
                                    harness=item.harness_id,
                                    action="refused",
                                    detail=f"harness file changed before relinking {item.binding_path.name}",
                                )
                            )
                            continue

                        item.binding_path.unlink()
                        item.binding_path.symlink_to(item.store_path.resolve())
                        self.ledger.upsert(
                            slug,
                            build_record(
                                harness=item.harness_id,
                                store_path=item.store_path,
                                now=now,
                            ),
                        )
                        actions.append(
                            AuditEntry(
                                at=now,
                                ref=slug,
                                harness=item.harness_id,
                                action="relinked",
                                detail="restored the link; content was identical",
                            )
                        )

                else:
                    unique_hashes = {item.harness_sha256 for item in one_sided_items}
                    if len(unique_hashes) == 1:
                        # Adopt that copy into store, then relink every drifted binding for the slug
                        primary_item = one_sided_items[0]
                        try:
                            document = primary_item.binding_path.read_text(encoding="utf-8")
                        except OSError as error:
                            now = time.time()
                            actions.append(
                                AuditEntry(
                                    at=now,
                                    ref=slug,
                                    harness=primary_item.harness_id,
                                    action="refused",
                                    detail=f"failed to read harness file: {error}",
                                )
                            )
                            issues.append((slug, f"failed to read harness file: {error}"))
                            continue

                        # Step 2: store.write_raw
                        self.store.write_raw(slug, document)

                        # Step 3: verify store file hash equals harness file's hash
                        store_hash_after = _safe_hash(primary_item.store_path)
                        if store_hash_after != primary_item.harness_sha256:
                            now = time.time()
                            actions.append(
                                AuditEntry(
                                    at=now,
                                    ref=slug,
                                    harness=primary_item.harness_id,
                                    action="refused",
                                    detail="store write verification failed during auto-adopt",
                                )
                            )
                            issues.append((slug, "store write verification failed during auto-adopt"))
                            continue

                        # Step 4: unlink each harness copy and recreate symlink; upsert fresh ledger record
                        now = time.time()
                        for item in drifted:
                            # Re-verify immediately before deleting, exactly as the
                            # all-clean path does. Between classification and here a
                            # harness may have written again, and that later edit was
                            # never weighed by the decision above — deleting it would
                            # discard content nothing has seen.
                            if _safe_hash(item.binding_path) != item.harness_sha256:
                                actions.append(
                                    AuditEntry(
                                        at=now,
                                        ref=slug,
                                        harness=item.harness_id,
                                        action="refused",
                                        detail=(
                                            "harness file changed again while adopting; "
                                            "left it in place"
                                        ),
                                    )
                                )
                                continue
                            item.binding_path.unlink()
                            item.binding_path.symlink_to(item.store_path.resolve())
                            self.ledger.upsert(
                                slug,
                                build_record(
                                    harness=item.harness_id,
                                    store_path=item.store_path,
                                    now=now,
                                ),
                            )

                        # Step 5: Audit entries
                        for item in one_sided_items:
                            actions.append(
                                AuditEntry(
                                    at=now,
                                    ref=slug,
                                    harness=item.harness_id,
                                    action="adopted",
                                    detail="adopted edited harness copy into store and restored link",
                                )
                            )
                        for item in clean_items:
                            actions.append(
                                AuditEntry(
                                    at=now,
                                    ref=slug,
                                    harness=item.harness_id,
                                    action="relinked",
                                    detail="restored link after adopting store content",
                                )
                            )

                    else:
                        # Several clobber_one_sided with differing hashes -> do not auto-resolve
                        now = time.time()
                        self.conflicts_root.mkdir(parents=True, exist_ok=True)
                        harness_names = sorted(item.harness_id for item in one_sided_items)

                        for item in one_sided_items:
                            conflict_file = self.conflicts_root / f"{slug}.{item.harness_id}.md"
                            already_preserved = (
                                conflict_file.is_file()
                                and _safe_hash(conflict_file) == item.harness_sha256
                            )

                            if not already_preserved:
                                try:
                                    content = item.binding_path.read_text(encoding="utf-8")
                                    atomic_write_text(conflict_file, content)
                                    actions.append(
                                        AuditEntry(
                                            at=now,
                                            ref=slug,
                                            harness=item.harness_id,
                                            action="conflict_preserved",
                                            detail=f"preserved conflicting copy to {conflict_file.name}",
                                        )
                                    )
                                except OSError as error:
                                    actions.append(
                                        AuditEntry(
                                            at=now,
                                            ref=slug,
                                            harness=item.harness_id,
                                            action="refused",
                                            detail=f"failed to preserve conflict copy: {error}",
                                        )
                                    )

                        issues.append(
                            (
                                slug,
                                f"conflicting edits in multiple harnesses ({', '.join(harness_names)}); preserved copies in conflicts directory",
                            )
                        )

            if actions:
                self.audit.append(actions)

            return ReconcileOutcome(actions=tuple(actions), issues=tuple(issues))


def _safe_hash(path: Path) -> str | None:
    try:
        return hash_file(path)
    except OSError:
        return None


__all__ = ["AgentReconcileService", "ReconcileOutcome"]
