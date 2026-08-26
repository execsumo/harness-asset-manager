from __future__ import annotations

from .service import ConfigsService


class ConfigsMutationService:
    def __init__(self, service: ConfigsService) -> None:
        self.service = service

    def capture(self, explicit: bool = False) -> None:
        self.service.capture(explicit=explicit)

    def restore(self, harness: str) -> None:
        self.service.restore(harness)

    def enable(self, harness: str) -> None:
        self.service.enable(harness)

    def disable(self, harness: str) -> None:
        self.service.disable(harness)
