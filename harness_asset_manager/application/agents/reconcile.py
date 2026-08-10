from __future__ import annotations

import time
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from harness_asset_manager.application.drift import (
    classify_drift as classify_drift_by_baseline,
)
from harness_asset_manager.atomic_files import atomic_write_text, file_lock
from harness_asset_manager.hashing import hash_file, hash_text

from .adapters import (
    AgentHarnessAdapter,
    TargetResolver,
    parse_codex_agent,
    render_codex_agent,
)
from .audit import AgentAuditLog, AuditEntry
from .ledger import AgentBindingLedger, AgentBindingRecord, build_record
from .model import AgentParseError
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
        default_harnesses: Callable[[], tuple[str, ...]] | None = None,
    ) -> None:
        self.store = store
        self._resolve = resolve
        self.ledger = ledger
        self.audit = audit
        self.conflicts_root = conflicts_root
        self._is_enabled = is_enabled
        self.lock_path = lock_path
        self._default_harnesses = default_harnesses or (lambda: ())

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
                    if adapter.renders:
                        agent = self.store.get(slug)
                        if agent is None or record.rendered_sha256 is None:
                            continue
                        store_sha256 = _safe_hash_text(render_codex_agent(agent))
                        baseline_sha256 = record.rendered_sha256
                    else:
                        store_sha256 = _safe_hash(store_path)
                        baseline_sha256 = record.store_sha256

                    kind = classify_drift_by_baseline(
                        baseline_sha256=baseline_sha256,
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

                        if item.adapter.renders:
                            agent = self.store.get(slug)
                            if agent is None:
                                continue
                            item.adapter.enable(agent)
                        else:
                            item.binding_path.unlink()
                            item.binding_path.symlink_to(item.store_path.resolve())
                        self.ledger.upsert(
                            slug,
                            build_record(
                                harness=item.harness_id,
                                store_path=item.store_path,
                                rendered_path=item.binding_path if item.adapter.renders else None,
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

                        # Step 2: ingest the edited document, preserving Codex-only
                        # TOML fields outside the shared Markdown store.
                        primary_adapter = primary_item.adapter
                        try:
                            if primary_adapter.renders:
                                parsed = parse_codex_agent(primary_item.binding_path)
                                self.store.write_codex_agent(
                                    slug,
                                    name=parsed.name,
                                    description=parsed.description,
                                    prompt=parsed.prompt,
                                    extras=dict(parsed.extras),
                                )
                            else:
                                self.store.write_raw(slug, document)
                                self.store.write_codex_extras(slug, {})
                        except (AgentParseError, OSError, tomllib.TOMLDecodeError) as error:
                            now = time.time()
                            actions.append(
                                AuditEntry(
                                    at=now,
                                    ref=slug,
                                    harness=primary_item.harness_id,
                                    action="refused",
                                    detail=f"failed to adopt harness file: {error}",
                                )
                            )
                            issues.append((slug, f"failed to adopt harness file: {error}"))
                            continue

                        # Step 3: verify the store faithfully captured the harness
                        # file. Markdown and Codex TOML cannot share a byte hash, so
                        # Codex uses a semantic TOML comparison instead.
                        if primary_adapter.renders:
                            stored_agent = self.store.get(slug)
                            verified = stored_agent is not None and _codex_equivalent(
                                render_codex_agent(stored_agent), document
                            )
                        else:
                            verified = _safe_hash(primary_item.store_path) == primary_item.harness_sha256
                        if not verified:
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
                            if item.adapter.renders:
                                agent = self.store.get(slug)
                                if agent is None:
                                    continue
                                item.adapter.enable(agent)
                            else:
                                item.binding_path.unlink()
                                item.binding_path.symlink_to(item.store_path.resolve())
                            self.ledger.upsert(
                                slug,
                                build_record(
                                    harness=item.harness_id,
                                    store_path=item.store_path,
                                    rendered_path=item.binding_path if item.adapter.renders else None,
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
                        self._enable_defaults(slug, adapters, drifted, actions, issues, now)

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

    def _enable_defaults(
        self,
        slug: str,
        adapters: dict[str, AgentHarnessAdapter],
        already_handled: list[_DriftInfo],
        actions: list[AuditEntry],
        issues: list[tuple[str, str]],
        now: float,
    ) -> None:
        handled = {item.harness_id for item in already_handled}
        agent = self.store.get(slug)
        if agent is None:
            return
        for harness in self._default_harnesses():
            if harness in handled:
                continue
            adapter = adapters.get(harness)
            if adapter is None:
                continue
            try:
                if adapter.is_enabled(slug):
                    continue
                adapter.enable(agent)
                self.ledger.upsert(
                    slug,
                    build_record(
                        harness=harness,
                        store_path=agent.path,
                        rendered_path=adapter.binding_path(slug) if adapter.renders else None,
                        now=now,
                    ),
                )
                actions.append(
                    AuditEntry(
                        at=now,
                        ref=slug,
                        harness=harness,
                        action="adopted",
                        detail="enabled the configured auto-adopt default harness",
                    )
                )
            except Exception as error:  # noqa: BLE001 — preserve the adopted source
                issues.append((slug, f"could not enable default harness {harness}: {error}"))


def _safe_hash(path: Path) -> str | None:
    try:
        return hash_file(path)
    except OSError:
        return None


def _safe_hash_text(text: str) -> str | None:
    try:
        return hash_text(text)
    except (UnicodeEncodeError, AttributeError):
        return None


def _codex_equivalent(rendered: str, original: str) -> bool:
    try:
        return tomllib.loads(rendered) == tomllib.loads(original)
    except tomllib.TOMLDecodeError:
        return False


__all__ = ["AgentReconcileService", "ReconcileOutcome"]
