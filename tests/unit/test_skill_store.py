from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness_asset_manager.application.skills.manifest import (
    load_skill_store_manifest as load_manifest,
)
from harness_asset_manager.application.skills.store import SkillStore
from tests.support.fake_home import create_fake_home_spec, seed_skill_package


class SkillStoreIngestTests(unittest.TestCase):
    def test_ingest_copies_package_and_updates_manifest(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            source = seed_skill_package(spec.home / ".codex" / "skills", "audit", "Audit Skill")
            store = SkillStore(spec.skills_store_root)
            dest = store.ingest(
                source_path=source,
                declared_name="Audit Skill",
                source_kind="centralized",
                source_locator="centralized:Audit Skill",
                source_ref="main",
                source_path_hint="skills/audit",
            )
            self.assertTrue(dest.is_dir())
            self.assertTrue((dest / "SKILL.md").is_file())
            manifest = load_manifest(store.manifest_path)
            self.assertEqual(len(manifest.entries), 1)
            self.assertEqual(manifest.entries[0].package_dir, "audit")
            self.assertEqual(manifest.entries[0].declared_name, "Audit Skill")
            self.assertEqual(manifest.entries[0].source_ref, "main")
            self.assertEqual(manifest.entries[0].source_path, "skills/audit")

    def test_ingest_refuses_existing_directory(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            seed_skill_package(spec.skills_store_root, "audit", "Existing")
            source = seed_skill_package(spec.home / ".codex" / "skills", "audit", "Audit Skill")
            store = SkillStore(spec.skills_store_root)
            with self.assertRaises(ValueError) as ctx:
                store.ingest(
                    source_path=source,
                    declared_name="Audit Skill",
                    source_kind="centralized",
                    source_locator="centralized:Audit Skill",
                )
            self.assertIn("already exists", str(ctx.exception))

    def test_ingest_creates_store_root_if_missing(self) -> None:
        with TemporaryDirectory() as temp_dir:
            source = seed_skill_package(Path(temp_dir) / "harness", "audit", "Audit Skill")
            missing_root = Path(temp_dir) / "new-store" / "shared"
            store = SkillStore(missing_root)
            dest = store.ingest(
                source_path=source,
                declared_name="Audit Skill",
                source_kind="centralized",
                source_locator="centralized:Audit Skill",
            )
            self.assertTrue(dest.is_dir())
            self.assertTrue(missing_root.is_dir())


class SkillStoreUpdateTests(unittest.TestCase):
    def test_update_replaces_changed_package(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            store = SkillStore(spec.skills_store_root)
            source_v1 = seed_skill_package(Path(temp_dir) / "v1", "audit", "Audit", body="version 1")
            store.ingest(source_path=source_v1, declared_name="Audit", source_kind="github", source_locator="github:test/test/audit")
            source_v2 = seed_skill_package(Path(temp_dir) / "v2", "audit", "Audit", body="version 2")
            _, changed = store.update("audit", source_path=source_v2, source_ref="main", source_path_hint="skills/audit")
            self.assertTrue(changed)
            content = (spec.skills_store_root / "audit" / "SKILL.md").read_text()
            self.assertIn("version 2", content)
            manifest = load_manifest(store.manifest_path)
            self.assertEqual(len(manifest.entries), 1)
            self.assertEqual(manifest.entries[0].source_ref, "main")
            self.assertEqual(manifest.entries[0].source_path, "skills/audit")

    def test_update_noop_when_identical(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            store = SkillStore(spec.skills_store_root)
            source = seed_skill_package(Path(temp_dir) / "original", "audit", "Audit", body="same content")
            store.ingest(source_path=source, declared_name="Audit", source_kind="github", source_locator="github:test/test/audit")
            source_copy = seed_skill_package(Path(temp_dir) / "copy", "audit", "Audit", body="same content")
            _, changed = store.update("audit", source_path=source_copy)
            self.assertFalse(changed)

    def test_update_refuses_missing_package(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            store = SkillStore(spec.skills_store_root)
            source = seed_skill_package(Path(temp_dir) / "src", "audit", "Audit")
            with self.assertRaises(ValueError) as ctx:
                store.update("nonexistent", source_path=source)
            self.assertIn("not in store", str(ctx.exception))


class SkillStoreDeleteTests(unittest.TestCase):
    def test_delete_removes_package_and_manifest_entry(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            store = SkillStore(spec.skills_store_root)
            source = seed_skill_package(Path(temp_dir) / "src", "audit", "Audit")
            store.ingest(
                source_path=source,
                declared_name="Audit",
                source_kind="github",
                source_locator="github:test/test/audit",
            )

            store.delete("audit")

            self.assertFalse((spec.skills_store_root / "audit").exists())
            manifest = load_manifest(store.manifest_path)
            self.assertEqual(manifest.entries, ())

    def test_delete_refuses_missing_package(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            store = SkillStore(spec.skills_store_root)

            with self.assertRaises(ValueError) as ctx:
                store.delete("missing")

            self.assertIn("not in store", str(ctx.exception))

    def test_delete_refuses_package_missing_from_manifest(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            seed_skill_package(spec.skills_store_root, "audit", "Audit")
            store = SkillStore(spec.skills_store_root)

            with self.assertRaises(ValueError) as ctx:
                store.delete("audit")

            self.assertIn("missing from manifest", str(ctx.exception))
            self.assertTrue((spec.skills_store_root / "audit").is_dir())


class SkillStoreScanArtifactsTests(unittest.TestCase):
    def test_scan_ignores_sync_artifacts_and_hidden_dirs(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            store = SkillStore(spec.skills_store_root)
            seed_skill_package(spec.skills_store_root, "audit", "Audit")

            # Add various sync artifacts in the skills store root
            (spec.skills_store_root / ".sync-conflict-20240101").mkdir(parents=True)
            (spec.skills_store_root / ".sync-conflict-20240101" / "SKILL.md").write_text("conflict", encoding="utf-8")
            (spec.skills_store_root / "audit.sync-conflict-20240101").mkdir(parents=True)
            (spec.skills_store_root / "audit.sync-conflict-20240101" / "SKILL.md").write_text("conflict", encoding="utf-8")
            (spec.skills_store_root / ".syncthing.temp.tmp").mkdir(parents=True)
            (spec.skills_store_root / "random.tmp").write_text("junk", encoding="utf-8")
            (spec.skills_store_root / "backup.bak").write_text("junk", encoding="utf-8")
            (spec.skills_store_root / "patch.rej").write_text("junk", encoding="utf-8")

            scan = store.scan()
            packages = [p.package.root_path.name for p in scan.packages]
            self.assertEqual(packages, ["audit"])

            integrity_issues = store.check_integrity()
            self.assertEqual(integrity_issues, ())


if __name__ == "__main__":
    unittest.main()
