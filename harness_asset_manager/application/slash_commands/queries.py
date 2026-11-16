from __future__ import annotations

import threading
from collections.abc import Callable

from harness_asset_manager.application.asset_archive import AssetArchiveStore

from .read_models import SlashCommandReadModelService


class SlashCommandQueryService:
    def __init__(
        self,
        read_models: SlashCommandReadModelService,
        reconcile: Callable[[], object] | None = None,
        archive: AssetArchiveStore | None = None,
    ) -> None:
        self.archive = archive
        self.read_models = read_models
        self._reconcile = reconcile
        # Reentrancy guard, per thread. The reconcile pass itself reads through this
        # service: the drift-repair path builds its mutation payloads via
        # ``get_command``, which would otherwise trigger ``reconcile`` again — one
        # nested full pass per repaired command (O(N^2) scans, N-deep recursion, and
        # unbounded if drift persists across passes). Mirrors the guard on
        # SkillsQueryService; sync API endpoints run in a threadpool over one shared
        # service instance, so the guard must be thread-local, not an instance flag.
        self._reconcile_state = threading.local()

    def set_reconcile(self, reconcile: Callable[[], object] | None) -> None:
        self._reconcile = reconcile

    def _reconcile_once(self) -> None:
        if self._reconcile is None or getattr(self._reconcile_state, "active", False):
            return
        self._reconcile_state.active = True
        try:
            self._reconcile()
        finally:
            self._reconcile_state.active = False

    def list_commands(self, *, include_archived: bool = False) -> dict[str, object]:
        self._reconcile_once()
        payload = self.read_models.list_commands()
        archived = self.archive.load() if self.archive else set()
        commands = payload["commands"]
        assert isinstance(commands, list)
        for command in commands:
            command["archived"] = f"slash_commands:{command['name']}" in archived
        payload["commands"] = [command for command in commands if include_archived or not command["archived"]]
        return payload

    def get_command(self, name: str) -> dict[str, object] | None:
        self._reconcile_once()
        result = self.read_models.get_command(name)
        if result is not None:
            result["archived"] = bool(self.archive and self.archive.is_archived("slash_commands", name))
        return result


__all__ = ["SlashCommandQueryService"]
