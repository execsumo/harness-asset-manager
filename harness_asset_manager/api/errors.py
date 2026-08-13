from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from harness_asset_manager.errors import MarketplaceUpstreamError, MutationError


def _status_code(status: int) -> str:
    if status == 404:
        return "not_found"
    if status == 409:
        return "conflict"
    if status == 422:
        return "validation_error"
    if 400 <= status < 500:
        return "request_failed"
    if status >= 500:
        return "internal_error"
    return "request_failed"


def _error_payload(
    *,
    message: str,
    status: int,
    code: str | None = None,
) -> dict[str, str]:
    return {"code": code or _status_code(status), "error": message}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def handle_http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict):
            message = exc.detail.get("error") or exc.detail.get("message") or "Request failed."
            code = exc.detail.get("code")
            if not isinstance(message, str):
                message = "Request failed."
            if not isinstance(code, str):
                code = None
        else:
            message = exc.detail if isinstance(exc.detail, str) else "Request failed."
            code = None
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(message=message, status=exc.status_code, code=code),
        )

    @app.exception_handler(MutationError)
    async def handle_mutation_error(_request: Request, exc: MutationError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content=_error_payload(message=str(exc), status=exc.status, code=exc.code),
        )

    @app.exception_handler(MarketplaceUpstreamError)
    async def handle_marketplace_upstream_error(_request: Request, exc: MarketplaceUpstreamError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status,
            content=_error_payload(message=str(exc), status=exc.status, code=exc.code),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        if not errors:
            return JSONResponse(
                status_code=422,
                content=_error_payload(message="Invalid request.", status=422),
            )
        first = errors[0]
        msg = first.get("msg", "Invalid request.") if isinstance(first, dict) else "Invalid request."
        loc = first.get("loc", ()) if isinstance(first, dict) else ()
        field_path = ".".join(str(part) for part in loc if part != "body")
        message = f"{field_path}: {msg}" if field_path else msg
        return JSONResponse(
            status_code=422,
            content=_error_payload(message=message, status=422),
        )
