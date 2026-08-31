"""Request guards for the local, unauthenticated mutation API.

The server binds to loopback and carries no credentials, which is the right
default for a local-first tool — but only if browsers cannot be tricked into
calling it. Two browser-side attacks are in scope:

- **DNS rebinding**: a malicious page rebinds its origin to 127.0.0.1, making
  the browser send requests with the *attacker's* ``Host`` header. Rejecting
  non-loopback ``Host`` values closes this.
- **Cross-site "simple request" CSRF**: HTML forms and ``fetch`` can send
  POSTs cross-origin without a CORS preflight, but they always carry an
  ``Origin`` header naming the attacking site. Rejecting mutations whose
  ``Origin`` is not loopback closes this. Non-browser local clients (curl,
  scripts) send no ``Origin`` and keep working, matching the long-standing
  trust level for same-user local processes.

Both checks are disabled when the operator explicitly launches with
``--allow-remote`` to bind a non-loopback interface.
"""

from __future__ import annotations

import ipaddress
import json
import secrets
from urllib.parse import urlsplit

from starlette.types import ASGIApp, Receive, Scope, Send

_MUTATION_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_LOOPBACK_HOSTNAMES = frozenset({"localhost", "localhost."})


def _extract_hostname(host: str) -> str:
    normalized = host.strip().lower()
    if not normalized:
        return ""
    if normalized.startswith("["):
        return normalized[1:].split("]", 1)[0]
    if normalized.count(":") == 1:
        return normalized.rsplit(":", 1)[0]
    return normalized


def is_loopback_host(host: str) -> bool:
    """True when a ``Host`` header value (optional port) names this machine."""
    candidate = _extract_hostname(host)
    if not candidate:
        return False
    if candidate in _LOOPBACK_HOSTNAMES:
        return True
    try:
        return ipaddress.ip_address(candidate).is_loopback
    except ValueError:
        return False


def is_loopback_client(client: tuple[str, int] | list[object] | None) -> bool:
    """True when an ASGI connection client tuple originates from loopback."""
    if not client or not client[0]:
        return False
    return is_loopback_host(str(client[0]))


class LoopbackOnlyMiddleware:
    """ASGI middleware enforcing the loopback and trusted Host/Origin policy."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        allow_remote: bool = False,
        trusted_hosts: tuple[str, ...] | frozenset[str] = (),
    ) -> None:
        self.app = app
        self.allow_remote = allow_remote
        self.trusted_hosts = frozenset(_extract_hostname(h) for h in trusted_hosts if h.strip())

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self.allow_remote:
            await self.app(scope, receive, send)
            return
        headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope.get("headers", [])}
        host_header = headers.get("host", "")
        host_candidate = _extract_hostname(host_header)
        if not (is_loopback_host(host_header) or host_candidate in self.trusted_hosts):
            await _reject(send, "forbidden host: harness-asset-manager only accepts loopback requests")
            return
        if scope["method"] in _MUTATION_METHODS:
            origin = headers.get("origin")
            if origin is not None:
                origin_host = (urlsplit(origin).hostname or "").strip().lower()
                if not (is_loopback_host(origin_host) or origin_host in self.trusted_hosts):
                    await _reject(send, "forbidden origin: mutations must originate from the harness-asset-manager app")
                    return
        await self.app(scope, receive, send)


class ApiTokenMiddleware:
    """ASGI middleware enforcing loopback trust, Tailscale identity, or Bearer token authentication."""

    def __init__(
        self,
        app: ASGIApp,
        *,
        api_token: str,
    ) -> None:
        self.app = app
        self.api_token = api_token
        self._expected_bytes = api_token.encode("utf-8")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        # Only guard /api/* endpoints, exempting /api/health
        if not path.startswith("/api/") or path.rstrip("/") == "/api/health":
            await self.app(scope, receive, send)
            return

        # Rule 1: Loopback peer
        client = scope.get("client")
        if is_loopback_client(client):
            await self.app(scope, receive, send)
            return

        headers = {key.decode("latin-1").lower(): value.decode("latin-1") for key, value in scope.get("headers", [])}

        # Rule 2: Tailscale-User-Login present (non-empty)
        tailscale_login = headers.get("tailscale-user-login", "").strip()
        if tailscale_login:
            await self.app(scope, receive, send)
            return

        # Rule 3: Authorization: Bearer <token> valid
        auth_header = headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            token_candidate = auth_header[7:].strip()
            if token_candidate:
                try:
                    candidate_bytes = token_candidate.encode("utf-8")
                    if secrets.compare_digest(candidate_bytes, self._expected_bytes):
                        await self.app(scope, receive, send)
                        return
                except Exception:
                    pass

        # Everything else -> 401
        await _reject_unauthorized(send, "unauthorized: request requires loopback peer, tailscale identity, or valid bearer token")


async def _reject(send: Send, message: str) -> None:
    body = json.dumps({"error": message}).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": 403,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode("ascii"))],
        }
    )
    await send({"type": "http.response.body", "body": body})


async def _reject_unauthorized(send: Send, message: str) -> None:
    body = json.dumps({"error": message}).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": 401,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode("ascii")),
                (b"www-authenticate", b"Bearer"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
