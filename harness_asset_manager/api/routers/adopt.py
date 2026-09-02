from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from harness_asset_manager.api.deps import get_container
from harness_asset_manager.api.schemas.adopt import (
    AdoptionActionDto,
    AdoptionApplyRequest,
    AdoptionApplyResponse,
    AdoptionApplyResultDto,
    AdoptionDismissResponse,
    AdoptionPlanResponse,
)
from harness_asset_manager.application import BackendContainer
from harness_asset_manager.application.adopt import AdoptionAction

router = APIRouter(prefix="/api/adopt", tags=["Adopt"])


@router.get("/plan", response_model=AdoptionPlanResponse)
def get_adoption_plan(
    container: BackendContainer = Depends(get_container),
) -> AdoptionPlanResponse:
    plan = container.adoption_planner.plan()
    dismissed = container.adoption_dismissal.is_dismissed()

    return AdoptionPlanResponse(
        actions=[
            AdoptionActionDto(
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


@router.post("/apply", response_model=AdoptionApplyResponse)
def apply_adoption_plan(
    payload: AdoptionApplyRequest,
    container: BackendContainer = Depends(get_container),
) -> AdoptionApplyResponse:
    actions = tuple(
        AdoptionAction(
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
    results = container.adoption_applier.apply(
        actions, allow_conflicts=payload.allow_conflicts
    )

    applied_count = sum(1 for r in results if r.status == "applied")
    failed_count = sum(1 for r in results if r.status == "failed")

    return AdoptionApplyResponse(
        results=[
            AdoptionApplyResultDto(
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


@router.post("/dismiss", response_model=AdoptionDismissResponse)
def dismiss_adoption_banner(
    container: BackendContainer = Depends(get_container),
) -> AdoptionDismissResponse:
    container.adoption_dismissal.dismiss()
    return AdoptionDismissResponse(ok=True, dismissed=True)


@router.post("/reset-dismiss", response_model=AdoptionDismissResponse)
def reset_adoption_banner(
    container: BackendContainer = Depends(get_container),
) -> AdoptionDismissResponse:
    container.adoption_dismissal.reset()
    return AdoptionDismissResponse(ok=True, dismissed=False)
