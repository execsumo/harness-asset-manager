from __future__ import annotations

import unittest

from tests.integration.test_agents_routes import _seed_unmanaged_claude_agent
from tests.support.app_harness import AppTestHarness


class AgentArchiveTests(unittest.TestCase):
    def test_archive_reconcile_and_restore(self) -> None:
        with AppTestHarness() as harness:
            created = harness.post_json('/api/agents', {
                'name': 'Archive Agent', 'description': 'Keep', 'prompt': 'Retain content',
                'harnesses': ['claude'],
            })
            ref = created['ref']
            link = harness.spec.home / '.claude' / 'agents' / f'{ref}.md'
            self.assertTrue(link.is_symlink())
            store = harness.container.agents_store.path_for(ref)
            harness.put_json(f'/api/agents/{ref}/tags', {'tags': ['keep']})
            harness.post_json(f'/api/agents/{ref}/archive')
            harness.post_json(f'/api/agents/{ref}/archive')
            self.assertFalse(link.exists())
            self.assertIn('Retain content', store.read_text())
            self.assertNotIn(ref, harness.container.agents_inventory.ledger.load())
            self.assertEqual(harness.get_json(f'/api/agents/{ref}')['tags'], ['keep'])
            self.assertTrue(harness.get_json(f'/api/agents/{ref}')['archived'])
            self.assertNotIn(ref, [row['ref'] for row in harness.get_json('/api/agents')['entries']])
            rows = harness.get_json('/api/agents?include_archived=true')['entries']
            self.assertTrue(next(row for row in rows if row['ref'] == ref)['archived'])
            harness.container.agents_reconcile.reconcile()
            self.assertFalse(link.exists())
            harness.post_json(f'/api/agents/{ref}/enable', {'harness': 'claude'}, expected_status=409)
            harness.post_json(f'/api/agents/{ref}/unarchive')
            harness.post_json(f'/api/agents/{ref}/unarchive')
            harness.post_json(f'/api/agents/{ref}/enable', {'harness': 'claude'})
            self.assertTrue(link.is_symlink())

    def test_replaced_binding_is_not_deleted(self) -> None:
        with AppTestHarness() as harness:
            created = harness.post_json('/api/agents', {
                'name': 'Clobbered', 'description': 'Keep', 'prompt': 'Body',
                'harnesses': ['claude'],
            })
            ref = created['ref']
            link = harness.spec.home / '.claude' / 'agents' / f'{ref}.md'
            link.unlink()
            link.write_text('User replacement')
            harness.post_json(f'/api/agents/{ref}/archive', expected_status=409)
            self.assertEqual(link.read_text(), 'User replacement')
            self.assertIn(ref, harness.container.agents_inventory.ledger.load())

    def test_unmanaged_ref_is_rejected(self) -> None:
        with AppTestHarness() as harness:
            _seed_unmanaged_claude_agent(harness.spec)
            harness.post_json('/api/agents/claude/stray/archive', expected_status=400)
            self.assertTrue((harness.spec.home / '.claude' / 'agents' / 'stray.md').is_file())
