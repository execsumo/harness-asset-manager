from __future__ import annotations

from pydantic import BaseModel, Field


class HarnessTarget(BaseModel):
    harness: str = Field(..., min_length=1, description="Harness identifier")


class SetHarnessSupportRequest(BaseModel):
    enabled: bool


class OkResponse(BaseModel):
    ok: bool


class ErrorResponse(BaseModel):
    """Stable machine-readable envelope for unsuccessful API responses."""

    code: str = Field(..., min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    error: str


__all__ = ["ErrorResponse", "HarnessTarget", "OkResponse", "SetHarnessSupportRequest"]
