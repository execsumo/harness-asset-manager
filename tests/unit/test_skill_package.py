from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from harness_asset_manager.application.skills.identity import SourceDescriptor
from harness_asset_manager.application.skills.package import (
    SkillPackageCache,
    SkillParseError,
    fingerprint_package,
    parse_skill_manifest_text,
    parse_skill_package,
)
from tests.support.fake_home import seed_skill_package


class SkillParsingTests(unittest.TestCase):
    def test_parse_skill_manifest_text_extracts_core_frontmatter(self) -> None:
        manifest = parse_skill_manifest_text(
            "---\nname: Manifest Skill\ndescription: A canonical description\nsource_kind: github\nsource_locator: github:mode-io/skills/manifest-skill\n---\n\n# Manifest Skill\n"
        )
        self.assertEqual(manifest.declared_name, "Manifest Skill")
        self.assertEqual(manifest.description, "A canonical description")
        self.assertEqual(manifest.source_kind, "github")
        self.assertEqual(manifest.source_locator, "github:mode-io/skills/manifest-skill")

    def test_parse_skill_manifest_text_normalizes_wrapping_quotes_for_scalar_metadata(self) -> None:
        manifest = parse_skill_manifest_text(
            "---\nname: \"Quoted Skill\"\ndescription: \"A canonical description\"\nsource_kind: \"github\"\nsource_locator: \"github:mode-io/skills/quoted-skill\"\n---\n\n# Ignored fallback heading\n"
        )
        self.assertEqual(manifest.declared_name, "Quoted Skill")
        self.assertEqual(manifest.description, "A canonical description")
        self.assertEqual(manifest.source_kind, "github")
        self.assertEqual(manifest.source_locator, "github:mode-io/skills/quoted-skill")

    def test_parse_skill_manifest_text_preserves_inner_quotes(self) -> None:
        manifest = parse_skill_manifest_text(
            "---\nname: Inner Quotes\ndescription: 'Use the \"fast\" path for browser automation.'\n---\n\n# Inner Quotes\n"
        )
        self.assertEqual(manifest.description, 'Use the "fast" path for browser automation.')

    def test_parse_skill_manifest_text_preserves_mismatched_quotes(self) -> None:
        manifest = parse_skill_manifest_text(
            "---\nname: Odd Quotes\ndescription: \"Leading quote only\n---\n\n# Odd Quotes\n"
        )
        self.assertEqual(manifest.description, '"Leading quote only')

    def test_parse_skill_package_uses_frontmatter_name_and_source_metadata(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            package_root = seed_skill_package(
                root,
                "audit-skill",
                "Audit Skill",
                support_files={"docs/readme.txt": "fixture"},
                source_kind="github",
                source_locator="github:mode-io/audit-skill",
            )
            package = parse_skill_package(
                package_root,
                default_source=SourceDescriptor(kind="shared-store", locator="shared-store:audit-skill"),
            )
            self.assertEqual(package.declared_name, "Audit Skill")
            self.assertIn("docs/readme.txt", package.relative_files)
            self.assertEqual(package.source.kind, "github")
            self.assertEqual(package.source.locator, "github:mode-io/audit-skill")

    def test_fingerprint_changes_when_supporting_file_changes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            package_root = seed_skill_package(root, "policy-kit", "Policy Kit", support_files={"notes.txt": "first"})
            first, _ = fingerprint_package(package_root)
            (package_root / "notes.txt").write_text("second", encoding="utf-8")
            second, _ = fingerprint_package(package_root)
            self.assertNotEqual(first, second)

    def test_package_cache_reuses_resolved_symlink_target_across_scan_cycles(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            package_root = seed_skill_package(
                root / "store",
                "policy-kit",
                "Policy Kit",
                support_files={"docs/notes.txt": "first"},
            )
            binding = root / "binding"
            binding.symlink_to(package_root)
            cache = SkillPackageCache()
            source = SourceDescriptor(kind="shared-store", locator="fixture:policy-kit")

            with patch(
                "harness_asset_manager.application.skills.package.fingerprint_package",
                wraps=fingerprint_package,
            ) as fingerprint:
                first_cycle = cache.new_validation_cycle()
                direct = cache.parse(
                    package_root,
                    default_source=source,
                    validation_cycle=first_cycle,
                )
                linked = cache.parse(
                    binding,
                    default_source=source,
                    validation_cycle=first_cycle,
                )
                unchanged = cache.parse(
                    binding,
                    default_source=source,
                    validation_cycle=cache.new_validation_cycle(),
                )

            self.assertEqual(fingerprint.call_count, 1)
            self.assertEqual(direct.revision, linked.revision)
            self.assertEqual(linked.revision, unchanged.revision)
            self.assertEqual(linked.root_path, binding)
            self.assertEqual(linked.resolved_path, package_root.resolve())

    def test_package_cache_detects_nested_content_and_topology_changes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            package_root = seed_skill_package(
                Path(temp_dir),
                "policy-kit",
                "Policy Kit",
                support_files={"docs/notes.txt": "first"},
            )
            cache = SkillPackageCache()
            source = SourceDescriptor(kind="shared-store", locator="fixture:policy-kit")

            original = cache.parse(
                package_root,
                default_source=source,
                validation_cycle=cache.new_validation_cycle(),
            )
            notes = package_root / "docs" / "notes.txt"
            notes.write_text("second", encoding="utf-8")
            content_changed = cache.parse(
                package_root,
                default_source=source,
                validation_cycle=cache.new_validation_cycle(),
            )
            added = package_root / "docs" / "added.txt"
            added.write_text("new", encoding="utf-8")
            file_added = cache.parse(
                package_root,
                default_source=source,
                validation_cycle=cache.new_validation_cycle(),
            )
            added.rename(package_root / "docs" / "renamed.txt")
            file_renamed = cache.parse(
                package_root,
                default_source=source,
                validation_cycle=cache.new_validation_cycle(),
            )
            (package_root / "docs" / "renamed.txt").unlink()
            file_removed = cache.parse(
                package_root,
                default_source=source,
                validation_cycle=cache.new_validation_cycle(),
            )

            self.assertNotEqual(original.revision, content_changed.revision)
            self.assertIn("docs/added.txt", file_added.relative_files)
            self.assertNotEqual(content_changed.revision, file_added.revision)
            self.assertIn("docs/renamed.txt", file_renamed.relative_files)
            self.assertNotEqual(file_added.revision, file_renamed.revision)
            self.assertNotIn("docs/renamed.txt", file_removed.relative_files)
            self.assertNotEqual(file_renamed.revision, file_removed.revision)

    def test_package_cache_detects_manifest_and_symlink_target_changes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first_root = seed_skill_package(root / "one", "skill", "First")
            second_root = seed_skill_package(root / "two", "skill", "Second")
            binding = root / "binding"
            binding.symlink_to(first_root)
            cache = SkillPackageCache()
            source = SourceDescriptor(kind="harness-local", locator="fixture:skill")

            first = cache.parse(
                binding,
                default_source=source,
                validation_cycle=cache.new_validation_cycle(),
            )
            (first_root / "SKILL.md").write_text(
                "---\nname: Renamed\n---\n\n# Renamed\n",
                encoding="utf-8",
            )
            renamed = cache.parse(
                binding,
                default_source=source,
                validation_cycle=cache.new_validation_cycle(),
            )
            binding.unlink()
            binding.symlink_to(second_root)
            repointed = cache.parse(
                binding,
                default_source=source,
                validation_cycle=cache.new_validation_cycle(),
            )

            self.assertEqual(first.declared_name, "First")
            self.assertEqual(renamed.declared_name, "Renamed")
            self.assertEqual(repointed.declared_name, "Second")
            self.assertEqual(repointed.resolved_path, second_root.resolve())

    def test_package_cache_explicit_invalidation_bypasses_same_cycle(self) -> None:
        with TemporaryDirectory() as temp_dir:
            package_root = seed_skill_package(Path(temp_dir), "skill", "First")
            cache = SkillPackageCache()
            source = SourceDescriptor(kind="shared-store", locator="fixture:skill")
            cycle = cache.new_validation_cycle()
            first = cache.parse(
                package_root,
                default_source=source,
                validation_cycle=cycle,
            )
            (package_root / "SKILL.md").write_text(
                "---\nname: Second\n---\n\n# Second\n",
                encoding="utf-8",
            )

            cache.invalidate()
            second = cache.parse(
                package_root,
                default_source=source,
                validation_cycle=cycle,
            )

            self.assertEqual(first.declared_name, "First")
            self.assertEqual(second.declared_name, "Second")

    def test_parse_skill_package_rejects_missing_skill_md(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "broken"
            root.mkdir(parents=True, exist_ok=True)
            with self.assertRaises(SkillParseError):
                parse_skill_package(
                    root,
                    default_source=SourceDescriptor(kind="shared-store", locator="fixture:broken"),
                )


    def test_parse_extracts_single_line_description(self) -> None:
        with TemporaryDirectory() as temp_dir:
            package_root = seed_skill_package(
                Path(temp_dir), "my-skill", "My Skill", description="A short description",
            )
            package = parse_skill_package(
                package_root, default_source=SourceDescriptor(kind="shared-store", locator="fixture:test"),
            )
            self.assertEqual(package.description, "A short description")

    def test_parse_extracts_single_line_description_without_wrapping_quotes(self) -> None:
        with TemporaryDirectory() as temp_dir:
            package_root = Path(temp_dir) / "quoted-desc"
            package_root.mkdir()
            (package_root / "SKILL.md").write_text(
                "---\nname: Quoted Description\ndescription: \"A short quoted description\"\n---\n\n# Quoted Description\n",
                encoding="utf-8",
            )
            package = parse_skill_package(
                package_root, default_source=SourceDescriptor(kind="shared-store", locator="fixture:test"),
            )
            self.assertEqual(package.description, "A short quoted description")

    def test_parse_extracts_multiline_block_scalar_description(self) -> None:
        with TemporaryDirectory() as temp_dir:
            package_root = Path(temp_dir) / "multi"
            package_root.mkdir()
            (package_root / "SKILL.md").write_text(
                "---\nname: Multi\ndescription: >-\n  First line of\n  the description.\n---\n\n# Multi\n",
                encoding="utf-8",
            )
            package = parse_skill_package(
                package_root, default_source=SourceDescriptor(kind="shared-store", locator="fixture:test"),
            )
            self.assertEqual(package.description, "First line of the description.")

    def test_parse_defaults_missing_description_to_empty(self) -> None:
        with TemporaryDirectory() as temp_dir:
            package_root = seed_skill_package(Path(temp_dir), "no-desc", "No Desc")
            package = parse_skill_package(
                package_root, default_source=SourceDescriptor(kind="shared-store", locator="fixture:test"),
            )
            self.assertEqual(package.description, "")


if __name__ == "__main__":
    unittest.main()
