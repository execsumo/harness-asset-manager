from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BootstrapActionDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    family: str
    ref: str
    display_name: str = Field(alias="displayName")
    harness: str
    action: Literal["link", "skip", "conflict"]
    target: str = Field(alias="targetPath", default="")
    reason: str | None = None
    detail: str | None = None


class BootstrapPlanResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    actions: list[BootstrapActionDto]
    linkable_count: int = Field(alias="linkableCount")
    conflict_count: int = Field(alias="conflictCount")
    skipped_count: int = Field(alias="skippedCount")
    total_count: int = Field(alias="totalCount")
    dismissed: bool = False


class BootstrapApplyRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    actions: list[BootstrapActionDto]
    allow_conflicts: bool = Field(alias="allowConflicts", default=False)


class BootstrapApplyResultDto(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    family: str
    ref: str
    harness: str
    status: Literal["applied", "failed", "skipped"]
    target: str
    error: str | None = None


class BootstrapApplyResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    results: list[BootstrapApplyResultDto]
    applied_count: int = Field(alias="appliedCount")
    failed_count: int = Field(alias="failedCount")


class BootstrapDismissResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ok: bool = True
    dismissed: bool = True


__all__ = [
    "BootstrapActionDto",
    "BootstrapApplyRequest",
    "BootstrapApplyResponse",
    "BootstrapApplyResultDto",
    "BootstrapDismissResponse",
    "BootstrapPlanResponse",
]
