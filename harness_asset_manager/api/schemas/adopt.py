from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AdoptionActionDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    family: str
    ref: str
    display_name: str = Field(alias="displayName")
    harness: str
    action: Literal["link", "skip", "conflict"]
    target: str = Field(alias="targetPath", default="")
    reason: str | None = None
    detail: str | None = None


class AdoptionPlanResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    actions: list[AdoptionActionDto]
    linkable_count: int = Field(alias="linkableCount")
    conflict_count: int = Field(alias="conflictCount")
    skipped_count: int = Field(alias="skippedCount")
    total_count: int = Field(alias="totalCount")
    dismissed: bool = False


class AdoptionApplyRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    actions: list[AdoptionActionDto]
    allow_conflicts: bool = Field(alias="allowConflicts", default=False)


class AdoptionApplyResultDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    family: str
    ref: str
    harness: str
    status: Literal["applied", "failed", "skipped"]
    target: str
    error: str | None = None


class AdoptionApplyResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    results: list[AdoptionApplyResultDto]
    applied_count: int = Field(alias="appliedCount")
    failed_count: int = Field(alias="failedCount")


class AdoptionDismissResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ok: bool = True
    dismissed: bool = True


__all__ = [
    "AdoptionActionDto",
    "AdoptionApplyRequest",
    "AdoptionApplyResponse",
    "AdoptionApplyResultDto",
    "AdoptionDismissResponse",
    "AdoptionPlanResponse",
]
