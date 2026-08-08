from __future__ import annotations

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

    def set_reconcile(self, reconcile: Callable[[], object] | None) -> None:
        self._reconcile = reconcile

    def list_commands(self) -> dict[str, object]:
        if self._reconcile is not None:
            self._reconcile()
        return self.read_models.list_commands()

    def get_command(self, name: str) -> dict[str, object] | None:
        if self._reconcile is not None:
            self._reconcile()
        return self.read_models.get_command(name)


__all__ = ["SlashCommandQueryService"]
