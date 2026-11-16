from __future__ import annotations

import unittest

from harness_asset_manager.application.skills.manifest import load_skill_store_manifest
from tests.support.app_harness import AppTestHarness
from tests.support.fake_home import seed_skill_package


class SkillsArchiveTests(unittest.TestCase):
    def test_adopt_archive_reconcile_and_restore(self) -> None:
        with AppTestHarness() as harness:
            seed_skill_package(harness.spec.codex_root, "archive-example", "Archive Example", body="Keep me")
            row = next(r for r in harness.get_json("/api/skills")["rows"] if r["name"] == "Archive Example")
            harness.post_json(f"/api/skills/{row['skillRef']}/manage")
            ref = "shared:archive-example"
            link = harness.spec.codex_root / "archive-example"
            package = harness.spec.skills_store_root / "archive-example" / "SKILL.md"
            self.assertTrue(link.is_symlink())
            harness.put_json(f"/api/skills/{ref}/tags", {"tags": ["keep"]})
            self.assertTrue(harness.post_json(f"/api/skills/{ref}/archive")["ok"])
            self.assertTrue(harness.post_json(f"/api/skills/{ref}/archive")["ok"])
            self.assertFalse(link.exists())
            self.assertTrue(package.is_file())
            manifest = load_skill_store_manifest(harness.container.skills_read_models.store.manifest_path)
            entry = next(e for e in manifest.entries if e.package_dir == "archive-example")
            self.assertEqual(entry.enabled_harnesses, ())
            self.assertNotIn(ref, [r["skillRef"] for r in harness.get_json("/api/skills")["rows"]])
            rows = harness.get_json("/api/skills?include_archived=true")["rows"]
            self.assertTrue(next(r for r in rows if r["skillRef"] == ref)["archived"])
            self.assertEqual(harness.get_json(f"/api/skills/{ref}")["tags"], ["keep"])
            harness.container.skills_queries.inventory()
            plan = harness.get_json("/api/bootstrap/plan")
            self.assertFalse(any(a["family"] == "skills" and a["ref"] == ref for a in plan["actions"]))
            self.assertFalse(link.exists())
            harness.post_json(f"/api/skills/{ref}/enable", {"harness": "codex"}, expected_status=409)
            harness.post_json(f"/api/skills/{ref}/unarchive")
            harness.post_json(f"/api/skills/{ref}/unarchive")
            self.assertFalse(harness.get_json(f"/api/skills/{ref}")["archived"])
            harness.post_json(f"/api/skills/{ref}/enable", {"harness": "codex"})
            self.assertTrue(link.is_symlink())
            self.assertTrue(package.is_file())

    def test_disabled_harness_link_and_recorded_intent_are_removed(self) -> None:
        with AppTestHarness() as harness:
            seed_skill_package(harness.spec.codex_root, "hidden-archive", "Hidden Archive")
            row = next(r for r in harness.get_json("/api/skills")["rows"] if r["name"] == "Hidden Archive")
            harness.post_json(f"/api/skills/{row['skillRef']}/manage")
            link = harness.spec.codex_root / "hidden-archive"
            harness.put_json("/api/settings/harnesses/codex/support", {"enabled": False})
            harness.post_json("/api/skills/shared:hidden-archive/archive")
            self.assertFalse(link.exists())
            manifest = load_skill_store_manifest(harness.container.skills_read_models.store.manifest_path)
            entry = next(e for e in manifest.entries if e.package_dir == "hidden-archive")
            self.assertEqual(entry.enabled_harnesses, ())
            harness.put_json("/api/settings/harnesses/codex/support", {"enabled": True})
            harness.get_json("/api/skills")
            self.assertFalse(link.exists())

    def test_stale_bootstrap_plan_cannot_restore_an_archived_binding(self) -> None:
        with AppTestHarness() as harness:
            seed_skill_package(harness.spec.codex_root, "stale-plan", "Stale Plan")
            row = next(r for r in harness.get_json("/api/skills")["rows"] if r["name"] == "Stale Plan")
            harness.post_json(f"/api/skills/{row['skillRef']}/manage")
            link = harness.spec.codex_root / "stale-plan"
            link.unlink()
            plan = harness.get_json("/api/bootstrap/plan")
            actions = [a for a in plan["actions"] if a["family"] == "skills" and a["ref"] == "shared:stale-plan" and a["harness"] == "codex"]
            self.assertEqual(len(actions), 1)
            harness.post_json("/api/skills/shared:stale-plan/archive")
            result = harness.post_json("/api/bootstrap/apply", {"actions": actions, "allowConflicts": False})
            self.assertEqual(result["appliedCount"], 0)
            self.assertFalse(link.exists())

    def test_replaced_binding_is_not_deleted(self) -> None:
        with AppTestHarness() as harness:
            seed_skill_package(harness.spec.codex_root, "replaced", "Replaced")
            row = next(r for r in harness.get_json("/api/skills")["rows"] if r["name"] == "Replaced")
            harness.post_json(f"/api/skills/{row['skillRef']}/manage")
            link = harness.spec.codex_root / "replaced"
            other = seed_skill_package(harness.spec.home / "other", "replaced", "Other")
            link.unlink()
            link.symlink_to(other)
            harness.container.skills_read_models.invalidate()
            harness.post_json("/api/skills/shared:replaced/archive", expected_status=409)
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), other.resolve())
            self.assertTrue((other / "SKILL.md").is_file())

    def test_unmanaged_and_missing_are_rejected(self) -> None:
        with AppTestHarness() as harness:
            seed_skill_package(harness.spec.codex_root, "untracked-archive", "Untracked Archive", body="Keep")
            row = next(r for r in harness.get_json("/api/skills")["rows"] if r["name"] == "Untracked Archive")
            harness.post_json(f"/api/skills/{row['skillRef']}/archive", expected_status=400)
            self.assertTrue((harness.spec.codex_root / "untracked-archive" / "SKILL.md").is_file())
            harness.post_json("/api/skills/shared:missing/archive", expected_status=404)
