from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from harness_asset_manager.api.deps import get_container
from harness_asset_manager.api.schemas.bootstrap import (
    BootstrapActionDto,
    BootstrapApplyRequest,
    BootstrapApplyResponse,
    BootstrapApplyResultDto,
    BootstrapDismissResponse,
    BootstrapPlanResponse,
)
from harness_asset_manager.application import BackendContainer
from harness_asset_manager.application.bootstrap import BootstrapAction

router = APIRouter(prefix="/api/bootstrap", tags=["Bootstrap"])


@router.get("/plan", response_model=BootstrapPlanResponse)
def get_bootstrap_plan(
    container: BackendContainer = Depends(get_container),
) -> BootstrapPlanResponse:
    plan = container.bootstrap_planner.plan()
    dismissed = container.bootstrap_dismissal.is_dismissed()

    return BootstrapPlanResponse(
        actions=[
            BootstrapActionDto(
                family=action.family,
                ref=action.ref,
                displayName=action.display_name,
                harness=action.harness,
                action=action.action,
                targetPath=str(action.target),
                reason=action.reason,
                detail=action.detail,
            )
            for action in plan.actions
        ],
        linkableCount=len(plan.linkable),
        conflictCount=len(plan.conflicts),
        skippedCount=len(plan.skipped),
        totalCount=len(plan.actions),
        dismissed=dismissed,
    )


@router.post("/apply", response_model=BootstrapApplyResponse)
def apply_bootstrap_plan(
    payload: BootstrapApplyRequest,
    container: BackendContainer = Depends(get_container),
) -> BootstrapApplyResponse:
    actions = tuple(
        BootstrapAction(
            family=dto.family,
            ref=dto.ref,
            display_name=dto.display_name,
            harness=dto.harness,
            action=dto.action,
            target=Path(dto.target),
            reason=dto.reason,
            detail=dto.detail,
        )
        for dto in payload.actions
    )
    results = container.bootstrap_applier.apply(
        actions, allow_conflicts=payload.allow_conflicts
    )

    applied_count = sum(1 for r in results if r.status == "applied")
    failed_count = sum(1 for r in results if r.status == "failed")

    return BootstrapApplyResponse(
        results=[
            BootstrapApplyResultDto(
                family=r.family,
                ref=r.ref,
                harness=r.harness,
                status=r.status,
                target=r.target,
                error=r.error,
            )
            for r in results
        ],
        appliedCount=applied_count,
        failedCount=failed_count,
    )


@router.post("/dismiss", response_model=BootstrapDismissResponse)
def dismiss_bootstrap_banner(
    container: BackendContainer = Depends(get_container),
) -> BootstrapDismissResponse:
    container.bootstrap_dismissal.dismiss()
    return BootstrapDismissResponse(ok=True, dismissed=True)


@router.post("/reset-dismiss", response_model=BootstrapDismissResponse)
def reset_bootstrap_banner(
    container: BackendContainer = Depends(get_container),
) -> BootstrapDismissResponse:
    container.bootstrap_dismissal.reset()
    return BootstrapDismissResponse(ok=True, dismissed=False)
