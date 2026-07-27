from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from harness_asset_manager.api.deps import get_container
from harness_asset_manager.application.container import BackendContainer

router = APIRouter(prefix="/api/config-snapshots", tags=["config-snapshots"])


@router.get("")
def list_snapshots(
    container: Annotated[BackendContainer, Depends(get_container)],
    harness: str | None = None,
) -> dict[str, Any]:
    snapshots = container.config_snapshots.list_snapshots(harness=harness)
    return {
        "snapshots": [
            {
                "snapshot_id": s.snapshot_id,
                "harness": s.harness,
                "config_name": s.config_name,
                "timestamp": s.timestamp,
                "trigger": s.trigger,
                "sha256": s.sha256,
                "snapshot_path": str(s.snapshot_path),
            }
            for s in snapshots
        ]
    }


@router.post("/trigger")
def trigger_manual_snapshot(
    container: Annotated[BackendContainer, Depends(get_container)],
) -> dict[str, Any]:
    targets = container.config_snapshots.resolve_target_configs()
    captured = []
    for target in targets:
        s = container.config_snapshots.capture_snapshot(target, trigger="manual", force=True)
        if s:
            captured.append(s.snapshot_id)
    return {"ok": True, "captured_count": len(captured), "captured": captured}
