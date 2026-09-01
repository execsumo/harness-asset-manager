from __future__ import annotations

import http.client
import json
import unittest
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from harness_asset_manager.cli.main import main
from harness_asset_manager.paths import resolve_app_paths
from harness_asset_manager.runtime.token import resolve_api_token, rotate_api_token
from tests.support.app_harness import AppTestHarness


def raw_request(
    base_url: str,
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
    body: str | bytes | None = None,
) -> tuple[int, dict[str, str], str]:
    """Send an HTTP request via TCP with exact header control."""
    parsed = urlsplit(base_url)
    connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=5)
    try:
        req_headers = dict(headers) if headers is not None else {}
        req_body = body.encode("utf-8") if isinstance(body, str) else body
        connection.request(method, path, body=req_body, headers=req_headers)
        response = connection.getresponse()
        resp_headers = {k.lower(): v for k, v in response.getheaders()}
        return response.status, resp_headers, response.read().decode("utf-8", errors="replace")
    finally:
        connection.close()


async def asgi_request(
    app,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    client: tuple[str, int] = ("127.0.0.1", 54321),
    body: str | bytes | None = None,
) -> tuple[int, dict[str, str], str]:
    """Execute a request directly through the ASGI app with explicit client peer IP."""
    req_headers = []
    if headers:
        for k, v in headers.items():
            req_headers.append((k.lower().encode("latin-1"), v.encode("latin-1")))
    body_bytes = body.encode("utf-8") if isinstance(body, str) else (body or b"")

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "path": path,
        "raw_path": path.encode("ascii"),
        "query_string": b"",
        "headers": req_headers,
        "client": client,
        "server": ("127.0.0.1", 8000),
    }

    status_code = 0
    resp_headers: dict[str, str] = {}
    resp_body = bytearray()

    async def receive():
        return {"type": "http.request", "body": body_bytes, "more_body": False}

    async def send(message):
        nonlocal status_code, resp_headers
        if message["type"] == "http.response.start":
            status_code = message["status"]
            resp_headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in message.get("headers", [])}
        elif message["type"] == "http.response.body":
            resp_body.extend(message.get("body", b""))

    await app(scope, receive, send)
    return status_code, resp_headers, resp_body.decode("utf-8", errors="replace")


