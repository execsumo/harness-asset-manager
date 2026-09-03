from __future__ import annotations

import os
import secrets
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from harness_asset_manager.api.schemas import ErrorResponse
from harness_asset_manager.application import BackendContainer

from .errors import install_error_handlers
from .guards import ApiTokenMiddleware, LoopbackOnlyMiddleware
from .routers import (
    agents,
    bootstrap,
    configs,
    health,
    hooks,
    marketplace,
    mcp,
    permissions,
    scaffold,
    settings,
    skills,
    slash_commands,
)


def custom_openapi(app: FastAPI) -> dict[str, object]:
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
        servers=app.servers,
        terms_of_service=app.terms_of_service,
        contact=app.contact,
        license_info=app.license_info,
        summary=app.summary,
    )
    # Python 3.14+ stdlib updated HTTP 422 reason phrase from "Unprocessable Entity"
    # to "Unprocessable Content" per RFC 9110. Normalize default 422 validation descriptions
    # to "Unprocessable Entity" so OpenAPI codegen is deterministic across Python 3.11-3.14+.
    for path in openapi_schema.get("paths", {}).values():
        for operation in path.values():
            if isinstance(operation, dict) and "responses" in operation:
                resp_422 = operation["responses"].get("422")
                if isinstance(resp_422, dict) and resp_422.get("description") == "Unprocessable Content":
                    resp_422["description"] = "Unprocessable Entity"
    app.openapi_schema = openapi_schema
    return app.openapi_schema


def create_app(
    container: BackendContainer,
    *,
    frontend_dist: Path | None = None,
    allow_remote: bool = False,
    trusted_hosts: tuple[str, ...] = (),
    api_token: str | None = None,
) -> FastAPI:
    resolved_token = api_token or os.environ.get("HARNESSAM_API_TOKEN") or secrets.token_urlsafe(32)
    app = FastAPI(
        title="harness-asset-manager",
        docs_url=None,
        redoc_url=None,
        openapi_url="/api/openapi.json",
        responses={
            400: {"model": ErrorResponse, "description": "Bad Request"},
            404: {"model": ErrorResponse, "description": "Not Found"},
            409: {"model": ErrorResponse, "description": "Conflict"},
            422: {"model": ErrorResponse, "description": "Unprocessable Entity"},
            500: {"model": ErrorResponse, "description": "Internal Server Error"},
            503: {"model": ErrorResponse, "description": "Service Unavailable"},
        },
    )
    app.openapi = lambda: custom_openapi(app)
    app.state.container = container
    app.state.frontend_dist = frontend_dist if frontend_dist is not None and frontend_dist.exists() else None
    app.state.api_token = resolved_token

    app.add_middleware(
        ApiTokenMiddleware,
        api_token=resolved_token,
    )
    app.add_middleware(
        LoopbackOnlyMiddleware,
        allow_remote=allow_remote,
        trusted_hosts=trusted_hosts,
    )
    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(configs.router)
    app.include_router(settings.router)
    app.include_router(skills.router)
    app.include_router(slash_commands.router)
    app.include_router(marketplace.router)
    app.include_router(mcp.router)
    app.include_router(hooks.router)
    app.include_router(permissions.router)
    app.include_router(scaffold.router)
    app.include_router(agents.router)
    app.include_router(bootstrap.router)

    @app.api_route(
        "/{full_path:path}",
        methods=["GET", "HEAD", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        include_in_schema=False,
        response_model=None,
    )
    def serve_frontend(full_path: str, request: Request):
        if full_path.startswith("api/"):
            return JSONResponse(
                status_code=404,
                content={"code": "not_found", "error": f"unknown api path: /{full_path}"},
            )
        if request.method not in ("GET", "HEAD"):
            return JSONResponse(
                status_code=405,
                content={"detail": "Method Not Allowed"},
            )
        dist = app.state.frontend_dist
        if dist is None:
            return HTMLResponse("<html><body><h1>harness-asset-manager</h1><p>Frontend build missing.</p></body></html>")

        requested = (dist / full_path).resolve() if full_path else dist / "index.html"
        dist_root = dist.resolve()
        # ``is_relative_to`` — not a string prefix check: a sibling like
        # ``dist-backup/`` would pass ``startswith(str(dist_root))``.
        if full_path and requested.is_relative_to(dist_root) and requested.exists() and requested.is_file():
            return FileResponse(requested)

        index_path = dist / "index.html"
        if index_path.exists():
            return FileResponse(index_path)

        return HTMLResponse("<html><body><h1>harness-asset-manager</h1><p>Frontend index.html missing.</p></body></html>", status_code=404)

    return app
