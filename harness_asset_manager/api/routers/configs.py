from fastapi import APIRouter, Depends
from pydantic import BaseModel

from harness_asset_manager.api.deps import get_container
from harness_asset_manager.application import BackendContainer

router = APIRouter(prefix="/api/configs", tags=["configs"])

@router.get("/")
def list_configs(container: BackendContainer = Depends(get_container)) -> dict:
    return container.configs_queries.list_configs()

@router.get("/{harness}/diff")
def get_diff(harness: str, container: BackendContainer = Depends(get_container)) -> dict:
    return container.configs_queries.get_diff(harness)

@router.post("/capture")
def capture_configs(explicit: bool = False, container: BackendContainer = Depends(get_container)) -> dict:
    container.configs_mutations.capture(explicit=explicit)
    return {"status": "ok"}

@router.post("/{harness}/restore")
def restore_config(harness: str, container: BackendContainer = Depends(get_container)) -> dict:
    container.configs_mutations.restore(harness)
    return {"status": "ok"}

@router.post("/{harness}/enable")
def enable_config(harness: str, container: BackendContainer = Depends(get_container)) -> dict:
    container.configs_mutations.enable(harness)
    return {"status": "ok"}

@router.post("/{harness}/disable")
def disable_config(harness: str, container: BackendContainer = Depends(get_container)) -> dict:
    container.configs_mutations.disable(harness)
    return {"status": "ok"}

class SetTagsRequest(BaseModel):
    tags: list[str]

@router.put("/{harness}/tags")
def set_config_tags(
    harness: str,
    req: SetTagsRequest,
    container: BackendContainer = Depends(get_container),
) -> dict:
    container.asset_tag_service.set_tags("configs", harness, req.tags)
    return {"tags": container.asset_tag_service.get_tags("configs", harness)}
