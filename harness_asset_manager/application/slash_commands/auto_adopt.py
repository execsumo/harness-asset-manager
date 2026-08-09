from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Callable

from harness_asset_manager.application.auto_adopt import (
    record_auto_adopt,
    record_auto_repair,
)
from harness_asset_manager.application.drift import classify_drift
from harness_asset_manager.application.mutation_audit import MutationAuditJournal
from harness_asset_manager.errors import MutationError
from harness_asset_manager.hashing import hash_text

from .codecs import parse_slash_command_document, render_slash_command
from .models import SlashCommand, SlashTarget
from .mutations import SlashCommandMutationService
from .read_models import SlashCommandReadModelService
from .sync_state import hash_file


class SlashCommandsAutoAdoptService:
    """Adopt new command files, and repair already-managed ones that drifted.

    Two distinct mechanisms behind one setting, matching how the rest of the
    family-wide 2026-08-08 auto-adoption work is gated: a single ``autoAdopt``
    toggle per family covers every safe automatic ownership change for that
    family, rather than growing a setting per mechanism.
    """

    def __init__(
        self,
        *,
        read_models: SlashCommandReadModelService,
        mutations: SlashCommandMutationService,
        is_enabled: Callable[[], bool],
        journal: MutationAuditJournal,
    ) -> None:
        self.read_models = read_models
        self.mutations = mutations
        self.is_enabled = is_enabled
        self.journal = journal

    def reconcile(self) -> None:
        if not self.is_enabled():
            return
        self._adopt_unmanaged()
        self._repair_drift()

    def _adopt_unmanaged(self) -> None:
        targets = self.read_models.resolve_targets()
        target_by_id = {target.id: target for target in targets}
        rows = self.read_models.review_commands()
        grouped: dict[str, list[tuple[SlashTarget, Path, SlashCommand]]] = defaultdict(list)
        for row in rows:
            if row.get("kind") != "unmanaged" or row.get("commandExists") or row.get("error") is not None:
                continue
            target = target_by_id.get(str(row.get("target")))
            if target is None:
                continue
            try:
                path = Path(str(row["path"]))
                parsed = parse_slash_command_document(
                    str(row["name"]),
                    path.read_text(encoding="utf-8"),
                    target.render_format,
                )
            except Exception:
                continue
            grouped[str(row["name"])].append((target, path, parsed))

        for name, observations in grouped.items():
            if not observations or not _equivalent(observations):
                continue
            try:
                self.mutations.auto_adopt_unmanaged(
                    name=name,
                    observations=[(target, command) for target, _path, command in observations],
                )
            except Exception as error:  # noqa: BLE001 — leave the row for review
                record_auto_adopt(
                    self.journal,
                    family="slash_commands",
                    ref=name,
                    target_paths=(str(path) for _target, path, _command in observations),
                    outcome="failed",
                    error_type=error.__class__.__name__,
                )
                continue
            record_auto_adopt(
                self.journal,
                family="slash_commands",
                ref=name,
                target_paths=(str(path) for _target, path, _command in observations),
            )

    def _repair_drift(self) -> None:
        """Auto-repair already-managed slash commands whose target file drifted.

        Reuses the exact review actions a user would click manually
        (``restore_managed`` / ``adopt_target``) rather than reimplementing the
        writes — only the *decision* of when it is safe to press that button
        automatically is new here. Mirrors the agents family's Stage 3 reconcile:
        never auto-resolve a two-sided conflict, never act without a usable
        baseline hash.
        """
        targets = self.read_models.resolve_targets()
        target_by_id = {target.id: target for target in targets}
        state = self.mutations.sync_state.load()
        for name, records in state.items():
            command = self.mutations.store.get_command(name)
            if command is None:
                # Orphaned tracked record with no store command behind it; not this
                # pass's concern (the review rows already surface it).
                continue
            for target_id, record in records.items():
                if record.content_hash is None:
                    continue
                target = target_by_id.get(target_id)
                if target is None:
                    continue
                try:
                    path = self.mutations.path_policy.tracked_path(target, record.path)
                except MutationError:
                    continue
                if not path.is_file():
                    continue
                harness_sha256 = _safe_hash(path)
                if harness_sha256 is None or harness_sha256 == record.content_hash:
                    continue  # unreadable, or not actually drifted
                store_sha256 = hash_text(render_slash_command(command, target.render_format))
                kind = classify_drift(
                    baseline_sha256=record.content_hash,
                    harness_sha256=harness_sha256,
                    store_sha256=store_sha256,
                )
                if kind == "clobber_clean":
                    self._repair_one(target=target, name=name, action="restore_managed", path=path)
                elif kind == "clobber_one_sided":
                    self._repair_one(target=target, name=name, action="adopt_target", path=path)
                # "collision" and "two_sided_conflict" stay for manual review.

    def _repair_one(self, *, target: SlashTarget, name: str, action: str, path: Path) -> None:
        try:
            self.mutations.review_resolver.resolve_review_command(
                target=target,
                name=name,
                action=action,  # type: ignore[arg-type]
            )
        except Exception as error:  # noqa: BLE001 — leave the row for manual review
            record_auto_repair(
                self.journal,
                family="slash_commands",
                ref=name,
                action=action,
                target_paths=(str(path),),
                outcome="failed",
                error_type=error.__class__.__name__,
            )
            return
        record_auto_repair(
            self.journal,
            family="slash_commands",
            ref=name,
            action=action,
            target_paths=(str(path),),
        )


def _safe_hash(path: Path) -> str | None:
    try:
        return hash_file(path)
    except OSError:
        return None


def _equivalent(observations: list[tuple[SlashTarget, Path, SlashCommand]]) -> bool:
    first = observations[0][2]
    return all(
        command.description == first.description
        and command.prompt == first.prompt
        and command.frontmatter == first.frontmatter
        for _target, _path, command in observations[1:]
    )


__all__ = ["SlashCommandsAutoAdoptService"]
