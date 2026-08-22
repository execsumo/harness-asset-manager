from __future__ import annotations

import threading
from collections.abc import Callable

from .read_models import SlashCommandReadModelService


class SlashCommandQueryService:
    def __init__(
        self,
        read_models: SlashCommandReadModelService,
        reconcile: Callable[[], object] | None = None,
    ) -> None:
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

    def list_commands(self) -> dict[str, object]:
        self._reconcile_once()
        return self.read_models.list_commands()

    def get_command(self, name: str) -> dict[str, object] | None:
        self._reconcile_once()
        return self.read_models.get_command(name)


__all__ = ["SlashCommandQueryService"]