class ApiTokenPressureTests(unittest.IsolatedAsyncioTestCase):
    """Mandatory pressure test suite verifying loopback trust, Tailscale identity, and Bearer token auth."""

    async def test_1_loopback_peer_with_no_credentials_returns_200(self) -> None:
        """1. Loopback peer with no credentials -> 200 on read and mutation."""
        with AppTestHarness() as harness:
            # Over TCP to 127.0.0.1 (loopback client)
            status, _, body = raw_request(harness.base_url, "GET", "/api/settings")
            self.assertEqual(status, 200)
            data = json.loads(body)
            self.assertIn("harnesses", data)

            # Mutation without credentials from loopback peer succeeds
            status, _, body = raw_request(
                harness.base_url,
                "PUT",
                "/api/settings/harnesses/codex/support",
                {"Content-Type": "application/json"},
                body=json.dumps({"enabled": False}),
            )
            self.assertEqual(status, 200)

    async def test_2_non_loopback_peer_without_credentials_or_identity_returns_401(self) -> None:
        """2. Non-loopback peer, no credentials, no identity header -> 401, not 500."""
        with AppTestHarness() as harness:
            app = harness.server.server.config.app
            remote_client = ("192.168.1.50", 12345)

            # Unauthenticated read from non-loopback peer -> 401
            status, headers, body = await asgi_request(
                app,
                "GET",
                "/api/settings",
                headers={"Host": "127.0.0.1"},
                client=remote_client,
            )
            self.assertEqual(status, 401)
            self.assertEqual(headers.get("www-authenticate"), "Bearer")
            self.assertIn("unauthorized", body)

            # Unauthenticated mutation from non-loopback peer -> 401
            status, headers, body = await asgi_request(
                app,
                "PUT",
                "/api/settings/harnesses/codex/support",
                headers={"Host": "127.0.0.1", "Content-Type": "application/json"},
                client=remote_client,
                body=json.dumps({"enabled": False}),
            )
            self.assertEqual(status, 401)
            self.assertEqual(headers.get("www-authenticate"), "Bearer")

            # Malformed headers from non-loopback peer return 401, never 500
            malformed_cases = [
                ("wrong-token", {"Host": "127.0.0.1", "Authorization": "Bearer wrong-token-xyz"}),
                ("bare-bearer", {"Host": "127.0.0.1", "Authorization": "Bearer"}),
                ("bearer-space", {"Host": "127.0.0.1", "Authorization": "Bearer "}),
                ("bearer-spaces-only", {"Host": "127.0.0.1", "Authorization": "Bearer    "}),
                ("basic-auth", {"Host": "127.0.0.1", "Authorization": "Basic dXNlcjpwYXNz"}),
                ("custom-scheme", {"Host": "127.0.0.1", "Authorization": "Token some-token"}),
                ("non-ascii", {"Host": "127.0.0.1", "Authorization": "Bearer \xff\xfe\xfd"}),
                ("high-bit", {"Host": "127.0.0.1", "Authorization": "Bearer " + "\x80" * 32}),
                ("random", {"Host": "127.0.0.1", "Authorization": "JustRandomText"}),
            ]
            for name, req_headers in malformed_cases:
                with self.subTest(case=name):
                    status, headers, body = await asgi_request(
                        app,
                        "GET",
                        "/api/settings",
                        headers=req_headers,
                        client=remote_client,
                    )
                    self.assertEqual(status, 401, msg=f"Case {name} returned {status}: {body}")
                    self.assertEqual(headers.get("www-authenticate"), "Bearer")
                    self.assertIn("unauthorized", body)

    async def test_3_non_loopback_peer_with_tailscale_user_login_returns_200(self) -> None:
        """3. Non-loopback peer + valid Tailscale-User-Login -> 200 (paste-free remote path)."""
        with AppTestHarness(trusted_hosts=("my-mac.tailnet.ts.net",)) as harness:
            app = harness.server.server.config.app
            remote_client = ("100.64.0.5", 54321)

            # Read with Tailscale identity
            status, _, body = await asgi_request(
                app,
                "GET",
                "/api/settings",
                headers={
                    "Host": "my-mac.tailnet.ts.net",
                    "Tailscale-User-Login": "alice@example.com",
                },
                client=remote_client,
            )
            self.assertEqual(status, 200)
            data = json.loads(body)
            self.assertIn("harnesses", data)

            # Mutation with Tailscale identity
            status, _, _ = await asgi_request(
                app,
                "PUT",
                "/api/settings/harnesses/codex/support",
                headers={
                    "Host": "my-mac.tailnet.ts.net",
                    "Origin": "https://my-mac.tailnet.ts.net:7443",
                    "Content-Type": "application/json",
                    "Tailscale-User-Login": "alice@example.com",
                },
                client=remote_client,
                body=json.dumps({"enabled": True}),
            )
            self.assertEqual(status, 200)

    async def test_4_non_loopback_peer_with_valid_bearer_token_returns_200(self) -> None:
        """4. Non-loopback peer + valid bearer token -> 200."""
        with AppTestHarness(trusted_hosts=("my-mac.tailnet.ts.net",)) as harness:
            app = harness.server.server.config.app
            remote_client = ("192.168.1.50", 12345)

            # Read with valid bearer token
            status, _, body = await asgi_request(
                app,
                "GET",
                "/api/settings",
                headers={
                    "Host": "my-mac.tailnet.ts.net",
                    "Authorization": f"Bearer {harness.api_token}",
                },
                client=remote_client,
            )
            self.assertEqual(status, 200)
            data = json.loads(body)
            self.assertIn("harnesses", data)

            # Mutation with valid bearer token
            status, _, _ = await asgi_request(
                app,
                "PUT",
                "/api/settings/harnesses/codex/support",
                headers={
                    "Host": "my-mac.tailnet.ts.net",
                    "Origin": "https://my-mac.tailnet.ts.net",
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {harness.api_token}",
                },
                client=remote_client,
                body=json.dumps({"enabled": True}),
            )
            self.assertEqual(status, 200)

    async def test_5_trusted_host_allows_proxy_hostname_while_keeping_guards_active(self) -> None:
        """6. --trusted-host foo.ts.net: Host: foo.ts.net passes; Host: evil.example gets 403; cross-origin mutation gets 403."""
        with AppTestHarness(trusted_hosts=("foo.ts.net",)) as harness:
            app = harness.server.server.config.app
            remote_client = ("100.64.0.5", 54321)

            # 1. Trusted host with valid Tailscale identity -> 200
            status, _, _ = await asgi_request(
                app,
                "GET",
                "/api/settings",
                headers={
                    "Host": "foo.ts.net:7443",
                    "Tailscale-User-Login": "alice@example.com",
                },
                client=remote_client,
            )
            self.assertEqual(status, 200)

            # 2. Untrusted Host header -> 403 Forbidden Host (guard is ACTIVE)
            status, _, body = await asgi_request(
                app,
                "GET",
                "/api/settings",
                headers={
                    "Host": "evil.example",
                    "Tailscale-User-Login": "alice@example.com",
                },
                client=remote_client,
            )
            self.assertEqual(status, 403)
            self.assertIn("forbidden host", body)

            # 3. Cross-origin mutation from untrusted Origin -> 403 Forbidden Origin (guard is ACTIVE)
            status, _, body = await asgi_request(
                app,
                "PUT",
                "/api/settings/harnesses/codex/support",
                headers={
                    "Host": "foo.ts.net",
                    "Origin": "https://evil.example",
                    "Content-Type": "application/json",
                    "Tailscale-User-Login": "alice@example.com",
                },
                client=remote_client,
                body=json.dumps({"enabled": False}),
            )
            self.assertEqual(status, 403)
            self.assertIn("forbidden origin", body)

    async def test_6_serve_proxied_traffic_is_not_trusted_as_a_loopback_client(self) -> None:
        """The real Serve shape: loopback peer (the proxy) + tailnet Host.

        ``tailscale serve`` proxies to 127.0.0.1, so tailnet requests arrive with a
        loopback peer exactly like a local client. If loopback-peer trust applied to
        them, every device on the tailnet would reach the API unauthenticated and the
        identity/token rules would be unreachable. The ``Host`` header is what tells
        them apart. Every other remote case in this suite uses a synthetic non-loopback
        peer, which this deployment never produces.
        """
        with AppTestHarness(trusted_hosts=("foo.ts.net",)) as harness:
            app = harness.server.server.config.app
            proxy_client = ("127.0.0.1", 54321)

            # No identity, no token -> 401 even though the peer is loopback.
            status, _, _ = await asgi_request(
                app,
                "GET",
                "/api/settings",
                headers={"Host": "foo.ts.net:7443"},
                client=proxy_client,
            )
            self.assertEqual(status, 401)

            # Serve-injected identity -> 200.
            status, _, _ = await asgi_request(
                app,
                "GET",
                "/api/settings",
                headers={
                    "Host": "foo.ts.net:7443",
                    "Tailscale-User-Login": "alice@example.com",
                },
                client=proxy_client,
            )
            self.assertEqual(status, 200)

            # Bearer token over the proxy -> 200.
            status, _, _ = await asgi_request(
                app,
                "GET",
                "/api/settings",
                headers={
                    "Host": "foo.ts.net:7443",
                    "Authorization": f"Bearer {harness.api_token}",
                },
                client=proxy_client,
            )
            self.assertEqual(status, 200)

            # A genuine local client is still unauthenticated-friendly.
            status, _, _ = await asgi_request(
                app,
                "GET",
                "/api/settings",
                headers={"Host": "127.0.0.1:8000"},
                client=proxy_client,
            )
            self.assertEqual(status, 200)

    async def test_7_token_persists_across_restart_and_rotates_with_rotate_flag(self) -> None:
        """7. Token persists across simulated restart (same store -> same token); --rotate changes it."""
        with TemporaryDirectory() as temp_state:
            env = {"HARNESS_ASSET_MANAGER_STATE_DIR": temp_state}
            paths = resolve_app_paths(env)

            # First resolve creates and persists token
            token1 = resolve_api_token(paths, env)
            self.assertTrue(paths.api_token_path.is_file())
            self.assertEqual(paths.api_token_path.stat().st_mode & 0o777, 0o600)

            # Re-resolving (simulated server restart with same store) gives identical token
            token2 = resolve_api_token(paths, env)
            self.assertEqual(token1, token2)

            # Rotating token generates new token and updates store
            rotated = rotate_api_token(paths)
            self.assertNotEqual(token1, rotated)
            self.assertEqual(resolve_api_token(paths, env), rotated)

    async def test_8_middleware_ordering_is_pinned(self) -> None:
        """8. Middleware ordering: LoopbackOnlyMiddleware (outer) runs before ApiTokenMiddleware (inner)."""
        with AppTestHarness(trusted_hosts=("foo.ts.net",)) as harness:
            app = harness.server.server.config.app
            remote_client = ("192.168.1.50", 12345)

            # 1. Invalid Host with NO credentials: rejected with 403 by LoopbackOnlyMiddleware (not 401)
            status, _, payload = await asgi_request(
                app,
                "GET",
                "/api/settings",
                headers={"Host": "evil.example"},
                client=remote_client,
            )
            self.assertEqual(status, 403)
            self.assertIn("forbidden host", payload)

            # 2. Invalid Host with VALID credentials: still rejected with 403 by LoopbackOnlyMiddleware
            status, _, payload = await asgi_request(
                app,
                "GET",
                "/api/settings",
                headers={
                    "Host": "evil.example",
                    "Authorization": f"Bearer {harness.api_token}",
                },
                client=remote_client,
            )
            self.assertEqual(status, 403)
            self.assertIn("forbidden host", payload)

            # 3. Valid Host with NO credentials on non-loopback peer: passes LoopbackOnly, rejected by ApiToken with 401
            status, headers, payload = await asgi_request(
                app,
                "GET",
                "/api/settings",
                headers={"Host": "foo.ts.net"},
                client=remote_client,
            )
            self.assertEqual(status, 401)
            self.assertEqual(headers.get("www-authenticate"), "Bearer")

    async def test_9_api_health_is_exempt_from_token_requirement(self) -> None:
        """9. /api/health returns 200 from non-loopback client without credentials. /api/openapi.json requires credentials."""
        with AppTestHarness(trusted_hosts=("foo.ts.net",)) as harness:
            app = harness.server.server.config.app
            remote_client = ("192.168.1.50", 12345)

            # /api/health requires no auth even for remote clients
            status, _, body = await asgi_request(
                app,
                "GET",
                "/api/health",
                headers={"Host": "foo.ts.net"},
                client=remote_client,
            )
            self.assertEqual(status, 200)
            data = json.loads(body)
            self.assertTrue(data["ok"])

            # /api/openapi.json requires credentials for remote clients
            status, _, _ = await asgi_request(
                app,
                "GET",
                "/api/openapi.json",
                headers={"Host": "foo.ts.net"},
                client=remote_client,
            )
            self.assertEqual(status, 401)

            status, _, body = await asgi_request(
                app,
                "GET",
                "/api/openapi.json",
                headers={
                    "Host": "foo.ts.net",
                    "Authorization": f"Bearer {harness.api_token}",
                },
                client=remote_client,
            )
            self.assertEqual(status, 200)
            schema = json.loads(body)
            self.assertIn("openapi", schema)

    async def test_10_concurrent_cli_mutation_works_without_token(self) -> None:
        """10. Concurrent CLI mutation running against same store still works headlessly without HTTP."""
        with AppTestHarness() as harness:
            import os
            from unittest.mock import patch

            with patch.dict(os.environ, harness.spec.env()):
                code = main(["settings", "harness", "cursor", "--disable"])
            self.assertEqual(code, 0)

            settings = harness.get_json("/api/settings")
            cursor = next(item for item in settings["harnesses"] if item["harness"] == "cursor")
            self.assertFalse(cursor["supportEnabled"])


if __name__ == "__main__":
    unittest.main()
