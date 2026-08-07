from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import ValidationError

from harness_asset_manager.api.deps import get_container
from harness_asset_manager.api.schemas.activity import (
    ActivityEventResponse,
    ActivityResponse,
)
from harness_asset_manager.application import BackendContainer

router = APIRouter(prefix="/api/activity", tags=["activity"])

_MAX_ACTIVITY_LIMIT = 200
_MAX_ACTIVITY_SCAN = 1000


@router.get("", response_model=ActivityResponse)
def activity(
    limit: int = Query(default=100, ge=1, le=_MAX_ACTIVITY_LIMIT),
    container: BackendContainer = Depends(get_container),
) -> ActivityResponse:
    events: list[ActivityEventResponse] = []
    candidates = container.mutation_audit.read_recent(limit=_MAX_ACTIVITY_SCAN)
    for candidate in reversed(candidates):
        try:
            event = ActivityEventResponse.model_validate(candidate)
        except ValidationError:
            continue
        events.append(event)
        if len(events) == limit:
            break
    return ActivityResponse(events=events)
