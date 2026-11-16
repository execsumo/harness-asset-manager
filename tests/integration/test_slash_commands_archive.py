from __future__ import annotations

import unittest

from tests.support.app_harness import AppTestHarness


class SlashCommandArchiveTests(unittest.TestCase):
    def test_archive_reconcile_and_restore(self) -> None:
        with AppTestHarness() as harness:
            harness.post_json('/api/slash-commands', {
                'name': 'archive-example', 'description': 'Keep', 'prompt': 'Retain content', 'targets': ['claude'],
            })
            path = harness.spec.home / '.claude' / 'commands' / 'archive-example.md'
            store = harness.container.slash_command_store.command_path('archive-example')
            self.assertTrue(path.is_file())
            harness.put_json('/api/slash-commands/archive-example/tags', {'tags': ['keep']})
            harness.post_json('/api/slash-commands/archive-example/archive')
            harness.post_json('/api/slash-commands/archive-example/archive')
            self.assertFalse(path.exists())
            self.assertIn('Retain content', store.read_text())
            self.assertNotIn('archive-example', harness.container.slash_command_sync_state.load())
            detail = harness.get_json('/api/slash-commands/archive-example')
            self.assertTrue(detail['archived'])
            self.assertEqual(detail['tags'], ['keep'])
            self.assertEqual(harness.get_json('/api/slash-commands')['commands'], [])
            self.assertTrue(harness.get_json('/api/slash-commands?include_archived=true')['commands'][0]['archived'])
            harness.get_json('/api/slash-commands')
            plan = harness.get_json('/api/bootstrap/plan')
            self.assertFalse(any(a['family'] == 'slash_commands' and a['ref'] == 'archive-example' for a in plan['actions']))
            self.assertFalse(path.exists())
            harness.post_json('/api/slash-commands/archive-example/sync', {'targets': ['claude']}, expected_status=409)
            harness.post_json('/api/slash-commands/archive-example/unarchive')
            harness.post_json('/api/slash-commands/archive-example/unarchive')
            harness.post_json('/api/slash-commands/archive-example/sync', {'targets': ['claude']})
            self.assertTrue(path.is_file())

    def test_unmanaged_and_modified_are_safe(self) -> None:
        with AppTestHarness() as harness:
            path = harness.spec.home / '.claude' / 'commands' / 'stray.md'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('---\ndescription: Stray\n---\nBody\n')
            harness.post_json('/api/slash-commands/stray/archive', expected_status=400)
            harness.post_json('/api/slash-commands', {
                'name': 'modified', 'description': 'Keep', 'prompt': 'Body', 'targets': ['claude'],
            })
            output = path.parent / 'modified.md'
            output.write_text('User replacement')
            harness.post_json('/api/slash-commands/modified/archive', expected_status=409)
            self.assertEqual(output.read_text(), 'User replacement')
