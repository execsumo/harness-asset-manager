from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from threading import Condition

from harness_asset_manager.errors import MutationError
from harness_asset_manager.harness import HarnessKernelService

from .adapters import build_skills_adapters, scan_all_adapters
from .contracts import SkillsHarnessAdapter, SkillsHarnessStatus
from .observations import SkillsHarnessScan, SkillStoreScan
from .package import SkillPackageCache
from .store import SkillStore


@dataclass(frozen=True)
class SkillsReadModelSnapshot:
    store_scan: SkillStoreScan
    harness_scans: tuple[SkillsHarnessScan, ...]


@dataclass(frozen=True)
class _CachedSnapshot:
    snapshot: SkillsReadModelSnapshot
    captured_at: float


class SkillsReadModelService:
    def __init__(
        self,
        *,
        store: SkillStore,
        adapters: tuple[SkillsHarnessAdapter, ...],
        kernel: HarnessKernelService,
        snapshot_ttl_seconds: float = 1.0,
        package_cache: SkillPackageCache | None = None,
    ) -> None:
        self.store = store
        self.adapters = adapters
        self.kernel = kernel
        self.snapshot_ttl_seconds = snapshot_ttl_seconds
        self.package_cache = package_cache or store.package_cache
        self._cache: _CachedSnapshot | None = None
        self._condition = Condition()
        self._building = False
        self._generation = 0

    @classmethod
    def from_kernel(
        cls,
        *,
        store: SkillStore,
        kernel: HarnessKernelService,
        data_dir: Path | None = None,
    ) -> "SkillsReadModelService":
        package_cache = store.package_cache
        return cls(
            store=store,
            adapters=build_skills_adapters(
                kernel,
                data_dir=data_dir,
                package_cache=package_cache,
            ),
            kernel=kernel,
            package_cache=package_cache,
        )

    def find_adapter(self, harness: str) -> SkillsHarnessAdapter | None:
        return next((adapter for adapter in self.adapters if adapter.harness == harness), None)

    def visible_harnesses(self) -> tuple[str, ...]:
        return self.kernel.enabled_harness_ids_for_family("skills")

    def enabled_harnesses(self) -> tuple[str, ...]:
        return self.visible_harnesses()

    def enabled_adapters(self) -> tuple[SkillsHarnessAdapter, ...]:
        enabled = set(self.enabled_harnesses())
        return tuple(adapter for adapter in self.adapters if adapter.harness in enabled)

    def enabled_installed_adapters(self) -> tuple[SkillsHarnessAdapter, ...]:
        return tuple(adapter for adapter in self.enabled_adapters() if adapter.status().installed)

    def all_adapters(self) -> tuple[SkillsHarnessAdapter, ...]:
        return self.adapters

    def require_enabled_adapter(self, harness: str) -> SkillsHarnessAdapter:
        adapter = self.find_adapter(harness)
        if adapter is None:
            raise MutationError(f"unknown harness: {harness}", status=400)
        if harness not in self.enabled_harnesses():
            raise MutationError(f"harness support is disabled: {harness}", status=400)
        status = adapter.status()
        if not status.installed:
            raise MutationError(f"{adapter.label} is not installed or not available on PATH", status=400)
        return adapter

    def harness_statuses(self) -> tuple[SkillsHarnessStatus, ...]:
        return tuple(adapter.status() for adapter in self.adapters)

    def visible_scans(
        self,
        snapshot: SkillsReadModelSnapshot | None = None,
    ) -> tuple[SkillsHarnessScan, ...]:
        current = snapshot or self.snapshot()
        visible = set(self.visible_harnesses())
        return tuple(scan for scan in current.harness_scans if scan.harness in visible)

    def snapshot(self) -> SkillsReadModelSnapshot:
        while True:
            with self._condition:
                cached = self._cache
                if (
                    cached is not None
                    and (time.monotonic() - cached.captured_at)
                    < self.snapshot_ttl_seconds
                ):
                    return cached.snapshot
                if self._building:
                    self._condition.wait()
                    continue
                self._building = True
                generation = self._generation

            try:
                cache_cycle = self.package_cache.new_validation_cycle()
                with ThreadPoolExecutor(max_workers=2) as executor:
                    store_future = executor.submit(
                        self.store.scan,
                        cache_cycle=cache_cycle,
                    )
                    adapters_future = executor.submit(
                        scan_all_adapters,
                        self.adapters,
                        cache_cycle=cache_cycle,
                    )
                    snapshot = SkillsReadModelSnapshot(
                        store_scan=store_future.result(),
                        harness_scans=adapters_future.result(),
                    )
            except BaseException:
                with self._condition:
                    self._building = False
                    self._condition.notify_all()
                raise

            with self._condition:
                self._building = False
                if generation == self._generation:
                    self._cache = _CachedSnapshot(
                        snapshot=snapshot,
                        captured_at=time.monotonic(),
                    )
                    self._condition.notify_all()
                    return snapshot
                self._condition.notify_all()

    def invalidate(self) -> None:
        with self._condition:
            self._generation += 1
            self._cache = None
            self._condition.notify_all()
        self.package_cache.invalidate()
        for adapter in self.adapters:
            adapter.invalidate()


__all__ = ["SkillsReadModelService", "SkillsReadModelSnapshot"]
