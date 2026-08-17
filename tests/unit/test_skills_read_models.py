from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from unittest.mock import Mock, patch

from harness_asset_manager.application.skills.observations import SkillStoreScan
from harness_asset_manager.application.skills.package import SkillPackageCache
from harness_asset_manager.application.skills.read_models import SkillsReadModelService


class _BlockingStore:
    def __init__(self, *, fail_first: bool = False) -> None:
        self.package_cache = SkillPackageCache()
        self.started = Event()
        self.release = Event()
        self.calls = 0
        self._lock = Lock()
        self._fail_first = fail_first

    def scan(self, *, cache_cycle: int | None = None) -> SkillStoreScan:
        del cache_cycle
        with self._lock:
            self.calls += 1
            call = self.calls
        if call == 1:
            self.started.set()
            self.release.wait(timeout=5)
            if self._fail_first:
                raise RuntimeError("scan failed")
        return SkillStoreScan(packages=(), issues=(str(call),))


class _ReentrantStore:
    def __init__(self) -> None:
        self.package_cache = SkillPackageCache()
        self.service: SkillsReadModelService | None = None

    def scan(self, *, cache_cycle: int | None = None) -> SkillStoreScan:
        del cache_cycle
        assert self.service is not None
        self.service.snapshot()
        raise AssertionError("reentrant snapshot unexpectedly returned")


class SkillsReadModelTests(unittest.TestCase):
    def _service(self, store: _BlockingStore) -> SkillsReadModelService:
        return SkillsReadModelService(
            store=store,  # type: ignore[arg-type]
            adapters=(),
            kernel=Mock(),
            snapshot_ttl_seconds=60,
        )

    def test_concurrent_cache_misses_build_one_snapshot(self) -> None:
        store = _BlockingStore()
        service = self._service(store)
        waiters_present = Event()
        waiter_count = 0
        waiter_lock = Lock()
        original_wait = service._condition.wait

        def tracked_wait(*args, **kwargs):
            nonlocal waiter_count
            with waiter_lock:
                waiter_count += 1
                if waiter_count == 2:
                    waiters_present.set()
            return original_wait(*args, **kwargs)

        with (
            patch.object(
                service._condition,
                "wait",
                side_effect=tracked_wait,
            ),
            ThreadPoolExecutor(max_workers=3) as executor,
        ):
            futures = [executor.submit(service.snapshot) for _ in range(3)]
            self.assertTrue(store.started.wait(timeout=2))
            self.assertTrue(waiters_present.wait(timeout=2))
            self.assertEqual(store.calls, 1)
            store.release.set()
            snapshots = [future.result(timeout=5) for future in futures]

        self.assertEqual(store.calls, 1)
        self.assertTrue(all(snapshot is snapshots[0] for snapshot in snapshots))

    def test_invalidation_during_build_discards_and_rebuilds_snapshot(self) -> None:
        store = _BlockingStore()
        service = self._service(store)

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(service.snapshot)
            self.assertTrue(store.started.wait(timeout=2))
            service.invalidate()
            store.release.set()
            snapshot = future.result(timeout=5)

        self.assertEqual(store.calls, 2)
        self.assertEqual(snapshot.store_scan.issues, ("2",))

    def test_failed_build_releases_waiter_and_waiter_retry_succeeds(self) -> None:
        store = _BlockingStore(fail_first=True)
        service = self._service(store)
        waiter_present = Event()
        original_wait = service._condition.wait

        def tracked_wait(*args, **kwargs):
            waiter_present.set()
            return original_wait(*args, **kwargs)

        with (
            patch.object(
                service._condition,
                "wait",
                side_effect=tracked_wait,
            ),
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            failed = executor.submit(service.snapshot)
            self.assertTrue(store.started.wait(timeout=2))
            retry = executor.submit(service.snapshot)
            self.assertTrue(waiter_present.wait(timeout=2))
            store.release.set()
            with self.assertRaisesRegex(RuntimeError, "scan failed"):
                failed.result(timeout=5)
            snapshot = retry.result(timeout=5)

        self.assertEqual(store.calls, 2)
        self.assertEqual(snapshot.store_scan.issues, ("2",))

    def test_snapshot_reentrancy_is_rejected_instead_of_deadlocking(self) -> None:
        store = _ReentrantStore()
        service = SkillsReadModelService(
            store=store,  # type: ignore[arg-type]
            adapters=(),
            kernel=Mock(),
        )
        store.service = service

        with self.assertRaisesRegex(RuntimeError, "not reentrant"):
            service.snapshot()


if __name__ == "__main__":
    unittest.main()
