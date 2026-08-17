from __future__ import annotations

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Lock
from unittest.mock import patch

import harness_asset_manager.application.skills.package as skill_package_module
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

            with patch.object(
                skill_package_module,
                "_read_stable_package",
                wraps=skill_package_module._read_stable_package,
            ) as package_read:
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

            self.assertEqual(package_read.call_count, 1)
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

    def test_file_symlink_is_re_fingerprinted_when_metadata_signature_is_stable(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            package_root = seed_skill_package(root / "packages", "skill", "Skill")
            external = root / "dynamic.txt"
            external.write_text("first", encoding="utf-8")
            link = package_root / "docs" / "dynamic.txt"
            link.parent.mkdir()
            link.symlink_to(external)
            cache = SkillPackageCache()
            source = SourceDescriptor(kind="shared-store", locator="fixture:skill")

            with patch.object(
                skill_package_module,
                "_package_metadata_signature",
                return_value=b"stable-metadata",
            ):
                first = cache.parse(
                    package_root,
                    default_source=source,
                    validation_cycle=cache.new_validation_cycle(),
                )
                external.write_text("second", encoding="utf-8")
                second = cache.parse(
                    package_root,
                    default_source=source,
                    validation_cycle=cache.new_validation_cycle(),
                )

            self.assertNotEqual(first.revision, second.revision)

    def test_directory_symlink_repoint_changes_topology_without_recursing(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            package_root = seed_skill_package(root / "packages", "skill", "Skill")
            first_target = root / "first-target"
            second_target = root / "second-target"
            first_target.mkdir()
            second_target.mkdir()
            (first_target / "ignored.txt").write_text("first", encoding="utf-8")
            (second_target / "ignored.txt").write_text("second", encoding="utf-8")
            link = package_root / "linked-directory"
            link.symlink_to(first_target, target_is_directory=True)

            first, first_files = fingerprint_package(package_root)
            link.unlink()
            link.symlink_to(second_target, target_is_directory=True)
            second, second_files = fingerprint_package(package_root)

            self.assertNotEqual(first, second)
            self.assertIn("linked-directory", first_files)
            self.assertEqual(first_files, second_files)
            self.assertNotIn("linked-directory/ignored.txt", first_files)

    def test_broken_symlink_add_repoint_and_remove_change_topology(self) -> None:
        with TemporaryDirectory() as temp_dir:
            package_root = seed_skill_package(Path(temp_dir), "skill", "Skill")
            link = package_root / "missing-link"

            original, original_files = fingerprint_package(package_root)
            link.symlink_to("missing-one")
            added, added_files = fingerprint_package(package_root)
            link.unlink()
            link.symlink_to("missing-two")
            repointed, repointed_files = fingerprint_package(package_root)
            link.unlink()
            removed, removed_files = fingerprint_package(package_root)

            self.assertNotEqual(original, added)
            self.assertNotEqual(added, repointed)
            self.assertEqual(original, removed)
            self.assertNotIn("missing-link", original_files)
            self.assertIn("missing-link", added_files)
            self.assertEqual(added_files, repointed_files)
            self.assertEqual(original_files, removed_files)

    def test_package_cache_concurrent_same_key_performs_one_build(self) -> None:
        with TemporaryDirectory() as temp_dir:
            package_root = seed_skill_package(Path(temp_dir), "skill", "Skill")
            cache = SkillPackageCache()
            source = SourceDescriptor(kind="shared-store", locator="fixture:skill")
            cycle = cache.new_validation_cycle()
            started = Event()
            release = Event()
            waiter_present = Event()
            calls = 0
            calls_lock = Lock()
            original_read = skill_package_module._read_stable_package
            original_wait = cache._condition.wait

            def blocking_read(*args, **kwargs):
                nonlocal calls
                with calls_lock:
                    calls += 1
                started.set()
                self.assertTrue(release.wait(timeout=5))
                return original_read(*args, **kwargs)

            def tracked_wait(*args, **kwargs):
                waiter_present.set()
                return original_wait(*args, **kwargs)

            with (
                patch.object(skill_package_module, "_read_stable_package", blocking_read),
                patch.object(cache._condition, "wait", side_effect=tracked_wait),
                ThreadPoolExecutor(max_workers=2) as executor,
            ):
                first = executor.submit(
                    cache.parse,
                    package_root,
                    default_source=source,
                    validation_cycle=cycle,
                )
                self.assertTrue(started.wait(timeout=2))
                second = executor.submit(
                    cache.parse,
                    package_root,
                    default_source=source,
                    validation_cycle=cycle,
                )
                self.assertTrue(waiter_present.wait(timeout=2))
                release.set()
                first_result = first.result(timeout=5)
                second_result = second.result(timeout=5)

            self.assertEqual(calls, 1)
            self.assertEqual(first_result.revision, second_result.revision)

    def test_package_cache_invalidation_during_parse_does_not_publish_stale_data(self) -> None:
        with TemporaryDirectory() as temp_dir:
            package_root = seed_skill_package(Path(temp_dir), "skill", "First")
            cache = SkillPackageCache()
            source = SourceDescriptor(kind="shared-store", locator="fixture:skill")
            started = Event()
            release = Event()
            waiter_present = Event()
            calls = 0
            original_read = skill_package_module._read_stable_package
            original_wait = cache._condition.wait

            def blocking_first_read(*args, **kwargs):
                nonlocal calls
                calls += 1
                result = original_read(*args, **kwargs)
                if calls == 1:
                    started.set()
                    self.assertTrue(release.wait(timeout=5))
                return result

            def tracked_wait(*args, **kwargs):
                waiter_present.set()
                return original_wait(*args, **kwargs)

            with (
                patch.object(
                    skill_package_module,
                    "_read_stable_package",
                    blocking_first_read,
                ),
                patch.object(cache._condition, "wait", side_effect=tracked_wait),
                ThreadPoolExecutor(max_workers=2) as executor,
            ):
                first = executor.submit(
                    cache.parse,
                    package_root,
                    default_source=source,
                    validation_cycle=cache.new_validation_cycle(),
                )
                self.assertTrue(started.wait(timeout=2))
                second = executor.submit(
                    cache.parse,
                    package_root,
                    default_source=source,
                    validation_cycle=cache.new_validation_cycle(),
                )
                self.assertTrue(waiter_present.wait(timeout=2))
                (package_root / "SKILL.md").write_text(
                    "---\nname: Second\n---\n\n# Second\n",
                    encoding="utf-8",
                )
                cache.invalidate()
                release.set()
                stale_result = first.result(timeout=5)
                fresh_result = second.result(timeout=5)

            cached_result = cache.parse(
                package_root,
                default_source=source,
                validation_cycle=cache.new_validation_cycle(),
            )
            self.assertEqual(stale_result.declared_name, "First")
            self.assertEqual(fresh_result.declared_name, "Second")
            self.assertEqual(cached_result.declared_name, "Second")
            self.assertEqual(calls, 2)

    def test_package_cache_exception_releases_waiter_and_retry_succeeds(self) -> None:
        with TemporaryDirectory() as temp_dir:
            package_root = seed_skill_package(Path(temp_dir), "skill", "Skill")
            cache = SkillPackageCache()
            source = SourceDescriptor(kind="shared-store", locator="fixture:skill")
            cycle = cache.new_validation_cycle()
            started = Event()
            release = Event()
            waiter_present = Event()
            calls = 0
            original_read = skill_package_module._read_stable_package
            original_wait = cache._condition.wait

            def flaky_read(*args, **kwargs):
                nonlocal calls
                calls += 1
                if calls == 1:
                    started.set()
                    self.assertTrue(release.wait(timeout=5))
                    raise SkillParseError("fixture parse failure")
                return original_read(*args, **kwargs)

            def tracked_wait(*args, **kwargs):
                waiter_present.set()
                return original_wait(*args, **kwargs)

            with (
                patch.object(skill_package_module, "_read_stable_package", flaky_read),
                patch.object(cache._condition, "wait", side_effect=tracked_wait),
                ThreadPoolExecutor(max_workers=2) as executor,
            ):
                failed = executor.submit(
                    cache.parse,
                    package_root,
                    default_source=source,
                    validation_cycle=cycle,
                )
                self.assertTrue(started.wait(timeout=2))
                retry = executor.submit(
                    cache.parse,
                    package_root,
                    default_source=source,
                    validation_cycle=cycle,
                )
                self.assertTrue(waiter_present.wait(timeout=2))
                release.set()
                with self.assertRaisesRegex(SkillParseError, "fixture parse failure"):
                    failed.result(timeout=5)
                result = retry.result(timeout=5)

            self.assertEqual(result.declared_name, "Skill")
            self.assertEqual(calls, 2)

    def test_package_cache_enforces_lru_bound_and_reloads_evicted_entry(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            packages = [
                seed_skill_package(root / str(index), "skill", f"Skill {index}")
                for index in range(3)
            ]
            cache = SkillPackageCache(max_entries=2)
            source = SourceDescriptor(kind="shared-store", locator="fixture:skill")

            with patch.object(
                skill_package_module,
                "_read_stable_package",
                wraps=skill_package_module._read_stable_package,
            ) as package_read:
                for package_root in packages:
                    cache.parse(
                        package_root,
                        default_source=source,
                        validation_cycle=cache.new_validation_cycle(),
                    )
                self.assertEqual(len(cache._entries), 2)
                self.assertNotIn(packages[0].resolve(), cache._entries)
                cache.parse(
                    packages[0],
                    default_source=source,
                    validation_cycle=cache.new_validation_cycle(),
                )

            self.assertEqual(package_read.call_count, 4)
            self.assertEqual(len(cache._entries), 2)

    def test_root_symlink_repoint_during_read_cannot_cross_cache_identities(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first_root = seed_skill_package(root / "first", "skill", "First")
            second_root = seed_skill_package(root / "second", "skill", "Second")
            binding = root / "binding"
            binding.symlink_to(first_root)
            cache = SkillPackageCache()
            source = SourceDescriptor(kind="harness-local", locator="fixture:skill")
            read_started = Event()
            release_read = Event()
            original_signature = skill_package_module._package_metadata_signature

            def blocking_signature(read_root: Path) -> bytes:
                self.assertEqual(read_root, first_root.resolve())
                read_started.set()
                self.assertTrue(release_read.wait(timeout=5))
                return original_signature(read_root)

            with (
                patch.object(
                    skill_package_module,
                    "_package_metadata_signature",
                    blocking_signature,
                ),
                ThreadPoolExecutor(max_workers=1) as executor,
            ):
                first_future = executor.submit(
                    cache.parse,
                    binding,
                    default_source=source,
                    validation_cycle=cache.new_validation_cycle(),
                )
                self.assertTrue(read_started.wait(timeout=2))
                binding.unlink()
                binding.symlink_to(second_root)
                release_read.set()
                first = first_future.result(timeout=5)

            second = cache.parse(
                binding,
                default_source=source,
                validation_cycle=cache.new_validation_cycle(),
            )

            self.assertEqual(first.declared_name, "First")
            self.assertEqual(first.root_path, binding)
            self.assertEqual(first.resolved_path, first_root.resolve())
            self.assertEqual(second.declared_name, "Second")
            self.assertEqual(second.resolved_path, second_root.resolve())
            self.assertEqual(
                set(cache._entries),
                {first_root.resolve(), second_root.resolve()},
            )

    def test_topology_only_symlinks_are_cacheable_across_cycles(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            package_root = seed_skill_package(root / "packages", "skill", "Skill")
            directory_target = root / "directory-target"
            directory_target.mkdir()
            (package_root / "directory-link").symlink_to(
                directory_target,
                target_is_directory=True,
            )
            (package_root / "broken-link").symlink_to("missing-target")
            cache = SkillPackageCache()
            source = SourceDescriptor(kind="shared-store", locator="fixture:skill")

            with patch.object(
                skill_package_module,
                "_read_stable_package",
                wraps=skill_package_module._read_stable_package,
            ) as package_read:
                for _ in range(2):
                    cache.parse(
                        package_root,
                        default_source=source,
                        validation_cycle=cache.new_validation_cycle(),
                    )

            self.assertEqual(package_read.call_count, 1)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO entries require os.mkfifo")
    def test_special_entries_are_cacheable_across_cycles(self) -> None:
        with TemporaryDirectory() as temp_dir:
            package_root = seed_skill_package(Path(temp_dir), "skill", "Skill")
            os.mkfifo(package_root / "events.fifo")
            cache = SkillPackageCache()
            source = SourceDescriptor(kind="shared-store", locator="fixture:skill")

            with patch.object(
                skill_package_module,
                "_read_stable_package",
                wraps=skill_package_module._read_stable_package,
            ) as package_read:
                for _ in range(2):
                    cache.parse(
                        package_root,
                        default_source=source,
                        validation_cycle=cache.new_validation_cycle(),
                    )

            self.assertEqual(package_read.call_count, 1)

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
