from __future__ import annotations

from harness_asset_manager.errors import MutationError
from harness_asset_manager.harness import HarnessKernelService, HarnessSupportStore

from ..invalidation import InvalidationFanout
from .auto_adopt import AutoAdoptStore


class SettingsMutationService:
    def __init__(
        self,
        harness_kernel: HarnessKernelService,
        support_store: HarnessSupportStore,
        invalidation: InvalidationFanout,
        auto_adopt_store: AutoAdoptStore,
    ) -> None:
        self.harness_kernel = harness_kernel
        self.support_store = support_store
        self.invalidation = invalidation
        self.auto_adopt_store = auto_adopt_store

    def set_harness_support(self, harness: str, enabled: bool) -> dict[str, object]:
        if not self.harness_kernel.is_known_harness(harness):
            raise MutationError(f"unknown harness: {harness}", status=404)
        self.support_store.set_enabled(harness, enabled)
        self.invalidation.invalidate_all()
        return {"ok": True, "enabled": enabled}

    def set_auto_adopt(self, family: str, enabled: bool) -> dict[str, object]:
        try:
            preferences = self.auto_adopt_store.set_enabled(family, enabled)
        except KeyError:
            raise MutationError(f"unknown asset family: {family}", status=404) from None
        except ValueError as error:
            raise MutationError(str(error), status=400) from error
        self.invalidation.invalidate_all()
        return {"ok": True, "autoAdopt": preferences}
