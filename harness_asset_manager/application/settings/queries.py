from __future__ import annotations

from harness_asset_manager.harness import HarnessKernelService
from harness_asset_manager.paths import AppPaths

from .auto_adopt import AutoAdoptStore
from .presenters import settings_payload


class SettingsQueryService:
    def __init__(
        self,
        harness_kernel: HarnessKernelService,
        paths: AppPaths,
        auto_adopt_store: AutoAdoptStore,
    ) -> None:
        self.harness_kernel = harness_kernel
        self.paths = paths
        self.auto_adopt_store = auto_adopt_store

    def get_settings(self) -> dict[str, object]:
        return settings_payload(
            paths=self.paths,
            platform=self.harness_kernel.context.platform,
            harness_statuses=self.harness_kernel.harness_statuses(),
            enabled_harnesses=self.harness_kernel.enabled_harness_ids(),
            auto_adopt=self.auto_adopt_store.preferences(),
            auto_adopt_harnesses=self.auto_adopt_store.default_harnesses(),
            auto_adopt_harness_options={
                family: tuple(
                    binding.definition.harness
                    for binding in self.harness_kernel.bindings_for_family(family)
                )
                for family in self.auto_adopt_store.default_harnesses()
            },
        )
