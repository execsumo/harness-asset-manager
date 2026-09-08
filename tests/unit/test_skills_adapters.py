from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from harness_asset_manager.application.container import build_backend_container
from harness_asset_manager.application.skills.adapters import (
    FileTreeSkillsAdapter,
    _ResolvedRoot,
    build_skills_adapters,
)
from harness_asset_manager.application.skills.inventory import SkillInventory
from harness_asset_manager.application.skills.manifest import load_skill_store_manifest
from harness_asset_manager.application.skills.store import SkillStore
from harness_asset_manager.errors import MutationError
from harness_asset_manager.harness import HarnessKernelService, HarnessSupportStore
from harness_asset_manager.paths import APP_NAME
from tests.support.fake_home import create_fake_home_spec, seed_skill_package


def _adapter(harness: str, spec, *, data_dir: Path | None = None) :
    kernel = HarnessKernelService.from_environment(
        spec.env(),
        support_store=HarnessSupportStore(spec.root / "settings.json"),
    )
    return next(adapter for adapter in build_skills_adapters(kernel, data_dir=data_dir) if adapter.harness == harness)


class SkillsAdapterTests(unittest.TestCase):
    def test_physical_profile_skill_is_unmanaged_and_names_its_bot(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            physical = seed_skill_package(
                spec.hermes_home / "profiles" / "coder" / "skills" / "harnessam",
                "bot-skill",
                "Bot Skill",
            )
            scan = _adapter(
                "hermes", spec, data_dir=spec.xdg_data_home / APP_NAME
            ).scan()

            self.assertEqual(len(scan.skills), 1)
            self.assertEqual(scan.skills[0].harness, "hermes:coder")
            self.assertEqual(scan.skills[0].label, "Hermes profile coder skills")
            self.assertEqual(scan.skills[0].classification, "unmanaged")
            self.assertEqual(scan.skills[0].package.root_path, physical)

    def test_profile_bundled_skill_is_excluded_by_profile_policy(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            profile_skills = spec.hermes_home / "profiles" / "coder" / "skills"
            seed_skill_package(profile_skills / "builtin", "official", "Official")
            (profile_skills / ".bundled_manifest").write_text(
                "Official:0123456789abcdef\n", encoding="utf-8"
            )

            scan = _adapter(
                "hermes", spec, data_dir=spec.xdg_data_home / APP_NAME
            ).scan()

            self.assertEqual(scan.skills, ())
            self.assertIn("Official", scan.excluded_skill_names)

    def test_adopting_profile_skill_ingests_links_and_records_exact_bot(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            physical = seed_skill_package(
                spec.hermes_home / "profiles" / "coder" / "skills" / "harnessam",
                "bot-skill",
                "Bot Skill",
            )
            container = build_backend_container(spec.env())
            entry = next(
                item
                for item in container.skills_queries.inventory().entries
                if item.kind == "unmanaged"
            )

            container.skills_mutations.manage_skill(entry.skill_ref)

            canonical = spec.skills_store_root / "bot-skill"
            link = (
                spec.hermes_home
                / "profiles"
                / "coder"
                / "skills"
                / "harnessam"
                / "bot-skill"
            )
            self.assertTrue(link.is_symlink())
            self.assertTrue(physical.is_symlink())
            self.assertEqual(link.resolve(), canonical.resolve())
            self.assertTrue((canonical / "SKILL.md").is_file())
            manifest = load_skill_store_manifest(container.paths.skills_store_manifest)
            self.assertEqual(manifest.entries[0].enabled_harnesses, ("hermes:coder",))

    def test_adoption_conflict_keeps_bot_copy_and_canonical_package(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            seed_skill_package(spec.skills_store_root, "bot-skill", "Canonical")
            physical = seed_skill_package(
                spec.hermes_home / "profiles" / "coder" / "skills" / "harnessam",
                "bot-skill",
                "Bot Copy",
            )
            container = build_backend_container(spec.env())
            entry = next(
                item
                for item in container.skills_queries.inventory().entries
                if item.kind == "unmanaged"
            )

            with self.assertRaises(MutationError):
                container.skills_mutations.manage_skill(entry.skill_ref)

            self.assertTrue(physical.is_dir())
            self.assertFalse(physical.is_symlink())
            self.assertEqual(
                (spec.skills_store_root / "bot-skill" / "SKILL.md").read_text(
                    encoding="utf-8"
                ).splitlines()[1],
                "name: Canonical",
            )

    def test_adoption_failure_after_ingest_restores_physical_bot_copy(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            physical = seed_skill_package(
                spec.hermes_home / "profiles" / "coder" / "skills" / "harnessam",
                "bot-skill",
                "Bot Skill",
            )
            container = build_backend_container(spec.env())
            entry = next(
                item
                for item in container.skills_queries.inventory().entries
                if item.kind == "unmanaged"
            )
            adapter = next(
                item for item in container.skills_read_models.adapters if item.harness == "hermes"
            )
            with mock.patch.object(
                adapter, "adopt_local_copy", side_effect=OSError("simulated link failure")
            ), self.assertRaises(OSError):
                container.skills_mutations.manage_skill(entry.skill_ref)

            self.assertTrue(physical.is_dir())
            self.assertFalse(physical.is_symlink())
            self.assertFalse((spec.skills_store_root / "bot-skill").exists())

    def test_auto_adopt_identical_profile_copies_once_and_links_both_bots(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            for profile in ("coder", "reviewer"):
                seed_skill_package(
                    spec.hermes_home / "profiles" / profile / "skills" / "harnessam",
                    "bot-skill",
                    "Bot Skill",
                )
            container = build_backend_container(spec.env())
            container.settings_mutations.set_auto_adopt_harnesses("skills", ["hermes"])

            inventory = container.skills_queries.inventory()

            managed = [entry for entry in inventory.entries if entry.kind == "managed"]
            self.assertEqual(len(managed), 1)
            self.assertEqual(managed[0].package_dir, "bot-skill")
            self.assertTrue(
                all(
                    (
                        spec.hermes_home
                        / "profiles"
                        / profile
                        / "skills"
                        / "harnessam"
                        / "bot-skill"
                    ).is_symlink()
                    for profile in ("coder", "reviewer")
                )
            )
            self.assertTrue((spec.skills_store_root / "bot-skill").is_dir())

    def test_auto_adopt_differing_profile_copies_stays_manual(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            seed_skill_package(
                spec.hermes_home / "profiles" / "coder" / "skills" / "harnessam",
                "bot-skill",
                "Bot Skill",
                body="coder version",
            )
            seed_skill_package(
                spec.hermes_home / "profiles" / "reviewer" / "skills" / "harnessam",
                "bot-skill",
                "Bot Skill",
                body="reviewer version",
            )
            container = build_backend_container(spec.env())
            container.settings_mutations.set_auto_adopt_harnesses("skills", ["hermes"])

            inventory = container.skills_queries.inventory()

            self.assertEqual(
                len([entry for entry in inventory.entries if entry.kind == "unmanaged"]),
                2,
            )
            self.assertFalse((spec.skills_store_root / "bot-skill").exists())
            for profile in ("coder", "reviewer"):
                path = (
                    spec.hermes_home
                    / "profiles"
                    / profile
                    / "skills"
                    / "harnessam"
                    / "bot-skill"
                )
                self.assertTrue(path.is_dir())
                self.assertFalse(path.is_symlink())

    def test_hermes_profile_root_resolution_is_total_when_profiles_are_absent(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            hermes = _adapter("hermes", spec)

            self.assertEqual(hermes._dynamic_roots_provider(), ())
            self.assertEqual(hermes.scan().skills, ())

    def test_hermes_profile_roots_carry_exact_targets_and_labels(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            for profile_name in ("coder", "reviewer"):
                (spec.hermes_home / "profiles" / profile_name / "skills").mkdir(
                    parents=True
                )

            hermes = _adapter("hermes", spec)
            roots = hermes._dynamic_roots_provider()

            self.assertEqual(
                [(root.binding_scope, root.label) for root in roots],
                [
                    ("coder", "Hermes profile coder skills"),
                    ("reviewer", "Hermes profile reviewer skills"),
                ],
            )

    def test_hermes_scoped_binding_is_profile_local_and_discovered_with_exact_target(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            package = seed_skill_package(spec.skills_store_root, "audit", "Audit")
            for profile_name in ("coder", "reviewer"):
                (spec.hermes_home / "profiles" / profile_name / "skills").mkdir(
                    parents=True
                )

            hermes = _adapter("hermes", spec)
            hermes.enable_shared_package(package, scope="coder")
            hermes.enable_shared_package(package, scope="reviewer")

            coder_link = (
                spec.hermes_home / "profiles" / "coder" / "skills" / "harnessam" / "audit"
            )
            reviewer_link = (
                spec.hermes_home
                / "profiles"
                / "reviewer"
                / "skills"
                / "harnessam"
                / "audit"
            )
            self.assertTrue(coder_link.is_symlink())
            self.assertTrue(reviewer_link.is_symlink())
            self.assertEqual(coder_link.resolve(), package.resolve())
            self.assertEqual(reviewer_link.resolve(), package.resolve())
            self.assertFalse((spec.hermes_skills_root / "harnessam" / "audit").exists())

            targets = {observation.harness for observation in hermes.scan().skills}
            self.assertEqual(targets, {"hermes:coder", "hermes:reviewer"})

    def test_hermes_bot_binding_leaves_default_profile_skills_root_untouched(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            package = seed_skill_package(spec.skills_store_root, "audit", "Audit")
            (spec.hermes_home / "profiles" / "coder" / "skills").mkdir(parents=True)

            _adapter("hermes", spec).enable_shared_package(package, scope="coder")

            self.assertFalse((spec.hermes_home / "skills" / "harnessam" / "audit").exists())

    def test_scan_reports_broken_stale_and_detached_links_distinctly(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            for package_name in ("broken", "stale", "detached"):
                seed_skill_package(spec.skills_store_root, package_name, package_name.title())
            profile_skills = spec.hermes_home / "profiles" / "coder" / "skills"
            managed = profile_skills / "harnessam"
            managed.mkdir(parents=True)
            (managed / "broken").symlink_to("missing-package")
            foreign = seed_skill_package(Path(temp_dir) / "foreign", "stale", "Stale")
            (managed / "stale").symlink_to(foreign.resolve())
            archive = profile_skills / ".archive"
            archive.mkdir()
            (archive / "detached").symlink_to(
                (spec.skills_store_root / "detached").resolve()
            )

            scan = _adapter(
                "hermes",
                spec,
                data_dir=spec.xdg_data_home / APP_NAME,
            ).scan()

            self.assertEqual(
                {(issue.package_dir, issue.detail) for issue in scan.link_issues},
                {
                    ("broken", "broken-link"),
                    ("stale", "stale-link"),
                    ("detached", "detached-link"),
                },
            )
            stale = next(observation for observation in scan.skills if observation.package.root_path.name == "stale")
            self.assertEqual(stale.detail, "stale-link")
            inventory = SkillInventory.from_snapshot(
                store_scan=SkillStore(spec.skills_store_root).scan(),
                harness_scans=(scan,),
            )
            self.assertEqual(
                {
                    name: {
                        sighting.detail
                        for sighting in inventory.find(f"shared:{name}").sightings
                        if sighting.detail
                    }
                    for name in ("broken", "stale", "detached")
                },
                {
                    "broken": {"broken-link"},
                    "stale": {"stale-link"},
                    "detached": {"detached-link"},
                },
            )

    def test_archived_recorded_binding_relinks_without_harming_canonical_package(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            profile_skills = spec.hermes_home / "profiles" / "coder" / "skills"
            profile_skills.mkdir(parents=True)
            source = seed_skill_package(Path(temp_dir) / "source", "audit", "Audit")
            container = build_backend_container(spec.env())
            container.skills_store.ingest(
                source_path=source,
                declared_name="Audit",
                source_kind="centralized",
                source_locator="centralized:audit",
            )

            container.skills_mutations.enable_skill("shared:audit", "hermes:coder")
            link = profile_skills / "harnessam" / "audit"
            package = spec.skills_store_root / "audit"
            archive = profile_skills / ".archive"
            archive.mkdir()
            link.rename(archive / "audit")

            container.skills_read_models.invalidate()
            self.assertTrue(package.is_dir())
            self.assertEqual(
                container.skills_queries.inventory().find("shared:audit").package_path,
                package,
            )
            container.skills_mutations.enable_skill("shared:audit", "hermes:coder")

            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), package.resolve())
            self.assertTrue(package.is_dir())
            manifest = load_skill_store_manifest(container.paths.skills_store_manifest)
            self.assertEqual(manifest.entries[0].enabled_harnesses, ("hermes:coder",))

    def test_hermes_scoped_disable_preserves_other_profile_and_store(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            package = seed_skill_package(spec.skills_store_root, "audit", "Audit")
            for profile_name in ("coder", "reviewer"):
                (spec.hermes_home / "profiles" / profile_name / "skills").mkdir(
                    parents=True
                )

            hermes = _adapter("hermes", spec)
            hermes.enable_shared_package(package, scope="coder")
            hermes.enable_shared_package(package, scope="reviewer")
            hermes.disable_shared_package("audit", scope="coder")

            self.assertFalse(
                (
                    spec.hermes_home
                    / "profiles"
                    / "coder"
                    / "skills"
                    / "harnessam"
                    / "audit"
                ).exists()
            )
            self.assertTrue(
                (
                    spec.hermes_home
                    / "profiles"
                    / "reviewer"
                    / "skills"
                    / "harnessam"
                    / "audit"
                ).is_symlink()
            )
            self.assertTrue((package / "SKILL.md").is_file())

    def test_scoped_binding_refuses_foreign_symlink(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            package = seed_skill_package(spec.skills_store_root, "audit", "Audit")
            foreign = seed_skill_package(Path(temp_dir) / "foreign", "audit", "Foreign Audit")
            target = spec.hermes_home / "profiles" / "coder" / "skills" / "harnessam" / "audit"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(foreign)

            hermes = _adapter("hermes", spec)

            with self.assertRaises(MutationError):
                hermes.enable_shared_package(package, scope="coder")
            self.assertEqual(target.resolve(), foreign.resolve())

    def test_scoped_binding_heals_known_stale_store_symlink(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            stale = seed_skill_package(spec.legacy_skills_store_root, "audit", "Old Audit")
            package = seed_skill_package(spec.skills_store_root, "audit", "Audit")
            target = spec.hermes_home / "profiles" / "coder" / "skills" / "harnessam" / "audit"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.symlink_to(stale)

            hermes = _adapter("hermes", spec, data_dir=spec.xdg_data_home / APP_NAME)
            hermes.enable_shared_package(package, scope="coder")

            self.assertEqual(target.resolve(), package.resolve())

    def test_scoped_binding_respects_flat_layout_without_category_scan(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            package = seed_skill_package(root / "store", "audit", "Audit")
            managed_root = root / "managed"
            scoped_root = root / "profiles" / "coder" / "skills"
            adapter = FileTreeSkillsAdapter(
                harness="flat",
                label="Flat",
                logo_key=None,
                install_probe="flat",
                path_env=None,
                managed_root=managed_root,
                discovery_roots=(
                    _ResolvedRoot(
                        kind="managed-root",
                        scope="canonical",
                        label="Managed skills root",
                        path=managed_root,
                    ),
                ),
                availability="cli",
                app_probe_paths=(),
                layout="flat",
                scoped_root_resolver=lambda _scope: scoped_root,
            )

            adapter.enable_shared_package(package, scope="coder")

            self.assertTrue((scoped_root / "audit").is_symlink())
            self.assertFalse((scoped_root / "harnessam" / "audit").exists())

    def test_adapter_scans_discovery_roots_and_reports_installation(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            seed_skill_package(spec.codex_legacy_root, "trace-lens", "Trace Lens")
            seed_skill_package(spec.opencode_root, "watch", "Workspace Watch")
            seed_skill_package(spec.hermes_skills_root / "debugging", "trace", "Hermes Trace")
            hub_lock = spec.hermes_skills_root / ".hub" / "lock.json"
            hub_lock.parent.mkdir(parents=True, exist_ok=True)
            hub_lock.write_text(
                """{
  \"version\": 1,
  \"installed\": {
    \"trace\": {
      \"source\": \"github\",
      \"identifier\": \"github/example/hermes-trace\",
      \"trust_level\": \"community\",
      \"install_path\": \"debugging/trace\"
    }
  }
}
""",
                encoding="utf-8",
            )

            codex = _adapter("codex", spec)
            claude = _adapter("claude", spec)
            opencode = _adapter("opencode", spec)
            hermes = _adapter("hermes", spec)

            codex_scan = codex.scan()
            claude_scan = claude.scan()
            opencode_scan = opencode.scan()
            hermes_scan = hermes.scan()

            self.assertTrue(codex_scan.installed)
            self.assertEqual(codex_scan.skills[0].package.declared_name, "Trace Lens")
            self.assertTrue(claude_scan.installed)
            self.assertEqual(claude_scan.skills, ())
            self.assertTrue(opencode_scan.installed)
            self.assertEqual(
                [skill.package.declared_name for skill in opencode_scan.skills],
                ["Workspace Watch"],
            )
            self.assertTrue(hermes_scan.installed)
            self.assertEqual(
                [skill.package.declared_name for skill in hermes_scan.skills],
                ["Hermes Trace"],
            )
            self.assertEqual(hermes_scan.skills[0].package.source.kind, "github")
            self.assertEqual(
                hermes_scan.skills[0].package.source.locator,
                "github/example/hermes-trace",
            )

    def test_hermes_scan_only_includes_external_hub_skills_without_touching_files(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            bundled = seed_skill_package(
                spec.hermes_skills_root / "builtin",
                "bundled-core",
                "Bundled Core",
            )
            official = seed_skill_package(
                spec.hermes_skills_root / "optional",
                "official-helper",
                "Official Helper",
            )
            local = seed_skill_package(
                spec.hermes_skills_root / "local",
                "user-helper",
                "User Helper",
            )
            community_hub = seed_skill_package(
                spec.hermes_skills_root / "hub",
                "community-helper",
                "Community Helper",
            )
            (spec.hermes_skills_root / ".bundled_manifest").write_text(
                "Bundled Core:0123456789abcdef\n",
                encoding="utf-8",
            )
            hub_lock = spec.hermes_skills_root / ".hub" / "lock.json"
            hub_lock.parent.mkdir(parents=True, exist_ok=True)
            hub_lock.write_text(
                """{
  "version": 1,
  "installed": {
    "official-helper": {
      "source": "official",
      "identifier": "official/optional/official-helper",
      "trust_level": "builtin",
      "install_path": "optional/official-helper",
      "metadata": {"backfilled_from": "optional-skills"}
    },
    "community-helper": {
      "source": "github",
      "identifier": "github/example/community-helper",
      "trust_level": "community",
      "install_path": "hub/community-helper"
    }
  }
}
""",
                encoding="utf-8",
            )
            hermes = _adapter("hermes", spec)

            scan = hermes.scan()

            self.assertEqual(
                [skill.package.declared_name for skill in scan.skills],
                ["Community Helper", "User Helper"],
            )
            self.assertEqual(scan.skills[0].package.source.kind, "github")
            self.assertEqual(scan.skills[0].package.source.locator, "github/example/community-helper")
            self.assertEqual(scan.skills[1].package.source.kind, "harness-local")
            self.assertEqual(scan.skills[1].package.source.locator, "hermes:canonical:local/user-helper")
            self.assertIn("Bundled Core", scan.excluded_skill_names)
            self.assertIn("official-helper", scan.excluded_skill_names)
            self.assertNotIn("user-helper", scan.excluded_skill_names)
            self.assertTrue((bundled / "SKILL.md").is_file())
            self.assertTrue((official / "SKILL.md").is_file())
            self.assertFalse(bundled.is_symlink())
            self.assertFalse(official.is_symlink())
            self.assertTrue((local / "SKILL.md").is_file())
            self.assertTrue((community_hub / "SKILL.md").is_file())

    def test_adapter_reports_missing_cli_as_not_installed(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir), omit_clis=("opencode",))

            opencode = _adapter("opencode", spec)

            self.assertFalse(opencode.status().installed)
            self.assertEqual(opencode.scan().skills, ())

    def test_cursor_skills_use_skills_root_and_ignore_skills_cursor(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            seed_skill_package(spec.cursor_root, "managed-cursor", "Managed Cursor")
            seed_skill_package(spec.cursor_owned_root, "cursor-built", "Cursor Built")

            cursor = _adapter("cursor", spec)
            scan = cursor.scan()

            self.assertEqual(cursor.managed_root, spec.cursor_root)
            self.assertEqual(
                [skill.package.declared_name for skill in scan.skills],
                ["Managed Cursor"],
            )

    def test_cursor_app_probe_keeps_skills_adapter_installed_without_cli(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            (spec.bin_dir / "cursor-agent").unlink()
            (spec.home / "Applications" / "Cursor.app").mkdir(parents=True)

            cursor = _adapter("cursor", spec)
            kernel = HarnessKernelService.from_environment(
                spec.env(),
                support_store=HarnessSupportStore(spec.root / "settings.json"),
            )
            cursor_status = next(
                status for status in kernel.harness_statuses() if status.harness == "cursor"
            )

            self.assertTrue(cursor.status().installed)
            self.assertTrue(cursor_status.installed)
            self.assertEqual(cursor_status.managed_location, spec.cursor_root)

    def test_enable_creates_symlink(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            package = seed_skill_package(spec.skills_store_root, "audit", "Audit")
            codex = _adapter("codex", spec)

            codex.enable_shared_package(package)

            link = spec.codex_root / "audit"
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), package.resolve())

    def test_enable_refuses_real_directory(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            package = seed_skill_package(spec.skills_store_root, "audit", "Audit")
            seed_skill_package(spec.codex_root, "audit", "Local Audit")
            codex = _adapter("codex", spec)

            with self.assertRaises(MutationError) as ctx:
                codex.enable_shared_package(package)

            self.assertIn("real directory", str(ctx.exception))

    def test_adopt_local_copy_replaces_dir_with_symlink(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            store_pkg = seed_skill_package(spec.skills_store_root, "audit", "Audit")
            harness_pkg = seed_skill_package(spec.codex_root, "audit", "Audit")
            codex = _adapter("codex", spec)

            codex.adopt_local_copy(harness_pkg, store_pkg)

            self.assertTrue(harness_pkg.is_symlink())
            self.assertEqual(harness_pkg.resolve(), store_pkg.resolve())

    def test_materialize_binding_restores_real_directory(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            store_pkg = seed_skill_package(
                spec.skills_store_root,
                "audit",
                "Audit",
                body="shared version",
            )
            link = spec.codex_root / "audit"
            link.symlink_to(store_pkg.resolve())
            codex = _adapter("codex", spec)

            codex.materialize_binding("audit", store_pkg)

            self.assertTrue(link.is_dir())
            self.assertFalse(link.is_symlink())
            self.assertIn("shared version", (link / "SKILL.md").read_text(encoding="utf-8"))

    def test_hermes_enable_creates_symlink_under_default_category(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            package = seed_skill_package(spec.skills_store_root, "audit", "Audit")
            hermes = _adapter("hermes", spec)

            hermes.enable_shared_package(package)

            link = spec.hermes_skills_root / "harnessam" / "audit"
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), package.resolve())
            self.assertTrue(hermes.has_binding("audit"))

    def test_legacy_hermes_category_remains_discoverable(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            package = seed_skill_package(spec.skills_store_root, "audit", "Audit")
            legacy_category = spec.hermes_skills_root / "harness-asset-manager"
            legacy_category.mkdir(parents=True)
            legacy_link = legacy_category / "audit"
            legacy_link.symlink_to(package)

            hermes = _adapter("hermes", spec)
            self.assertTrue(hermes.has_binding("audit"))
            self.assertEqual(hermes._binding_path("audit"), legacy_link)

    def test_legacy_hermes_binding_is_not_replaced_when_enabling(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            package = seed_skill_package(spec.skills_store_root, "audit", "Audit")
            legacy_category = spec.hermes_skills_root / "harness-asset-manager"
            legacy_category.mkdir(parents=True)
            legacy_link = legacy_category / "audit"
            legacy_link.symlink_to(package)

            hermes = _adapter("hermes", spec)
            hermes.enable_shared_package(package)
            self.assertTrue(legacy_link.is_symlink())
            self.assertFalse((spec.hermes_skills_root / "harnessam" / "audit").exists())

    def test_hermes_enable_ignores_real_directory_in_existing_category(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            package = seed_skill_package(spec.skills_store_root, "audit", "Audit")
            hermes_owned = seed_skill_package(
                spec.hermes_skills_root / "local",
                "audit",
                "Hermes Audit",
            )
            hermes = _adapter("hermes", spec)

            self.assertFalse(hermes.has_binding("audit"))

            hermes.enable_shared_package(package)

            link = spec.hermes_skills_root / "harnessam" / "audit"
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), package.resolve())
            self.assertTrue((hermes_owned / "SKILL.md").is_file())
            self.assertFalse(hermes_owned.is_symlink())

    def test_hermes_disable_finds_symlink_in_existing_category(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            package = seed_skill_package(spec.skills_store_root, "audit", "Audit")
            link = spec.hermes_skills_root / "custom" / "audit"
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(package)
            hermes = _adapter("hermes", spec)

            hermes.disable_shared_package("audit")

            self.assertFalse(link.exists())
            self.assertFalse(link.is_symlink())


class StaleTargetHealingTests(unittest.TestCase):
    """Tests for symlink self-healing when targets point to old store locations."""

    def test_enable_heals_stale_shared_symlink(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            # Create old-shape directory structure
            stale_dir = spec.legacy_skills_store_root / "audit"
            stale_dir.mkdir(parents=True)
            (stale_dir / "SKILL.md").write_text("---\nname: Audit\n---\nold audit", encoding="utf-8")
            # Create new-flat skill in the store
            new_pkg = seed_skill_package(spec.skills_store_root, "audit", "Audit", body="new audit")
            # Create symlink in harness pointing to OLD location
            link = spec.codex_root / "audit"
            link.symlink_to(stale_dir.resolve())
            codex = _adapter("codex", spec, data_dir=spec.xdg_data_home / APP_NAME)

            # Should heal without raising
            codex.enable_shared_package(new_pkg)

            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), new_pkg.resolve())

    def test_enable_heals_stale_package_layout_symlink(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            # Create old-shape packages/local/skills directory structure
            stale_dir = spec.legacy_packages_skills_store_root / "audit"
            stale_dir.mkdir(parents=True, exist_ok=True)
            (stale_dir / "SKILL.md").write_text("---\nname: Audit\n---\nold", encoding="utf-8")
            # Create new-flat skill in the store
            new_pkg = seed_skill_package(spec.skills_store_root, "audit", "Audit", body="new")
            link = spec.codex_root / "audit"
            link.symlink_to(stale_dir.resolve())
            codex = _adapter("codex", spec, data_dir=spec.xdg_data_home / APP_NAME)

            codex.enable_shared_package(new_pkg)

            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), new_pkg.resolve())

    def test_enable_refuses_foreign_symlink(self) -> None:
        """A symlink to an unrelated location without data_dir should still raise."""
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            # Create a foreign dir (NOT under data_dir)
            foreign_dir = Path(temp_dir) / "foreign" / "audit"
            foreign_dir.mkdir(parents=True)
            (foreign_dir / "SKILL.md").write_text("---\nname: Audit\n---\nforeign", encoding="utf-8")
            new_pkg = seed_skill_package(spec.skills_store_root, "audit", "Audit", body="new")
            link = spec.codex_root / "audit"
            link.symlink_to(foreign_dir.resolve())
            codex = _adapter("codex", spec, data_dir=spec.xdg_data_home / APP_NAME)

            with self.assertRaises(MutationError) as ctx:
                codex.enable_shared_package(new_pkg)
            self.assertIn("symlink already exists", str(ctx.exception))

    def test_adopt_heals_stale_symlink(self) -> None:
        with TemporaryDirectory() as temp_dir:
            spec = create_fake_home_spec(Path(temp_dir))
            stale_dir = spec.legacy_skills_store_root / "audit"
            stale_dir.mkdir(parents=True)
            (stale_dir / "SKILL.md").write_text("---\nname: Audit\n---\nold", encoding="utf-8")
            new_pkg = seed_skill_package(spec.skills_store_root, "audit", "Audit", body="new")
            harness_dir = spec.codex_root / "audit"
            harness_dir.symlink_to(stale_dir.resolve())
            codex = _adapter("codex", spec, data_dir=spec.xdg_data_home / APP_NAME)

            codex.adopt_local_copy(harness_dir, new_pkg)

            self.assertTrue(harness_dir.is_symlink())
            self.assertEqual(harness_dir.resolve(), new_pkg.resolve())


if __name__ == "__main__":
    unittest.main()
