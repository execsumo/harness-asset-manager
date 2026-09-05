from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase

from harness_asset_manager.application.skills.adapters import FileTreeSkillsAdapter, _ResolvedRoot
from harness_asset_manager.application.skills.auto_adopt import SkillsAutoAdoptService
from harness_asset_manager.application.skills.identity import SourceDescriptor
from harness_asset_manager.application.skills.inventory import InventoryEntry, InventorySighting
from harness_asset_manager.application.skills.package import SkillPackageCache
from harness_asset_manager.errors import MutationError
from harness_asset_manager.harness.catalog import supported_harness_definitions
from harness_asset_manager.harness.claude_plugins import (
    _find_plugin_skill_roots,
    resolve_candidate_install_path,
    resolve_claude_plugin_roots,
)
from harness_asset_manager.harness.resolution import resolve_context
from tests.support.fake_home import FakeHomeSpec, seed_skill_package


class ClaudePluginSkillsUnitTests(TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory(prefix="test-claude-plugins-")
        self.home = Path(self.temp_dir.name)
        self.claude_skills = self.home / ".claude" / "skills"
        self.claude_skills.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.home / ".claude" / "plugins" / "installed_plugins.json"
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        self.context = resolve_context({"HOME": str(self.home)})

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _write_registry(self, data: object) -> None:
        self.registry_path.write_text(json.dumps(data), encoding="utf-8")

    def _create_plugin(
        self,
        rel_path: str,
        *,
        skills: tuple[str, ...] = ("my-skill",),
        manifest: dict | None = None,
    ) -> Path:
        install_dir = self.home / ".claude" / "plugins" / "cache" / rel_path
        install_dir.mkdir(parents=True, exist_ok=True)

        if manifest is not None:
            manifest_dir = install_dir / ".claude-plugin"
            manifest_dir.mkdir(parents=True, exist_ok=True)
            (manifest_dir / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")

        for skill_name in skills:
            seed_skill_package(install_dir / "skills", skill_name, skill_name)
        return install_dir

    def test_missing_registry_returns_empty_tuple(self) -> None:
        # Registry does not exist
        if self.registry_path.exists():
            self.registry_path.unlink()
        roots = resolve_claude_plugin_roots(self.context)
        self.assertEqual(roots, ())

    def test_malformed_json_returns_empty_tuple(self) -> None:
        self.registry_path.write_text("{{not valid json", encoding="utf-8")
        roots = resolve_claude_plugin_roots(self.context)
        self.assertEqual(roots, ())

    def test_invalid_structure_tolerated(self) -> None:
        # Array instead of object
        self._write_registry([1, 2, 3])
        self.assertEqual(resolve_claude_plugin_roots(self.context), ())

        # Missing plugins dict
        self._write_registry({"version": 2})
        self.assertEqual(resolve_claude_plugin_roots(self.context), ())

        # Non-dict plugins
        self._write_registry({"version": 2, "plugins": "invalid"})
        self.assertEqual(resolve_claude_plugin_roots(self.context), ())

    def test_stale_missing_install_path_ignored(self) -> None:
        self._write_registry({
            "version": 2,
            "plugins": {
                "ghost-plugin@marketplace": [
                    {
                        "installPath": str(self.home / ".claude" / "plugins" / "cache" / "nonexistent" / "1.0.0"),
                        "version": "1.0.0",
                    }
                ]
            },
        })
        roots = resolve_claude_plugin_roots(self.context)
        self.assertEqual(roots, ())

    def test_valid_registry_with_standard_skills_layout(self) -> None:
        install_dir = self._create_plugin("market/agtx/0.1.0", skills=("brainstorm", "sweep"))
        self._write_registry({
            "version": 2,
            "plugins": {
                "agtx@market": [
                    {
                        "installPath": str(install_dir),
                        "version": "0.1.0",
                        "installedAt": "2026-09-01T00:00:00Z",
                    }
                ]
            },
        })

        roots = resolve_claude_plugin_roots(self.context)
        self.assertEqual(len(roots), 2)
        paths = {root.path_resolver(self.context) for root in roots}
        self.assertEqual(
            paths,
            {
                (install_dir / "skills" / "brainstorm").resolve(),
                (install_dir / "skills" / "sweep").resolve(),
            },
        )
        for root in roots:
            self.assertEqual(root.kind, "plugin-root")
            self.assertEqual(root.scope, "plugin")
            self.assertEqual(root.locator_prefix, "agtx@market@0.1.0")
            self.assertEqual(root.label, "Claude Plugin (agtx@market@0.1.0)")

    def test_manifest_declared_skills_directory(self) -> None:
        install_dir = self.home / ".claude" / "plugins" / "cache" / "custom" / "tool/1.0.0"
        install_dir.mkdir(parents=True, exist_ok=True)
        custom_skills_dir = install_dir / "custom-skills"
        seed_skill_package(custom_skills_dir, "custom-one", "custom-one")

        manifest = {"name": "tool", "skills": "./custom-skills"}
        manifest_dir = install_dir / ".claude-plugin"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        (manifest_dir / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")

        self._write_registry({
            "version": 2,
            "plugins": {
                "tool@custom": [
                    {
                        "installPath": str(install_dir),
                        "version": "1.0.0",
                    }
                ]
            },
        })

        roots = resolve_claude_plugin_roots(self.context)
        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0].path_resolver(self.context), (custom_skills_dir / "custom-one").resolve())

    def test_manifest_declared_single_skill_file(self) -> None:
        install_dir = self.home / ".claude" / "plugins" / "cache" / "single" / "1.0.0"
        install_dir.mkdir(parents=True, exist_ok=True)
        single_skill_dir = install_dir / "single-skill"
        seed_skill_package(install_dir, "single-skill", "single-skill")

        manifest = {"name": "single", "skills": "./single-skill/SKILL.md"}
        (install_dir / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")

        self._write_registry({
            "version": 2,
            "plugins": {
                "single": [
                    {
                        "installPath": str(install_dir),
                        "version": "1.0.0",
                    }
                ]
            },
        })

        roots = resolve_claude_plugin_roots(self.context)
        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0].path_resolver(self.context), single_skill_dir.resolve())

    def test_path_traversal_in_manifest_skills_rejected(self) -> None:
        install_dir = self._create_plugin("unsafe/evil/1.0.0", skills=())
        manifest = {"name": "evil", "skills": "../../../../../etc"}
        manifest_dir = install_dir / ".claude-plugin"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        (manifest_dir / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")

        self._write_registry({
            "version": 2,
            "plugins": {
                "evil": [{"installPath": str(install_dir), "version": "1.0.0"}]
            },
        })

        roots = resolve_claude_plugin_roots(self.context)
        self.assertEqual(roots, ())

    def test_nested_unrelated_skill_md_not_imported(self) -> None:
        install_dir = self._create_plugin("nested/plugin/1.0.0", skills=("legit-skill",))

        # Decoy skill files in test, example, vendor, benchmark directories
        for decoy in ("tests/fixtures", "examples/sample", "vendor/bundled", "benchmarks/cases"):
            decoy_dir = install_dir / decoy / "decoy-skill"
            decoy_dir.mkdir(parents=True, exist_ok=True)
            (decoy_dir / "SKILL.md").write_text("# Decoy Skill\nFake content", encoding="utf-8")

        self._write_registry({
            "version": 2,
            "plugins": {
                "nested": [{"installPath": str(install_dir), "version": "1.0.0"}]
            },
        })

        roots = resolve_claude_plugin_roots(self.context)
        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0].path_resolver(self.context), (install_dir / "skills" / "legit-skill").resolve())

    def test_multiple_versions_prefers_active_installed_entry(self) -> None:
        v1_dir = self._create_plugin("market/agtx/0.1.0", skills=("v1-skill",))
        v2_dir = self._create_plugin("market/agtx/0.2.0", skills=("v2-skill",))

        self._write_registry({
            "version": 2,
            "plugins": {
                "agtx@market": [
                    {
                        "installPath": str(v1_dir),
                        "version": "0.1.0",
                        "installedAt": "2026-08-01T00:00:00Z",
                    },
                    {
                        "installPath": str(v2_dir),
                        "version": "0.2.0",
                        "installedAt": "2026-09-01T00:00:00Z",
                    },
                ]
            },
        })

        roots = resolve_claude_plugin_roots(self.context)
        # Should pick v2 (most recent)
        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0].path_resolver(self.context), (v2_dir / "skills" / "v2-skill").resolve())
        self.assertEqual(roots[0].locator_prefix, "agtx@market@0.2.0")

    def test_deduplication_of_duplicate_registry_records(self) -> None:
        install_dir = self._create_plugin("market/dup/1.0.0", skills=("dup-skill",))

        self._write_registry({
            "version": 2,
            "plugins": {
                "dup1@market": [{"installPath": str(install_dir), "version": "1.0.0"}],
                "dup2@market": [{"installPath": str(install_dir), "version": "1.0.0"}],
            },
        })

        roots = resolve_claude_plugin_roots(self.context)
        # Same install path should not produce duplicate roots
        self.assertEqual(len(roots), 1)

    def test_symlinked_install_path_handled_safely(self) -> None:
        real_dir = self._create_plugin("real/pkg/1.0.0", skills=("symlinked-skill",))
        link_dir = self.home / ".claude" / "plugins" / "cache" / "link" / "pkg"
        link_dir.parent.mkdir(parents=True, exist_ok=True)
        link_dir.symlink_to(real_dir)

        self._write_registry({
            "version": 2,
            "plugins": {
                "sym@market": [{"installPath": str(link_dir), "version": "1.0.0"}]
            },
        })

        roots = resolve_claude_plugin_roots(self.context)
        self.assertEqual(len(roots), 1)
        self.assertEqual(roots[0].path_resolver(self.context), (real_dir / "skills" / "symlinked-skill").resolve())

    def test_adapter_scans_both_canonical_and_plugin_roots(self) -> None:
        # Seed canonical skill
        seed_skill_package(self.claude_skills, "canonical-skill", "canonical-skill")
        # Seed plugin skill
        plugin_dir = self._create_plugin("market/agtx/0.1.0", skills=("plugin-skill",))
        self._write_registry({
            "version": 2,
            "plugins": {
                "agtx@market": [{"installPath": str(plugin_dir), "version": "0.1.0"}]
            },
        })

        adapter = FileTreeSkillsAdapter(
            harness="claude",
            label="Claude",
            logo_key="claude",
            install_probe="claude",
            path_env=None,
            managed_root=self.claude_skills,
            discovery_roots=(
                _ResolvedRoot(
                    kind="managed-root",
                    scope="canonical",
                    label="Managed skills root",
                    path=self.claude_skills,
                ),
            ),
            availability="cli",
            app_probe_paths=(),
            package_cache=SkillPackageCache(),
        )

        scan = adapter.scan()
        declared_names = {s.package.declared_name for s in scan.skills}
        self.assertIn("canonical-skill", declared_names)
        self.assertIn("plugin-skill", declared_names)

        plugin_obs = next(s for s in scan.skills if s.package.declared_name == "plugin-skill")
        self.assertEqual(plugin_obs.scope, "plugin")
        self.assertEqual(
            plugin_obs.package.source,
            SourceDescriptor(kind="harness-local", locator="claude:plugin:agtx@market@0.1.0:plugin-skill"),
        )
        self.assertIn("agtx@market@0.1.0", plugin_obs.label)

    def test_auto_adopt_service_refuses_plugin_skills(self) -> None:
        entry = InventoryEntry(
            skill_ref="unmanaged:test",
            name="plugin-skill",
            description="",
            kind="unmanaged",
            source=SourceDescriptor(kind="harness-local", locator="claude:plugin:agtx@0.1.0:plugin-skill"),
            sightings=[
                InventorySighting(
                    kind="harness",
                    harness="claude",
                    label="Claude Plugin",
                    scope="plugin",
                    path=self.home / "some" / "plugin" / "path",
                    revision="rev1",
                    source=SourceDescriptor(kind="harness-local", locator="claude:plugin:agtx@0.1.0:plugin-skill"),
                )
            ],
        )
        reason = SkillsAutoAdoptService._unsafe_reason(entry)
        self.assertEqual(reason, "plugin skills require explicit adoption")
