from fastapi import APIRouter, Depends

from harness_asset_manager.api.deps import get_container
from harness_asset_manager.application import BackendContainer

router = APIRouter(prefix="/api/asset-tags", tags=["asset-tags"])


@router.get("/")
def list_asset_tags(container: BackendContainer = Depends(get_container)) -> dict[str, list[str]]:
    return {"tags": container.asset_tags.list_tags()}
