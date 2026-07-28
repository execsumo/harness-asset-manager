from __future__ import annotations

import socket
import unittest
from unittest import mock
from urllib.error import HTTPError, URLError

from harness_asset_manager.application.mcp.marketplace.client import (
    configured_mcp_registry_base_url,
)
from harness_asset_manager.application.skills.marketplace.client import (
    SkillsShClient,
    configured_marketplace_base_url,
    configured_marketplace_ca_file,
)
from harness_asset_manager.application.skills.marketplace.skillssh import (
    fetch_all_time_leaderboard,
    search_skills,
)
from harness_asset_manager.env_names import (
    MARKETPLACE_BASE_URL_ENV,
    MCP_REGISTRY_BASE_URL_ENV,
    legacy_name,
)
from harness_asset_manager.errors import (
    MARKETPLACE_UNAVAILABLE_MESSAGE,
    MarketplaceUpstreamError,
)


class MarketplaceClientConfigTests(unittest.TestCase):
    def test_base_url_override_is_normalized(self) -> None:
        self.assertEqual(
            configured_marketplace_base_url({"HARNESS_ASSET_MANAGER_MARKETPLACE_BASE_URL": "https://fixture.local/"}),
            "https://fixture.local",
        )

    def test_marketplace_base_url_fallback_precedence_and_empty_string(self) -> None:
        new_url = "https://new.fixture.local/"
        legacy_url = "https://legacy.fixture.local/"
        new_key = MARKETPLACE_BASE_URL_ENV
        legacy_key = legacy_name(new_key)

        # Case 1: new name alone -> honored
        self.assertEqual(
            configured_marketplace_base_url({new_key: new_url}),
            "https://new.fixture.local",
        )

        # Case 2: legacy name alone -> honored
        self.assertEqual(
            configured_marketplace_base_url({legacy_key: legacy_url}),
            "https://legacy.fixture.local",
        )

        # Case 3: both set -> new name wins
        self.assertEqual(
            configured_marketplace_base_url({new_key: new_url, legacy_key: legacy_url}),
            "https://new.fixture.local",
        )

        # Case 4: empty string -> falls back to default
        self.assertEqual(
            configured_marketplace_base_url({new_key: "   "}),
            "https://skills.sh",
        )
        self.assertEqual(
            configured_marketplace_base_url({legacy_key: ""}),
            "https://skills.sh",
        )

    def test_mcp_registry_base_url_fallback_precedence_and_empty_string(self) -> None:
        new_url = "https://mcp-new.fixture.local/"
        legacy_url = "https://mcp-legacy.fixture.local/"
        new_key = MCP_REGISTRY_BASE_URL_ENV
        legacy_key = legacy_name(new_key)

        # Case 1: new name alone -> honored
        self.assertEqual(
            configured_mcp_registry_base_url({new_key: new_url}),
            "https://mcp-new.fixture.local",
        )

        # Case 2: legacy name alone -> honored
        self.assertEqual(
            configured_mcp_registry_base_url({legacy_key: legacy_url}),
            "https://mcp-legacy.fixture.local",
        )

        # Case 3: both set -> new name wins
        self.assertEqual(
            configured_mcp_registry_base_url({new_key: new_url, legacy_key: legacy_url}),
            "https://mcp-new.fixture.local",
        )

        # Case 4: empty string -> falls back to default
        self.assertEqual(
            configured_mcp_registry_base_url({new_key: ""}),
            "https://registry.modelcontextprotocol.io",
        )
        self.assertEqual(
            configured_mcp_registry_base_url({legacy_key: "  "}),
            "https://registry.modelcontextprotocol.io",
        )

    def test_ssl_cert_override_takes_precedence(self) -> None:
        self.assertEqual(
            str(configured_marketplace_ca_file({"SSL_CERT_FILE": "/tmp/custom-ca.pem"})),
            "/tmp/custom-ca.pem",
        )

    def test_certifi_is_used_when_no_override_exists(self) -> None:
        with mock.patch("harness_asset_manager.application.marketplace_http.certifi.where", return_value="/tmp/certifi-ca.pem"):
            self.assertEqual(str(configured_marketplace_ca_file({})), "/tmp/certifi-ca.pem")


