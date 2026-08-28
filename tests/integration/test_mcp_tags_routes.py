from __future__ import annotations

import unittest

from tests.integration.test_mcp_routes import _seed_manual_remote
from tests.support.app_harness import AppTestHarness


class McpTagsRoutesTests(unittest.TestCase):
    def test_mcp_tags_put_and_get_lifecycle(self) -> None:
        with AppTestHarness() as harness:
            # Seed a managed MCP server
            _seed_manual_remote(harness, "filesystem")

            # Initially empty tags in list & detail
            detail = harness.get_json("/api/mcp/servers/filesystem")
            self.assertEqual(detail["tags"], [])

            list_page = harness.get_json("/api/mcp/servers")
            entry = next(e for e in list_page["entries"] if e["name"] == "filesystem")
            self.assertEqual(entry["tags"], [])

            # PUT /api/mcp/servers/{name}/tags
            put_resp = harness.put_json(
                "/api/mcp/servers/filesystem/tags",
                {"tags": ["  files  ", "Files", " starred ", "Local"]},
            )
            self.assertEqual(put_resp["tags"], ["starred", "files", "Local"])

            # Verify tags ride along on GET detail
            updated_detail = harness.get_json("/api/mcp/servers/filesystem")
            self.assertEqual(updated_detail["tags"], ["starred", "files", "Local"])

            # Verify tags ride along on GET list
            updated_list = harness.get_json("/api/mcp/servers")
            updated_entry = next(e for e in updated_list["entries"] if e["name"] == "filesystem")
            self.assertEqual(updated_entry["tags"], ["starred", "files", "Local"])

            # Clear tags
            clear_resp = harness.put_json(
                "/api/mcp/servers/filesystem/tags",
                {"tags": []},
            )
            self.assertEqual(clear_resp["tags"], [])
            cleared_detail = harness.get_json("/api/mcp/servers/filesystem")
            self.assertEqual(cleared_detail["tags"], [])

    def test_mcp_tags_put_validation_errors(self) -> None:
        with AppTestHarness() as harness:
            _seed_manual_remote(harness, "valserver")

            # Empty tag -> 400
            err_empty = harness.put_json(
                "/api/mcp/servers/valserver/tags",
                {"tags": ["valid", "   "]},
                expected_status=400,
            )
            self.assertEqual(err_empty["code"], "invalid_tag")

            # Overly long tag -> 400
            err_long = harness.put_json(
                "/api/mcp/servers/valserver/tags",
                {"tags": ["x" * 65]},
                expected_status=400,
            )
            self.assertEqual(err_long["code"], "invalid_tag")

            # Unknown server -> 404
            err_unknown = harness.put_json(
                "/api/mcp/servers/non-existent-server/tags",
                {"tags": ["starred"]},
                expected_status=404,
            )
            self.assertEqual(err_unknown["code"], "mcp_not_found")

    def test_unmanaged_mcp_server_tagging(self) -> None:
        with AppTestHarness() as harness:
            import json
            claude_cfg = harness.spec.home / ".claude.json"
            claude_cfg.write_text(
                json.dumps({
                    "mcpServers": {
                        "unmanaged-mcp": {
                            "command": "npx",
                            "args": ["-y", "unmanaged-server"],
                        }
                    }
                }),
                encoding="utf-8",
            )

            # Unmanaged server shows in list
            list_page = harness.get_json("/api/mcp/servers")
            entry = next(e for e in list_page["entries"] if e["name"] == "unmanaged-mcp")
            self.assertEqual(entry["kind"], "unmanaged")
            self.assertEqual(entry["tags"], [])

            # Tag unmanaged MCP server
            put_resp = harness.put_json(
                "/api/mcp/servers/unmanaged-mcp/tags",
                {"tags": ["starred", "external-tool"]},
            )
            self.assertEqual(put_resp["tags"], ["starred", "external-tool"])

            # Detail shows tags
            detail = harness.get_json("/api/mcp/servers/unmanaged-mcp")
            self.assertEqual(detail["tags"], ["starred", "external-tool"])

            # List shows tags
            updated_list = harness.get_json("/api/mcp/servers")
            updated_entry = next(e for e in updated_list["entries"] if e["name"] == "unmanaged-mcp")
            self.assertEqual(updated_entry["tags"], ["starred", "external-tool"])
