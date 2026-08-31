from __future__ import annotations

import unittest

from harness_asset_manager.api.guards import is_loopback_host


class IsLoopbackHostTests(unittest.TestCase):
    def test_accepts_loopback_forms(self) -> None:
        loopback_hosts = [
            "127.0.0.1",
            "127.0.0.1:8000",
            "127.0.0.2:9000",
            "localhost",
            "localhost:5173",
            "LOCALHOST:8000",
            "::1",
            "[::1]",
            "[::1]:8000",
        ]
        for host in loopback_hosts:
            with self.subTest(host=host):
                self.assertTrue(is_loopback_host(host))

    def test_rejects_remote_and_deceptive_forms(self) -> None:
        remote_hosts = [
            "",
            "   ",
            "evil.com",
            "evil.com:80",
            "127.0.0.1.evil.com",
            "localhost.evil.com",
            "0.0.0.0",
            "0.0.0.0:8000",
            "192.168.1.5",
            "10.0.0.2:8000",
            "[::]",
            "[::]:8000",
        ]
        for host in remote_hosts:
            with self.subTest(host=host):
                self.assertFalse(is_loopback_host(host))


class LoopbackOnlyMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    async def test_trusted_host_allows_specified_host_and_origin(self) -> None:
        from harness_asset_manager.api.guards import LoopbackOnlyMiddleware

        called = False

        async def dummy_app(scope, receive, send):
            nonlocal called
            called = True

        middleware = LoopbackOnlyMiddleware(dummy_app, trusted_hosts=("foo.ts.net",))

        # Trusted host passes
        scope = {
            "type": "http",
            "method": "GET",
            "headers": [(b"host", b"foo.ts.net:7443")],
        }
        await middleware(scope, None, None)  # type: ignore[arg-type]
        self.assertTrue(called)

        # Trusted origin passes on mutation
        called = False
        scope = {
            "type": "http",
            "method": "POST",
            "headers": [(b"host", b"foo.ts.net:7443"), (b"origin", b"https://foo.ts.net:7443")],
        }
        await middleware(scope, None, None)  # type: ignore[arg-type]
        self.assertTrue(called)

    async def test_untrusted_host_and_origin_rejected_with_403(self) -> None:
        from harness_asset_manager.api.guards import LoopbackOnlyMiddleware

        messages: list[dict] = []

        async def dummy_send(msg):
            messages.append(msg)

        middleware = LoopbackOnlyMiddleware(None, trusted_hosts=("foo.ts.net",))  # type: ignore[arg-type]

        # Untrusted host
        scope = {
            "type": "http",
            "method": "GET",
            "headers": [(b"host", b"evil.example")],
        }
        await middleware(scope, None, dummy_send)  # type: ignore[arg-type]
        self.assertEqual(messages[0]["status"], 403)

        # Untrusted origin on mutation with trusted host
        messages.clear()
        scope = {
            "type": "http",
            "method": "PUT",
            "headers": [(b"host", b"foo.ts.net"), (b"origin", b"https://evil.example")],
        }
        await middleware(scope, None, dummy_send)  # type: ignore[arg-type]
        self.assertEqual(messages[0]["status"], 403)


class ApiTokenMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    async def test_non_http_scope_bypasses(self) -> None:
        from harness_asset_manager.api.guards import ApiTokenMiddleware

        called = False

        async def dummy_app(scope, receive, send):
            nonlocal called
            called = True

        middleware = ApiTokenMiddleware(dummy_app, api_token="secret-123")
        await middleware({"type": "websocket"}, None, None)  # type: ignore[arg-type]
        self.assertTrue(called)

    async def test_health_and_non_api_paths_bypass(self) -> None:
        from harness_asset_manager.api.guards import ApiTokenMiddleware

        for path in ("/api/health", "/api/health/", "/index.html", "/", "/assets/main.js"):
            with self.subTest(path=path):
                called = False

                async def dummy_app(scope, receive, send):
                    nonlocal called
                    called = True

                middleware = ApiTokenMiddleware(dummy_app, api_token="secret-123")
                await middleware({"type": "http", "path": path, "headers": [], "client": ("192.168.1.5", 12345)}, None, None)  # type: ignore[arg-type]
                self.assertTrue(called)

    async def test_rule_1_loopback_client_allows_without_credentials(self) -> None:
        from harness_asset_manager.api.guards import ApiTokenMiddleware

        called = False

        async def dummy_app(scope, receive, send):
            nonlocal called
            called = True

        middleware = ApiTokenMiddleware(dummy_app, api_token="secret-123")
        scope = {
            "type": "http",
            "path": "/api/settings",
            # A real request always carries Host; one without it is rejected by
            # LoopbackOnlyMiddleware before it reaches here.
            "headers": [(b"host", b"127.0.0.1:8000")],
            "client": ("127.0.0.1", 54321),
        }
        await middleware(scope, None, None)  # type: ignore[arg-type]
        self.assertTrue(called)

    async def test_rule_1_does_not_trust_a_loopback_proxy_forwarding_a_remote_host(self) -> None:
        """``tailscale serve`` proxies from 127.0.0.1; only the Host tells it apart."""
        from harness_asset_manager.api.guards import ApiTokenMiddleware

        called = False
        sent: list[dict] = []

        async def dummy_app(scope, receive, send):
            nonlocal called
            called = True

        async def capture(message):
            sent.append(message)

        middleware = ApiTokenMiddleware(dummy_app, api_token="secret-123")
        scope = {
            "type": "http",
            "path": "/api/settings",
            "headers": [(b"host", b"foo.ts.net:7443")],
            "client": ("127.0.0.1", 54321),
        }
        await middleware(scope, None, capture)  # type: ignore[arg-type]
        self.assertFalse(called)
        self.assertEqual(sent[0]["status"], 401)

    async def test_rule_2_tailscale_user_login_allows_remote_client(self) -> None:
        from harness_asset_manager.api.guards import ApiTokenMiddleware

        called = False

        async def dummy_app(scope, receive, send):
            nonlocal called
            called = True

        middleware = ApiTokenMiddleware(dummy_app, api_token="secret-123")
        scope = {
            "type": "http",
            "path": "/api/settings",
            "headers": [(b"tailscale-user-login", b"alice@example.com")],
            "client": ("100.64.0.5", 54321),
        }
        await middleware(scope, None, None)  # type: ignore[arg-type]
        self.assertTrue(called)

    async def test_rule_3_valid_bearer_token_allows_remote_client(self) -> None:
        from harness_asset_manager.api.guards import ApiTokenMiddleware

        called = False

        async def dummy_app(scope, receive, send):
            nonlocal called
            called = True

        middleware = ApiTokenMiddleware(dummy_app, api_token="secret-123")
        scope = {
            "type": "http",
            "path": "/api/settings",
            "headers": [(b"authorization", b"Bearer secret-123")],
            "client": ("192.168.1.100", 54321),
        }
        await middleware(scope, None, None)  # type: ignore[arg-type]
        self.assertTrue(called)

    async def test_remote_client_without_valid_auth_sends_401(self) -> None:
        from harness_asset_manager.api.guards import ApiTokenMiddleware

        test_headers = [
            [],
            [(b"authorization", b"Basic dXNlcjpwYXNz")],
            [(b"authorization", b"Bearer wrong-token")],
            [(b"authorization", b"Bearer")],
            [(b"authorization", b"Bearer   ")],
        ]

        for headers in test_headers:
            with self.subTest(headers=headers):
                messages: list[dict] = []

                async def dummy_send(msg):
                    messages.append(msg)

                middleware = ApiTokenMiddleware(None, api_token="secret-123")  # type: ignore[arg-type]
                scope = {
                    "type": "http",
                    "path": "/api/skills",
                    "headers": headers,
                    "client": ("192.168.1.100", 54321),
                }
                await middleware(scope, None, dummy_send)  # type: ignore[arg-type]

                self.assertEqual(messages[0]["type"], "http.response.start")
                self.assertEqual(messages[0]["status"], 401)
                header_dict = dict(messages[0]["headers"])
                self.assertEqual(header_dict.get(b"www-authenticate"), b"Bearer")


if __name__ == "__main__":
    unittest.main()