class MarketplaceProviderErrorTests(unittest.TestCase):
    def test_fetch_all_time_leaderboard_wraps_malformed_homepage_payload(self) -> None:
        client = mock.Mock()
        client.fetch_text.return_value = "<html><body>missing payload</body></html>"
        client.base_url = "https://fixture.local"
        client.absolute_url.return_value = "https://fixture.local/"

        with self.assertRaises(MarketplaceUpstreamError) as captured:
            fetch_all_time_leaderboard(client=client)

        self.assertEqual(str(captured.exception), MARKETPLACE_UNAVAILABLE_MESSAGE)
        self.assertEqual(captured.exception.kind, "payload")

    def test_search_skills_wraps_malformed_search_payload(self) -> None:
        client = mock.Mock()
        client.fetch_json.return_value = {"skills": "bad"}
        client.base_url = "https://fixture.local"
        client.absolute_url.return_value = "https://fixture.local/api/search?q=trace&limit=20"

        with self.assertRaises(MarketplaceUpstreamError) as captured:
            search_skills("trace", client=client)

        self.assertEqual(str(captured.exception), MARKETPLACE_UNAVAILABLE_MESSAGE)
        self.assertEqual(captured.exception.kind, "payload")

    def test_search_skills_filters_unsupported_sources(self) -> None:
        client = mock.Mock()
        client.fetch_json.return_value = {
            "skills": [
                {
                    "source": "unsupported-source.example",
                    "skillId": "ui-ux-pro-max",
                    "name": "ui-ux-pro-max",
                    "installs": 128,
                },
                {
                    "source": "mode-io/skills",
                    "skillId": "mode-switch",
                    "name": "Mode Switch",
                    "installs": 64,
                },
            ],
        }
        client.base_url = "https://fixture.local"
        client.absolute_url.return_value = "https://fixture.local/api/search?q=mode&limit=20"

        skills = search_skills("mode", client=client)

        self.assertEqual([(item.repo, item.skill_id) for item in skills], [("mode-io/skills", "mode-switch")])


class SkillsShClientErrorTests(unittest.TestCase):
    def test_fetch_json_maps_http_error_to_upstream_error(self) -> None:
        client = SkillsShClient(base_url="https://fixture.local")
        http_error = HTTPError(
            url="https://fixture.local/api/search?q=trace&limit=20",
            code=502,
            msg="Bad Gateway",
            hdrs=None,
            fp=None,
        )
        with mock.patch("harness_asset_manager.application.skills.marketplace.client.urlopen", side_effect=http_error):
            with self.assertRaises(MarketplaceUpstreamError) as captured:
                client.fetch_json("/api/search?q=trace&limit=20")

        self.assertEqual(str(captured.exception), MARKETPLACE_UNAVAILABLE_MESSAGE)
        self.assertEqual(captured.exception.kind, "bad_status")
        self.assertEqual(captured.exception.upstream_status, 502)

    def test_fetch_text_maps_timeout_to_upstream_error(self) -> None:
        client = SkillsShClient(base_url="https://fixture.local")
        timeout_error = URLError(socket.timeout("timed out"))
        with mock.patch("harness_asset_manager.application.skills.marketplace.client.urlopen", side_effect=timeout_error):
            with self.assertRaises(MarketplaceUpstreamError) as captured:
                client.fetch_text("/")

        self.assertEqual(str(captured.exception), MARKETPLACE_UNAVAILABLE_MESSAGE)
        self.assertEqual(captured.exception.kind, "timeout")


if __name__ == "__main__":
    unittest.main()
