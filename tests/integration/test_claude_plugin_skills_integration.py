from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest import TestCase

from harness_asset_manager.application.skills.mutations import SkillsMutationService
from harness_asset_manager.application.skills.queries import SkillsQueryService
from harness_asset_manager.errors import MutationError
from tests.support.app_harness import AppTestHarness
from tests.support.fake_home import FakeHomeSpec, seed_skill_package


def _dir_hash(path: Path) -> str:
    """Compute a deterministic hash of all files in a directory."""
    hasher = hashlib.sha256()
    for file in sorted(path.rglob("*")):
        if file.is_file():
            hasher.update(file.relative_to(path).as_posix().encode("utf-8"))
            hasher.update(file.read_bytes())
    return hasher.hexdigest()


class ClaudePluginSkillsIntegrationTests(TestCase):
    def test_unmanaged_plugin_skill_discovery_and_adoption(self) -> None:
        def fixture(spec: FakeHomeSpec) -> None:
            plugin_dir = spec.home / ".claude" / "plugins" / "cache" / "market" / "agtx" / "0.1.0"
            seed_skill_package(plugin_dir / "skills", "brainstorm", "brainstorm", description="Explore ideas")

            registry_data = {
                "version": 2,
                "plugins": {
                    "agtx@market": [
                        {
                            "installPath": str(plugin_dir),
                            "version": "0.1.0",
                            "installedAt": "2026-09-01T00:00:00Z",
                        }
                    ]
                },
            }
            spec.claude_plugins_registry.parent.mkdir(parents=True, exist_ok=True)
            spec.claude_plugins_registry.write_text(json.dumps(registry_data), encoding="utf-8")

        with AppTestHarness(fixture_factory=fixture) as harness:
            queries = harness.container.skills_queries
            mutations = harness.container.skills_mutations

            # 1. Verify unmanaged discovery
            inv = queries.inventory()
            entries = [e for e in inv.entries if e.name == "brainstorm"]
            self.assertEqual(len(entries), 1)
            entry = entries[0]
            self.assertEqual(entry.kind, "unmanaged")
            self.assertEqual(entry.source.kind, "harness-local")
            self.assertEqual(entry.source.locator, "claude:plugin:agtx@market@0.1.0:brainstorm")

            # Check sighting details
            harness_sightings = [s for s in entry.sightings if s.harness == "claude"]
            self.assertEqual(len(harness_sightings), 1)
            sighting = harness_sightings[0]
            self.assertEqual(sighting.scope, "plugin")
            self.assertIn("Claude Plugin", sighting.label)
            self.assertIn("agtx@market@0.1.0", sighting.label)

            # 2. Verify editing unmanaged plugin skill directly is refused
            with self.assertRaises(MutationError) as cm:
                mutations.update_skill_document(entry.skill_ref, body="new content")
            self.assertIn("plugin skills are read-only until adopted", str(cm.exception))

            # 3. Adopt the skill
            plugin_skill_dir = harness.spec.home / ".claude" / "plugins" / "cache" / "market" / "agtx" / "0.1.0" / "skills" / "brainstorm"
            hash_before_adopt = _dir_hash(plugin_skill_dir)

            result = mutations.manage_skill(entry.skill_ref)
            self.assertTrue(result.get("ok"))

            # 4. Verify post-adoption state
            # Plugin cache directory MUST NOT be modified or deleted
            self.assertTrue(plugin_skill_dir.is_dir())
            hash_after_adopt = _dir_hash(plugin_skill_dir)
            self.assertEqual(hash_before_adopt, hash_after_adopt)

            # Central store has the ingested package
            store_dir = harness.spec.skills_store_root / "brainstorm"
            self.assertTrue(store_dir.is_dir())

            # Claude managed root has a symlink pointing to the store
            claude_binding = harness.spec.claude_root / "brainstorm"
            self.assertTrue(claude_binding.is_symlink())
            self.assertEqual(claude_binding.resolve(), store_dir.resolve())

            # Re-query inventory: skill is now Managed
            inv_after = queries.inventory()
            managed_entries = [e for e in inv_after.entries if e.name == "brainstorm"]
            self.assertEqual(len(managed_entries), 1)
            m_entry = managed_entries[0]
            self.assertEqual(m_entry.kind, "managed")
            self.assertEqual(m_entry.skill_ref, "shared:brainstorm")

            # Sightings include shared store, canonical claude binding, and plugin cache location
            scopes = {s.scope for s in m_entry.sightings}
            self.assertIn("canonical", scopes)
            self.assertIn("plugin", scopes)

            # 5. Delete managed skill: removes binding and store copy, never touches plugin cache
            del_result = mutations.delete_skill(m_entry.skill_ref)
            self.assertTrue(del_result.get("ok"))
            self.assertFalse(store_dir.exists())
            self.assertFalse(claude_binding.exists())

            # Plugin cache remains completely intact!
            self.assertTrue(plugin_skill_dir.is_dir())
            self.assertEqual(_dir_hash(plugin_skill_dir), hash_before_adopt)

    def test_pressure_edge_cases_and_traversal_protection(self) -> None:
        """Pressure test with malformed registry, path traversal, stale paths, decoys, duplicate records, and symlinks."""
        def fixture(spec: FakeHomeSpec) -> None:
            cache_root = spec.home / ".claude" / "plugins" / "cache"

            # 1. Valid plugin A (v1 stale, v2 active)
            pkg_a_v1 = cache_root / "market" / "pkg-a" / "1.0.0"
            seed_skill_package(pkg_a_v1 / "skills", "skill-a", "skill-a", body="V1 Old content")

            pkg_a_v2 = cache_root / "market" / "pkg-a" / "2.0.0"
            seed_skill_package(pkg_a_v2 / "skills", "skill-a", "skill-a", body="V2 New content")

            # Add decoy SKILL.md files inside pkg_a_v2 that must NOT be imported
            for decoy_rel in ("tests/unit", "examples/demo", "benchmarks", "vendor/nested"):
                decoy_dir = pkg_a_v2 / decoy_rel / "decoy-skill"
                decoy_dir.mkdir(parents=True, exist_ok=True)
                (decoy_dir / "SKILL.md").write_text("# Decoy\nShould not be imported", encoding="utf-8")

            # 2. Valid plugin B with symlinked install path
            real_b = cache_root / "market" / "pkg-b-real" / "1.0.0"
            seed_skill_package(real_b / "skills", "skill-b", "skill-b")
            symlink_b = cache_root / "market" / "pkg-b-symlink" / "1.0.0"
            symlink_b.parent.mkdir(parents=True, exist_ok=True)
            symlink_b.symlink_to(real_b)

            # 3. Malicious plugin C attempting path traversal via plugin.json
            evil_c = cache_root / "market" / "pkg-evil" / "1.0.0"
            evil_c.mkdir(parents=True, exist_ok=True)
            evil_manifest_dir = evil_c / ".claude-plugin"
            evil_manifest_dir.mkdir(parents=True, exist_ok=True)
            (evil_manifest_dir / "plugin.json").write_text(
                json.dumps({"name": "evil", "skills": "../../../../../../../../etc"}),
                encoding="utf-8",
            )

            # Build stressful installed_plugins.json
            registry_data = {
                "version": 2,
                "plugins": {
                    # Plugin A: has two entries (v1 older, v2 newer)
                    "pkg-a@market": [
                        {
                            "installPath": str(pkg_a_v1),
                            "version": "1.0.0",
                            "lastUpdated": "2026-08-01T00:00:00Z",
                        },
                        {
                            "installPath": str(pkg_a_v2),
                            "version": "2.0.0",
                            "lastUpdated": "2026-09-01T00:00:00Z",
                        },
                    ],
                    # Duplicate entry pointing to same real path as symlink_b
                    "pkg-b1@market": [{"installPath": str(real_b), "version": "1.0.0"}],
                    "pkg-b2@market": [{"installPath": str(symlink_b), "version": "1.0.0"}],
                    # Missing/stale install path
                    "stale-ghost@market": [{"installPath": "/nonexistent/path/on/disk", "version": "9.9.9"}],
                    # Malicious plugin attempting traversal
                    "evil@market": [{"installPath": str(evil_c), "version": "1.0.0"}],
                    # Malformed record (missing installPath)
                    "broken-entry": [{"notInstallPath": 123}],
                    # Malformed records type (string instead of list/dict)
                    "string-record": "not a record",
                },
            }

            spec.claude_plugins_registry.parent.mkdir(parents=True, exist_ok=True)
            spec.claude_plugins_registry.write_text(json.dumps(registry_data), encoding="utf-8")

        with AppTestHarness(fixture_factory=fixture) as harness:
            queries = harness.container.skills_queries
            inv = queries.inventory()

            discovered_names = {e.name for e in inv.entries}

            # 1. Legitimate skills ARE discovered
            self.assertIn("skill-a", discovered_names)
            self.assertIn("skill-b", discovered_names)

            # 2. Skill A is from v2 (newest), NOT v1
            skill_a = next(e for e in inv.entries if e.name == "skill-a")
            self.assertEqual(skill_a.source.locator, "claude:plugin:pkg-a@market@2.0.0:skill-a")

            # 3. Duplicate symlinked skill-b produced only ONE inventory entry (deduped)
            skill_b_entries = [e for e in inv.entries if e.name == "skill-b"]
            self.assertEqual(len(skill_b_entries), 1)

            # 4. Decoys NOT imported
            self.assertNotIn("decoy-skill", discovered_names)
            self.assertNotIn("etc", discovered_names)
            self.assertNotIn("evil", discovered_names)
            self.assertNotIn("stale-ghost", discovered_names)
