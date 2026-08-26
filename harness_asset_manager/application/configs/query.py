from __future__ import annotations

from typing import Any

from .service import ConfigsService


class ConfigsQueryService:
    def __init__(self, service: ConfigsService) -> None:
        self.service = service

    def list_configs(self) -> dict[str, Any]:
        return self.service.list()

    def get_diff(self, harness: str) -> dict[str, Any]:
        return self.service.diff(harness)
