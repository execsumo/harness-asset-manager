from __future__ import annotations

import json
import unittest

from tests.support.app_harness import AppTestHarness


class McpArchiveTests(unittest.TestCase):
    def test_archive_reconcile_and_restore(self) -> None:
        with AppTestHarness() as harness:
            path = harness.spec.home / '.claude.json'
            path.write_text(json.dumps({'mcpServers': {'archive-example': {'command': 'uvx', 'args': ['example']}}}))
            harness.post_json('/api/mcp/servers/archive-example/archive', expected_status=400)
            harness.post_json('/api/mcp/unmanaged/adopt', {'name': 'archive-example'})
            harness.put_json('/api/mcp/servers/archive-example/tags', {'tags': ['keep']})
            harness.post_json('/api/mcp/servers/archive-example/archive')
            harness.post_json('/api/mcp/servers/archive-example/archive')
            self.assertNotIn('archive-example', json.loads(path.read_text()).get('mcpServers', {}))
            spec = harness.container.mcp_store.get_managed('archive-example')
            self.assertEqual(spec.enabled_harnesses, ())
            self.assertEqual(spec.command, 'uvx')
            detail = harness.get_json('/api/mcp/servers/archive-example')
            self.assertTrue(detail['archived'])
            self.assertEqual(detail['tags'], ['keep'])
            self.assertEqual(harness.get_json('/api/mcp/servers')['entries'], [])
            self.assertTrue(harness.get_json('/api/mcp/servers?include_archived=true')['entries'][0]['archived'])
            harness.get_json('/api/mcp/servers')
            plan = harness.get_json('/api/bootstrap/plan')
            self.assertFalse(any(a['family'] == 'mcp' and a['ref'] == 'archive-example' for a in plan['actions']))
            self.assertNotIn('archive-example', json.loads(path.read_text()).get('mcpServers', {}))
            harness.post_json('/api/mcp/servers/archive-example/enable', {'harness': 'claude'}, expected_status=409)
            harness.post_json('/api/mcp/servers/archive-example/reconcile', {'sourceKind': 'managed', 'harnesses': ['claude']}, expected_status=409)
            harness.post_json('/api/mcp/servers/archive-example/unarchive')
            harness.post_json('/api/mcp/servers/archive-example/unarchive')
            harness.post_json('/api/mcp/servers/archive-example/enable', {'harness': 'claude'})
            self.assertIn('archive-example', json.loads(path.read_text())['mcpServers'])

    def test_changed_binding_is_not_removed(self) -> None:
        with AppTestHarness() as harness:
            path = harness.spec.home / '.claude.json'
            path.write_text(json.dumps({'mcpServers': {'modified': {'command': 'uvx', 'args': ['old']}}}))
            harness.post_json('/api/mcp/unmanaged/adopt', {'name': 'modified'})
            path.write_text(json.dumps({'mcpServers': {'modified': {'command': 'uvx', 'args': ['new']}}}))
            harness.container.mcp_read_models.invalidate()
            harness.post_json('/api/mcp/servers/modified/archive', expected_status=409)
            self.assertEqual(json.loads(path.read_text())['mcpServers']['modified']['args'], ['new'])
