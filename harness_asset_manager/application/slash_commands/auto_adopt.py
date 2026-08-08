from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Callable

from harness_asset_manager.application.auto_adopt import record_auto_adopt
from harness_asset_manager.application.mutation_audit import MutationAuditJournal

from .codecs import parse_slash_command_document
from .models import SlashCommand, SlashTarget
from .mutations import SlashCommandMutationService
from .read_models import SlashCommandReadModelService


class SlashCommandsAutoAdoptService:
    """Adopt new command files only when every observed copy is equivalent."""

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


def _equivalent(observations: list[tuple[SlashTarget, Path, SlashCommand]]) -> bool:
    first = observations[0][2]
    return all(
        command.description == first.description
        and command.prompt == first.prompt
        and command.frontmatter == first.frontmatter
        for _target, _path, command in observations[1:]
    )


__all__ = ["SlashCommandsAutoAdoptService"]
