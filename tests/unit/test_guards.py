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
                await middleware({"type": "http", "path": path, "headers": []}, None, None)  # type: ignore[arg-type]
                self.assertTrue(called)

    async def test_valid_token_calls_app(self) -> None:
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
        }
        await middleware(scope, None, None)  # type: ignore[arg-type]
        self.assertTrue(called)

    async def test_missing_or_invalid_token_sends_401(self) -> None:
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
                }
                await middleware(scope, None, dummy_send)  # type: ignore[arg-type]

                self.assertEqual(messages[0]["type"], "http.response.start")
                self.assertEqual(messages[0]["status"], 401)
                header_dict = dict(messages[0]["headers"])
                self.assertEqual(header_dict.get(b"www-authenticate"), b"Bearer")


if __name__ == "__main__":
    unittest.main()
