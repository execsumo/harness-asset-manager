from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ActivityOutcome = Literal["succeeded", "partial", "refused", "failed"]
ActivityParameterValue = str | bool | int | float | None | list[str]


class ActivityEventResponse(BaseModel):
    version: Literal[1]
    timestamp: datetime
    family: str = Field(..., min_length=1)
    operation: str = Field(..., min_length=1)
    parameters: dict[str, ActivityParameterValue]
    targetPaths: list[str]
    outcome: ActivityOutcome
    errorType: str | None = None


class ActivityResponse(BaseModel):
    events: list[ActivityEventResponse]


__all__ = ["ActivityEventResponse", "ActivityResponse"]
