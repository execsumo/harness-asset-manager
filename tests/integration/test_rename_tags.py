from __future__ import annotations

import unittest
from unittest.mock import patch

from tests.integration.test_cross_family_tags_pressure import (
    _create_agent,
    _create_hook,
    _create_skill,
)
from tests.support.app_harness import AppTestHarness


class RenameTagsPressureTest(unittest.TestCase):
    def test_merge_case_only_and_atomic_failure(self) -> None:
        with AppTestHarness() as harness:
            agent = _create_agent(harness)
            hook = _create_hook(harness)
            skill = _create_skill(harness)
            routes = [f"/api/agents/{agent}/tags", f"/api/hooks/{hook}/tags", f"/api/skills/{skill}/tags"]
            for route in routes:
                harness.put_json(route, {"tags": ["DevOps"]})
            harness.put_json(routes[1], {"tags": ["DevOps", "Development"]})
            self.assertIn("DevOps", harness.get_json("/api/asset-tags/")["tags"])

            before = harness.container.asset_tag_store.path.read_bytes()
            with patch("harness_asset_manager.atomic_files.os.replace", side_effect=OSError("injected failure")):
                harness.post_json("/api/asset-tags/rename", {"from": "DevOps", "to": "Development"}, expected_status=500)
            self.assertEqual(before, harness.container.asset_tag_store.path.read_bytes())
            self.assertEqual(harness.post_json("/api/asset-tags/rename", {"from": " DevOps ", "to": " Development "}), {"assets_changed": 3})
            entries = harness.container.asset_tag_store.load()
            self.assertEqual(len(entries), 3)
            for tags in entries.values():
                self.assertEqual(tags, ["Development"])
            self.assertEqual(harness.get_json("/api/asset-tags/")["tags"], ["Development"])
            self.assertEqual(harness.post_json("/api/asset-tags/rename", {"from": "development", "to": "DEVELOPMENT"}), {"assets_changed": 3})
            self.assertTrue(all(tags == ["DEVELOPMENT"] for tags in harness.container.asset_tag_store.load().values()))
            self.assertEqual(harness.get_json("/api/asset-tags/")["tags"], ["DEVELOPMENT"])

    def test_validation(self) -> None:
        with AppTestHarness() as harness:
            for source, target, status in [
                ("", "new", 400), ("old", "  ", 400), ("x" * 65, "new", 400),
                ("old", "x" * 65, 400), ("starred", "new", 400),
                ("old", "STARRED", 400), ("missing", "new", 404),
            ]:
                with self.subTest(source=source, target=target):
                    harness.post_json("/api/asset-tags/rename", {"from": source, "to": target}, expected_status=status)
