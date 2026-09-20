from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from harness_asset_manager.api.guards import is_loopback_client, is_loopback_host
from harness_asset_manager.application.agents.model import AgentParseError
from harness_asset_manager.errors import MarketplaceUpstreamError, MutationError

_log = logging.getLogger(__name__)


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

    @app.exception_handler(AgentParseError)
    async def handle_agent_parse_error(_request: Request, exc: AgentParseError) -> JSONResponse:
        """A file we cannot parse is the user's to fix, so say which file and why.

        This used to fall through to the unhandled-exception path and reach the UI as
        a bare 500 with no body -- the one failure where the message *is* the fix.
        """
        return JSONResponse(
            status_code=422,
            content=_error_payload(message=str(exc), status=422, code="invalid_frontmatter"),
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

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        """Last resort: a 500 still has to say something the user can act on.

        Without this the server returns Starlette's bodyless "Internal Server Error"
        and the banner can only render the status line. This is a local-first tool
        operating on the user's own files, so the exception text -- paths included --
        is exactly what makes the failure diagnosable at the machine it happened on.

        An unhandled exception is by definition one nobody vetted the wording of, so
        that text only goes to a caller sitting at this machine. A tailnet peer gets
        the status and a pointer to the log, which has the full text either way.
        """
        _log.exception("unhandled error serving %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content=_error_payload(
                message=(
                    f"{type(exc).__name__}: {exc}"
                    if _is_local_client(request)
                    else "Internal server error. The details are in the "
                    "harness-asset-manager server log on the host."
                ),
                status=500,
            ),
        )


def _is_local_client(request: Request) -> bool:
    """The same "genuine local client" test :class:`ApiTokenGuard` applies.

    ``tailscale serve`` proxies to 127.0.0.1, so a loopback peer on its own does not
    mean the user is at this machine -- the forwarded ``Host`` is what separates the
    two. Deriving both answers the same way keeps the body a remote caller sees from
    depending on which layer decided they were remote.
    """
    return is_loopback_client(request.client) and is_loopback_host(
        request.headers.get("host", "")
    )
