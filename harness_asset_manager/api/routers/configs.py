from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

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
def restore_config(harness: str, container: BackendContainer = Depends(get_container)):
    try:
        container.configs_mutations.restore(harness)
        return {"status": "ok"}
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
