from __future__ import annotations

from harness_asset_manager.errors import MutationError
from harness_asset_manager.harness import HarnessKernelService, HarnessSupportStore

from ..invalidation import InvalidationFanout


class SettingsMutationService:
    def __init__(
        self,
        harness_kernel: HarnessKernelService,
        support_store: HarnessSupportStore,
        invalidation: InvalidationFanout,
    ) -> None:
        self.harness_kernel = harness_kernel
        self.support_store = support_store
        self.invalidation = invalidation

    def set_harness_support(self, harness: str, enabled: bool) -> dict[str, object]:
        if not self.harness_kernel.is_known_harness(harness):
            raise MutationError(f"unknown harness: {harness}", status=404)
        self.support_store.set_enabled(harness, enabled)
        self.invalidation.invalidate_all()
        return {"ok": True, "enabled": enabled}
