#!/usr/bin/env python3
"""Read-only benchmark for comparable skills inventory snapshots."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _measure(iterations: int) -> dict[str, object]:
    import harness_asset_manager.application.skills.read_models as read_models_module
    from harness_asset_manager.application.skills.read_models import (
        SkillsReadModelService,
    )
    from harness_asset_manager.application.skills.store import SkillStore
    from harness_asset_manager.harness import (
        HarnessKernelService,
        HarnessSupportStore,
    )
    from harness_asset_manager.paths import resolve_app_paths

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
    # invalidating package state. No benchmark operation writes to a skill root.
    service.snapshot_ttl_seconds = 0

    elapsed: list[float] = []
    snapshot = None
    for _ in range(iterations):
        started = time.perf_counter()
        snapshot = service.snapshot()
        elapsed.append(time.perf_counter() - started)

    assert snapshot is not None
    harness_counts = {
        scan.harness: len(scan.skills) for scan in snapshot.harness_scans
    }
    return {
        "implementation": str(Path(read_models_module.__file__).resolve()),
        "skills_store_root": str(paths.skills_store_root.resolve()),
        "settings_path": str(paths.settings_path.resolve()),
        "store_packages": len(snapshot.store_scan.packages),
        "harness_observations": sum(harness_counts.values()),
        "harness_counts": harness_counts,
        "cold_seconds": elapsed[0],
        "unchanged_seconds": elapsed[1:],
        "unchanged_median_seconds": statistics.median(elapsed[1:]),
    }


def _run_source_tree(source_root: Path, iterations: int) -> dict[str, object]:
    active_env = dict(os.environ)
    active_env["PYTHONPATH"] = str(source_root.resolve())
    completed = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--iterations",
            str(iterations),
            "--json",
        ],
        cwd=tempfile.gettempdir(),
        env=active_env,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def _validate_parity(
    baseline: dict[str, object],
    candidate: dict[str, object],
) -> None:
    parity_fields = (
        "skills_store_root",
        "settings_path",
        "store_packages",
        "harness_observations",
        "harness_counts",
    )
    mismatches = [
        field
        for field in parity_fields
        if baseline.get(field) != candidate.get(field)
    ]
    if mismatches:
        details = ", ".join(
            f"{field}: {baseline.get(field)!r} != {candidate.get(field)!r}"
            for field in mismatches
        )
        raise SystemExit(f"benchmark inputs are not comparable ({details})")


def _format_durations(raw: object) -> str:
    assert isinstance(raw, list)
    return ", ".join(f"{float(duration):.3f}s" for duration in raw)


def _print_measurement(label: str, result: dict[str, object]) -> None:
    print(f"{label} implementation: {result['implementation']}")
    print(f"{label} cold snapshot: {float(result['cold_seconds']):.3f}s")
    print(
        f"{label} unchanged snapshots: "
        f"{_format_durations(result['unchanged_seconds'])}"
    )
    print(
        f"{label} unchanged median: "
        f"{float(result['unchanged_median_seconds']):.3f}s"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=5)
    parser.add_argument("--baseline-root", type=Path)
    parser.add_argument("--candidate-root", type=Path)
    parser.add_argument("--json", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.iterations < 2:
        parser.error("--iterations must be at least 2")
    if (args.baseline_root is None) != (args.candidate_root is None):
        parser.error("--baseline-root and --candidate-root must be provided together")

    if args.baseline_root is None:
        result = _measure(args.iterations)
        if args.json:
            print(json.dumps(result, sort_keys=True))
            return
        print(f"skills store root: {result['skills_store_root']}")
        print(f"store packages: {result['store_packages']}")
        print(f"harness observations: {result['harness_observations']}")
        _print_measurement("current", result)
        return

    baseline = _run_source_tree(args.baseline_root, args.iterations)
    candidate = _run_source_tree(args.candidate_root, args.iterations)
    _validate_parity(baseline, candidate)
    baseline_median = float(baseline["unchanged_median_seconds"])
    candidate_median = float(candidate["unchanged_median_seconds"])

    print(f"skills store root: {baseline['skills_store_root']}")
    print(f"store packages: {baseline['store_packages']}")
    print(f"harness observations: {baseline['harness_observations']}")
    print("parity check: passed")
    _print_measurement("baseline", baseline)
    _print_measurement("candidate", candidate)
    print(f"unchanged median speedup: {baseline_median / candidate_median:.2f}x")


if __name__ == "__main__":
    main()
