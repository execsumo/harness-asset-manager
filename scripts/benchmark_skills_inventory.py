#!/usr/bin/env python3
"""Read-only benchmark for cold and unchanged skills inventory snapshots."""

from __future__ import annotations

import argparse
import os
import statistics
import time

from harness_asset_manager.application.skills.read_models import SkillsReadModelService
from harness_asset_manager.application.skills.store import SkillStore
from harness_asset_manager.harness import HarnessKernelService, HarnessSupportStore
from harness_asset_manager.paths import resolve_app_paths


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=5)
    args = parser.parse_args()
    if args.iterations < 2:
        parser.error("--iterations must be at least 2")

    active_env = dict(os.environ)
    paths = resolve_app_paths(active_env)
    kernel = HarnessKernelService.from_environment(
        active_env,
        support_store=HarnessSupportStore(paths.settings_path),
    )
    store = SkillStore(
        paths.skills_store_root,
        manifest_path=paths.skills_store_manifest,
    )
    service = SkillsReadModelService.from_kernel(
        store=store,
        kernel=kernel,
        data_dir=paths.data_dir,
    )
    # A zero snapshot TTL starts a new validation cycle on every call without
    # clearing the package cache. The benchmark never writes to a skill root.
    service.snapshot_ttl_seconds = 0

    elapsed: list[float] = []
    snapshot = None
    for _ in range(args.iterations):
        started = time.perf_counter()
        snapshot = service.snapshot()
        elapsed.append(time.perf_counter() - started)

    assert snapshot is not None
    observations = sum(len(scan.skills) for scan in snapshot.harness_scans)
    print(f"store packages: {len(snapshot.store_scan.packages)}")
    print(f"harness observations: {observations}")
    print(f"cold snapshot: {elapsed[0]:.3f}s")
    print(
        "unchanged snapshots: "
        + ", ".join(f"{duration:.3f}s" for duration in elapsed[1:])
    )
    print(f"unchanged median: {statistics.median(elapsed[1:]):.3f}s")


if __name__ == "__main__":
    main()
