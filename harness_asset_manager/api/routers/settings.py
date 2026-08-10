from __future__ import annotations

from fastapi import APIRouter, Depends

from harness_asset_manager.api.deps import get_container
from harness_asset_manager.api.schemas import (
    SetAutoAdoptHarnessesRequest,
    SetAutoAdoptRequest,
    SetHarnessSupportRequest,
    SettingsResponse,
)
from harness_asset_manager.application import BackendContainer

router = APIRouter(prefix="/api/settings")


@router.get("", response_model=SettingsResponse)
def settings(container: BackendContainer = Depends(get_container)) -> dict[str, object]:
    return container.settings_queries.get_settings()


@router.put("/harnesses/{harness}/support")
def set_harness_support(
    harness: str,
    body: SetHarnessSupportRequest,
    container: BackendContainer = Depends(get_container),
) -> dict[str, object]:
    return container.settings_mutations.set_harness_support(harness, body.enabled)


@router.put("/auto-adopt/{family}")
def set_auto_adopt(
    family: str,
    body: SetAutoAdoptRequest,
    container: BackendContainer = Depends(get_container),
) -> dict[str, object]:
    return container.settings_mutations.set_auto_adopt(family, body.enabled)


@router.put("/auto-adopt/{family}/harnesses")
def set_auto_adopt_harnesses(
    family: str,
    body: SetAutoAdoptHarnessesRequest,
    container: BackendContainer = Depends(get_container),
) -> dict[str, object]:
    return container.settings_mutations.set_auto_adopt_harnesses(family, body.harnesses)
