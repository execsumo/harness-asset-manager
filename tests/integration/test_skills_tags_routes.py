from __future__ import annotations

import unittest

from harness_asset_manager.application.skills.manifest import SkillStoreEntry
from harness_asset_manager.application.skills.package import fingerprint_package
from tests.support.app_harness import AppTestHarness
from tests.support.fake_home import seed_skill_package, seed_store_manifest


class SkillsTagsRoutesTests(unittest.TestCase):
    def test_skills_tags_put_and_get_lifecycle(self) -> None:
        with AppTestHarness() as harness:
            package_root = seed_skill_package(
                harness.spec.skills_store_root,
                "tagged-skill",
                "Tagged Skill",
                body="Skill body.",
                source_kind="github",
                source_locator="github:mode-io/tagged-skill",
            )
            revision, _ = fingerprint_package(package_root)
            seed_store_manifest(
                harness.spec,
                [
                    SkillStoreEntry(
                        package_dir="tagged-skill",
                        declared_name="Tagged Skill",
                        source_kind="github",
                        source_locator="github:mode-io/tagged-skill",
                        revision=revision,
                    )
                ],
            )

            # Initially empty tags in list & detail
            detail = harness.get_json("/api/skills/shared:tagged-skill")
            self.assertEqual(detail["tags"], [])

            list_page = harness.get_json("/api/skills")
            row = next(r for r in list_page["rows"] if r["skillRef"] == "shared:tagged-skill")
            self.assertEqual(row["tags"], [])

            # PUT /api/skills/{ref}/tags - Happy path with mixed cases, duplicates, whitespace
            put_resp = harness.put_json(
                "/api/skills/shared:tagged-skill/tags",
                {"tags": ["  devops  ", "DevOps", " starred ", "Core"]},
            )
            # Response returns updated tags, normalized, deduped, sorted with starred first
            self.assertEqual(put_resp["tags"], ["starred", "Core", "devops"])

            # Verify tags ride along on GET detail
            updated_detail = harness.get_json("/api/skills/shared:tagged-skill")
            self.assertEqual(updated_detail["tags"], ["starred", "Core", "devops"])

            # Verify tags ride along on GET list
            updated_list = harness.get_json("/api/skills")
            updated_row = next(r for r in updated_list["rows"] if r["skillRef"] == "shared:tagged-skill")
            self.assertEqual(updated_row["tags"], ["starred", "Core", "devops"])

            # Clear tags via empty list
            clear_resp = harness.put_json(
                "/api/skills/shared:tagged-skill/tags",
                {"tags": []},
            )
            self.assertEqual(clear_resp["tags"], [])
            cleared_detail = harness.get_json("/api/skills/shared:tagged-skill")
            self.assertEqual(cleared_detail["tags"], [])

    def test_skills_tags_put_validation_errors(self) -> None:
        with AppTestHarness() as harness:
            package_root = seed_skill_package(
                harness.spec.skills_store_root,
                "val-skill",
                "Validation Skill",
                body="Skill body.",
            )
            revision, _ = fingerprint_package(package_root)
            seed_store_manifest(
                harness.spec,
                [
                    SkillStoreEntry(
                        package_dir="val-skill",
                        declared_name="Validation Skill",
                        source_kind="manual",
                        source_locator="manual",
                        revision=revision,
                    )
                ],
            )

            # Empty tag string -> 400
            err_empty = harness.put_json(
                "/api/skills/shared:val-skill/tags",
                {"tags": ["valid", "   "]},
                expected_status=400,
            )
            self.assertEqual(err_empty["code"], "invalid_tag")
            self.assertIn("empty", err_empty["error"])

            # Overly long tag -> 400
            err_long = harness.put_json(
                "/api/skills/shared:val-skill/tags",
                {"tags": ["a" * 65]},
                expected_status=400,
            )
            self.assertEqual(err_long["code"], "invalid_tag")
            self.assertIn("exceeds maximum length", err_long["error"])

            # Unknown skill -> 404
            err_unknown = harness.put_json(
                "/api/skills/shared:non-existent/tags",
                {"tags": ["starred"]},
                expected_status=404,
            )
            self.assertEqual(err_unknown["code"], "skill_not_found")

    def test_unmanaged_skills_tagging_and_adoption_migration(self) -> None:
        with AppTestHarness() as harness:
            seed_skill_package(
                harness.spec.codex_root,
                "unmanaged-skill",
                "Unmanaged Skill",
                body="Body of unmanaged skill.",
            )

            list_page = harness.get_json("/api/skills")
            row = next(r for r in list_page["rows"] if r["name"] == "Unmanaged Skill")
            skill_ref = row["skillRef"]
            self.assertTrue(skill_ref.startswith("unmanaged:"))
            self.assertEqual(row["tags"], [])

            # Tag unmanaged skill
            put_resp = harness.put_json(
                f"/api/skills/{skill_ref}/tags",
                {"tags": ["starred", "experimental"]},
            )
            self.assertEqual(put_resp["tags"], ["starred", "experimental"])

            # Detail shows tags
            detail = harness.get_json(f"/api/skills/{skill_ref}")
            self.assertEqual(detail["tags"], ["starred", "experimental"])

            # Adopt unmanaged skill
            manage_resp = harness.post_json(
                f"/api/skills/{skill_ref}/manage",
                {},
            )
            self.assertTrue(manage_resp["ok"])

            # Managed skill ref is now shared:unmanaged-skill
            managed_detail = harness.get_json("/api/skills/shared:unmanaged-skill")
            # Tags survived adoption!
            self.assertEqual(managed_detail["tags"], ["starred", "experimental"])
