import re
with open("harness_asset_manager/api/routers/configs.py", "r") as f:
    code = f.read()

code = code.replace(
    'from fastapi import APIRouter, Depends',
    'from fastapi import APIRouter, Depends\nfrom fastapi.responses import JSONResponse'
)

old_restore = '''@router.post("/{harness}/restore")
def restore_config(harness: str, container: BackendContainer = Depends(get_container)) -> dict:
    container.configs_mutations.restore(harness)
    return {"status": "ok"}'''

new_restore = '''@router.post("/{harness}/restore")
def restore_config(harness: str, container: BackendContainer = Depends(get_container)):
    try:
        container.configs_mutations.restore(harness)
        return {"status": "ok"}
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})'''

code = code.replace(old_restore, new_restore)

with open("harness_asset_manager/api/routers/configs.py", "w") as f:
    f.write(code)
