from __future__ import annotations

import unittest
from unittest.mock import patch

from harness_asset_manager.application.skills.manifest import SkillStoreEntry
from harness_asset_manager.application.skills.package import fingerprint_package
from tests.support.app_harness import AppTestHarness
from tests.support.fake_home import seed_skill_package, seed_store_manifest


def _seed_skill(harness: AppTestHarness) -> str:
    package_root = seed_skill_package(harness.spec.skills_store_root, "vocab-skill", "Vocab Skill")
    revision, _ = fingerprint_package(package_root)
    seed_store_manifest(
        harness.spec,
        [SkillStoreEntry(
            package_dir="vocab-skill",
            declared_name="Vocab Skill",
            source_kind="manual",
            source_locator="manual",
            revision=revision,
        )],
    )
    return "shared:vocab-skill"


class SharedTagVocabularyTest(unittest.TestCase):
    def test_vocabulary_reuses_a_recent_skills_scan_instead_of_rescanning(self) -> None:
        with AppTestHarness() as harness:
            skill_ref = _seed_skill(harness)
            harness.put_json(f"/api/skills/{skill_ref}/tags", {"tags": ["vocab-tag"]})
            harness.get_json("/api/skills")
            read_models = harness.container.skills_read_models
            # Every list request now counts as past the read-model TTL.
            read_models.snapshot_ttl_seconds = 0
            store = read_models.store

            with patch.object(store, "scan", wraps=store.scan) as scan:
                tags = harness.get_json("/api/asset-tags/")["tags"]
                self.assertEqual(scan.call_count, 0)
                harness.get_json("/api/skills")
                self.assertEqual(scan.call_count, 1)

            self.assertIn("vocab-tag", tags)

    def test_vocabulary_drops_tags_of_a_deleted_skill_immediately(self) -> None:
        with AppTestHarness() as harness:
            skill_ref = _seed_skill(harness)
            harness.put_json(f"/api/skills/{skill_ref}/tags", {"tags": ["vocab-tag"]})
            self.assertIn("vocab-tag", harness.get_json("/api/asset-tags/")["tags"])

            harness.post_json(f"/api/skills/{skill_ref}/delete")

            self.assertNotIn("vocab-tag", harness.get_json("/api/asset-tags/")["tags"])


if __name__ == "__main__":
    unittest.main()
