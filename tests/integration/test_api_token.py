from __future__ import annotations

import http.client
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from harness_asset_manager.cli.main import main
from tests.support.app_harness import AppTestHarness


def raw_request(
    base_url: str,
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
    body: str | bytes | None = None,
) -> tuple[int, dict[str, str], str]:
    """Send an HTTP request with exact header control."""
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


class ApiTokenPressureTests(unittest.TestCase):
    """Mandatory pressure test suite verifying bearer token authentication."""

    def test_1_no_authorization_header_returns_401_on_read_and_mutation(self) -> None:
        """1. No Authorization header -> 401 on a read and on a mutation."""
        with AppTestHarness() as harness:
            # Read endpoint without Authorization header
            status, headers, body = raw_request(harness.base_url, "GET", "/api/settings")
            self.assertEqual(status, 401)
            self.assertEqual(headers.get("www-authenticate"), "Bearer")
            self.assertIn("unauthorized", body)

            # Mutation endpoint without Authorization header
            status, headers, body = raw_request(
                harness.base_url,
                "PUT",
                "/api/settings/harnesses/codex/support",
                {"Content-Type": "application/json"},
                body=json.dumps({"enabled": False}),
            )
            self.assertEqual(status, 401)
            self.assertEqual(headers.get("www-authenticate"), "Bearer")
            self.assertIn("unauthorized", body)

    def test_2_wrong_token_and_malformed_headers_return_401_not_500(self) -> None:
        """2. Wrong token -> 401. Malformed headers -> 401, not 500."""
        with AppTestHarness() as harness:
            malformed_test_cases = [
                ("wrong-token", {"Authorization": "Bearer wrong-token-xyz"}),
                ("bare-bearer", {"Authorization": "Bearer"}),
                ("bearer-empty-space", {"Authorization": "Bearer "}),
                ("bearer-spaces-only", {"Authorization": "Bearer    "}),
                ("basic-auth-scheme", {"Authorization": "Basic dXNlcjpwYXNz"}),
                ("custom-token-scheme", {"Authorization": "Token some-token"}),
                ("non-ascii-bytes", {"Authorization": "Bearer \xff\xfe\xfd"}),
                ("high-bit-bytes", {"Authorization": "Bearer " + "\x80" * 32}),
                ("random-string", {"Authorization": "JustRandomText"}),
            ]

            for name, req_headers in malformed_test_cases:
                with self.subTest(case=name):
                    status, headers, body = raw_request(
                        harness.base_url,
                        "GET",
                        "/api/settings",
                        headers=req_headers,
                    )
                    self.assertEqual(status, 401, msg=f"Case {name} returned {status}: {body}")
                    self.assertEqual(headers.get("www-authenticate"), "Bearer")
                    self.assertIn("unauthorized", body)

    def test_3_correct_token_returns_200(self) -> None:
        """3. Correct token -> 200."""
        with AppTestHarness() as harness:
            auth_header = {"Authorization": f"Bearer {harness.api_token}"}

            # Read returns 200
            status, _, body = raw_request(harness.base_url, "GET", "/api/settings", headers=auth_header)
            self.assertEqual(status, 200)
            data = json.loads(body)
            self.assertIn("harnesses", data)

            # Mutation returns 200
            status, _, body = raw_request(
                harness.base_url,
                "PUT",
                "/api/settings/harnesses/codex/support",
                {"Content-Type": "application/json", **auth_header},
                body=json.dumps({"enabled": True}),
            )
            self.assertEqual(status, 200)

    def test_4_allow_remote_with_no_token_returns_401(self) -> None:
        """4. allow_remote=True + no token -> 401 (critical regression test)."""
        with AppTestHarness(allow_remote=True) as harness:
            # Unauthenticated read with allow_remote=True is blocked with 401
            status, headers, body = raw_request(harness.base_url, "GET", "/api/settings")
            self.assertEqual(status, 401)
            self.assertEqual(headers.get("www-authenticate"), "Bearer")
            self.assertIn("unauthorized", body)

            # Unauthenticated mutation with allow_remote=True is blocked with 401
            status, headers, body = raw_request(
                harness.base_url,
                "PUT",
                "/api/settings/harnesses/codex/support",
                {"Content-Type": "application/json"},
                body=json.dumps({"enabled": False}),
            )
            self.assertEqual(status, 401)
            self.assertEqual(headers.get("www-authenticate"), "Bearer")
            self.assertIn("unauthorized", body)

            # With correct token, allow_remote=True succeeds
            status, _, _ = raw_request(
                harness.base_url,
                "GET",
                "/api/settings",
                headers={"Authorization": f"Bearer {harness.api_token}"},
            )
            self.assertEqual(status, 200)

    def test_5_api_health_exempt_from_token_requirement(self) -> None:
        """5. /api/health with no token -> 200. /api/openapi.json requires token."""
        with AppTestHarness() as harness:
            # /api/health requires no token
            status, _, body = raw_request(harness.base_url, "GET", "/api/health")
            self.assertEqual(status, 200)
            data = json.loads(body)
            self.assertTrue(data["ok"])

            # /api/openapi.json requires token over HTTP
            status, _, _ = raw_request(harness.base_url, "GET", "/api/openapi.json")
            self.assertEqual(status, 401)

            status, _, body = raw_request(
                harness.base_url,
                "GET",
                "/api/openapi.json",
                headers={"Authorization": f"Bearer {harness.api_token}"},
            )
            self.assertEqual(status, 200)
            schema = json.loads(body)
            self.assertIn("openapi", schema)

    def test_6_existing_host_origin_403_still_fire_with_valid_token(self) -> None:
        """6. Existing Host/Origin 403s still fire unchanged with a valid token."""
        with AppTestHarness() as harness:
            auth_header = {"Authorization": f"Bearer {harness.api_token}"}

            # Invalid Host header with valid token -> 403 Forbidden Host
            status, _, payload = raw_request(
                harness.base_url,
                "GET",
                "/api/settings",
                headers={"Host": "evil.example", **auth_header},
            )
            self.assertEqual(status, 403)
            self.assertIn("forbidden host", payload)

            # Invalid Origin header with valid token on mutation -> 403 Forbidden Origin
            status, _, payload = raw_request(
                harness.base_url,
                "PUT",
                "/api/settings/harnesses/codex/support",
                {
                    "Origin": "https://evil.example",
                    "Content-Type": "application/json",
                    **auth_header,
                },
                body=json.dumps({"enabled": False}),
            )
            self.assertEqual(status, 403)
            self.assertIn("forbidden origin", payload)

    def test_7_concurrent_cli_mutation_works_without_token(self) -> None:
        """7. Concurrent CLI mutation running against same store still works headlessly."""
        with AppTestHarness() as harness:
            import os
            from unittest.mock import patch

            with patch.dict(os.environ, harness.spec.env()):
                code = main(["settings", "harness", "cursor", "--disable"])
            self.assertEqual(code, 0)

            settings = harness.get_json("/api/settings")
            cursor = next(item for item in settings["harnesses"] if item["harness"] == "cursor")
            self.assertFalse(cursor["supportEnabled"])

    def test_8_middleware_ordering_is_pinned(self) -> None:
        """8. Middleware ordering is pinned so outer guards run before inner token guard."""
        with AppTestHarness() as harness:
            # 1. Invalid Host with NO token: LoopbackOnlyMiddleware is outer and fires 403 (not 401)
            status, _, payload = raw_request(
                harness.base_url,
                "GET",
                "/api/settings",
                headers={"Host": "evil.example"},
            )
            self.assertEqual(status, 403)
            self.assertIn("forbidden host", payload)

            # 2. Invalid Host with VALID token: still 403
            status, _, payload = raw_request(
                harness.base_url,
                "GET",
                "/api/settings",
                headers={"Host": "evil.example", "Authorization": f"Bearer {harness.api_token}"},
            )
            self.assertEqual(status, 403)
            self.assertIn("forbidden host", payload)

            # 3. Valid loopback Host with NO token: passes LoopbackOnly, rejected with 401 by ApiToken
            status, headers, payload = raw_request(
                harness.base_url,
                "GET",
                "/api/settings",
            )
            self.assertEqual(status, 401)
            self.assertEqual(headers.get("www-authenticate"), "Bearer")

        with AppTestHarness(allow_remote=True) as harness:
            # 4. allow_remote=True disables Host check, but ApiToken still runs -> 401
            status, _, payload = raw_request(
                harness.base_url,
                "GET",
                "/api/settings",
                headers={"Host": "evil.example"},
            )
            self.assertEqual(status, 401)

    def test_frontend_index_html_injects_token_meta_tag(self) -> None:
        """Frontend delivery injects <meta name="ham-api-token"> into index.html."""
        with TemporaryDirectory() as temp_dist:
            dist_path = Path(temp_dist)
            index_file = dist_path / "index.html"
            index_file.write_text(
                "<!doctype html><html><head><title>Test App</title></head><body><div id='root'></div></body></html>",
                encoding="utf-8",
            )

            with AppTestHarness(frontend_dist=dist_path) as harness:
                # GET /
                status, _, html = raw_request(harness.base_url, "GET", "/")
                self.assertEqual(status, 200)
                expected_meta = f'<meta name="ham-api-token" content="{harness.api_token}">'
                self.assertIn(expected_meta, html)
                self.assertIn("<head>", html)

                # GET /some-spa-route falls back to index.html with injected token
                status, _, html = raw_request(harness.base_url, "GET", "/skills")
                self.assertEqual(status, 200)
                self.assertIn(expected_meta, html)


if __name__ == "__main__":
    unittest.main()
