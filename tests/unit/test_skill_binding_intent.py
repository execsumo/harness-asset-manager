from __future__ import annotations

import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness_asset_manager.application.container import build_backend_container
from harness_asset_manager.application.skills.manifest import (
    SkillStoreEntry,
    SkillStoreManifest,
    load_skill_store_manifest,
    write_skill_store_manifest,
)
from harness_asset_manager.application.skills.store import SkillStore
from harness_asset_manager.paths import APP_NAME
from tests.support.fake_home import (
    FakeHomeSpec,
    create_fake_home_spec,
    seed_skill_package,
    write_cli_stub,
)


def _entry(package_dir: str = "audit", **overrides: object) -> SkillStoreEntry:
    fields: dict[str, object] = {
        "package_dir": package_dir,
        "declared_name": "Audit Skill",
        "source_kind": "centralized",
        "source_locator": "centralized:Audit Skill",
        "revision": "rev-1",
    }
    fields.update(overrides)
    return SkillStoreEntry(**fields)  # type: ignore[arg-type]


class SkillStoreEntryIntentTests(unittest.TestCase):
    """The manifest field itself: serialization, defaults, and hostile input."""

    def test_absent_field_loads_as_no_intent(self) -> None:
        """A manifest written before this field existed must still load."""
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(
                json.dumps({
                    "entries": [{
                        "packageDir": "audit",
                        "declaredName": "Audit Skill",
                        "sourceKind": "centralized",
                        "sourceLocator": "centralized:Audit Skill",
                        "revision": "rev-1",
                    }]
                }),
                encoding="utf-8",
            )
            manifest = load_skill_store_manifest(path)
            self.assertEqual(manifest.entries[0].enabled_harnesses, ())

    def test_empty_intent_is_omitted_from_json(self) -> None:
        """Stores that never bind keep byte-identical manifests to the old format."""
        self.assertNotIn("enabledHarnesses", _entry().to_dict())

    def test_round_trip_preserves_intent(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            write_skill_store_manifest(
                path,
                SkillStoreManifest(entries=(_entry(enabled_harnesses=("claude", "codex")),)),
            )
            self.assertEqual(
                load_skill_store_manifest(path).entries[0].enabled_harnesses,
                ("claude", "codex"),
            )

    def test_intent_is_sorted_and_deduplicated_on_read(self) -> None:
        """Stable ordering keeps a dotfiled manifest from churning in git diffs."""
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(
                json.dumps({
                    "entries": [{
                        "packageDir": "audit",
                        "declaredName": "Audit Skill",
                        "sourceKind": "centralized",
                        "sourceLocator": "centralized:Audit Skill",
                        "revision": "rev-1",
                        "enabledHarnesses": ["codex", "claude", "codex"],
                    }]
                }),
                encoding="utf-8",
            )
            self.assertEqual(
                load_skill_store_manifest(path).entries[0].enabled_harnesses,
                ("claude", "codex"),
            )

    def test_malformed_intent_degrades_instead_of_raising(self) -> None:
        """Corrupt intent costs a re-enable click; it must not break the inventory."""
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(
                json.dumps({
                    "entries": [
                        {
                            "packageDir": "a",
                            "declaredName": "A",
                            "sourceKind": "centralized",
                            "sourceLocator": "centralized:A",
                            "revision": "r",
                            "enabledHarnesses": "claude",
                        },
                        {
                            "packageDir": "b",
                            "declaredName": "B",
                            "sourceKind": "centralized",
                            "sourceLocator": "centralized:B",
                            "revision": "r",
                            "enabledHarnesses": ["claude", 7, None, "", "codex"],
                        },
                    ]
                }),
                encoding="utf-8",
            )
            entries = {e.package_dir: e for e in load_skill_store_manifest(path).entries}
            self.assertEqual(entries["a"].enabled_harnesses, ())
            self.assertEqual(entries["b"].enabled_harnesses, ("claude", "codex"))

    def test_with_binding_returns_self_when_unchanged(self) -> None:
        """Identity is the signal record_binding uses to skip a manifest write."""
        entry = _entry(enabled_harnesses=("claude",))
        self.assertIs(entry.with_binding("claude", bound=True), entry)
        self.assertIs(entry.with_binding("codex", bound=False), entry)
        self.assertEqual(entry.with_binding("codex", bound=True).enabled_harnesses, ("claude", "codex"))
        self.assertEqual(entry.with_binding("claude", bound=False).enabled_harnesses, ())


class SkillStoreRecordBindingTests(unittest.TestCase):
    def _store(self, tmp: str) -> SkillStore:
        spec = create_fake_home_spec(Path(tmp))
        source = seed_skill_package(spec.home / ".codex" / "skills", "audit", "Audit Skill")
        store = SkillStore(spec.skills_store_root)
        store.ingest(
            source_path=source,
            declared_name="Audit Skill",
            source_kind="centralized",
            source_locator="centralized:Audit Skill",
        )
        return store

    def test_record_binding_adds_and_removes(self) -> None:
        with TemporaryDirectory() as tmp:
            store = self._store(tmp)
            store.record_binding("audit", "claude", bound=True)
            store.record_binding("audit", "codex", bound=True)
            self.assertEqual(
                load_skill_store_manifest(store.manifest_path).entries[0].enabled_harnesses,
                ("claude", "codex"),
            )
            store.record_binding("audit", "claude", bound=False)
            self.assertEqual(
                load_skill_store_manifest(store.manifest_path).entries[0].enabled_harnesses,
                ("codex",),
            )

    def test_record_binding_ignores_unknown_package(self) -> None:
        """An unmanaged or concurrently-deleted skill is a silent no-op, not an error."""
        with TemporaryDirectory() as tmp:
            store = self._store(tmp)
            before = store.manifest_path.read_text(encoding="utf-8")
            store.record_binding("not-in-store", "claude", bound=True)
            self.assertEqual(store.manifest_path.read_text(encoding="utf-8"), before)

    def test_update_preserves_recorded_intent(self) -> None:
        """Regression: update() rebuilds the entry and used to drop added fields."""
        with TemporaryDirectory() as tmp:
            spec = create_fake_home_spec(Path(tmp))
            store = self._store(tmp)
            store.record_binding("audit", "claude", bound=True)

            newer = seed_skill_package(spec.home / ".codex" / "skills-v2", "audit", "Audit Skill v2")
            _dest, changed = store.update("audit", source_path=newer, source_ref="v2")

            self.assertTrue(changed)
            entry = load_skill_store_manifest(store.manifest_path).entries[0]
            self.assertEqual(entry.source_ref, "v2")
            self.assertEqual(entry.enabled_harnesses, ("claude",))


class SkillBindingIntentSurvivesSyncTests(unittest.TestCase):
    """The point of the field: intent that a copied store carries to a new device."""

    def _spec(self, root: Path, user: str) -> FakeHomeSpec:
        spec = FakeHomeSpec(
            root=root,
            home=root / "home" / user,
            xdg_config_home=root / "home" / user / ".config",
            xdg_data_home=root / "home" / user / ".local" / "share",
            xdg_state_home=root / "home" / user / ".local" / "state",
        )
        for path in (
            spec.skills_store_root,
            spec.agents_root,
            spec.codex_root,
            spec.claude_root,
            spec.xdg_state_home,
            spec.bin_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
        for executable in ("codex", "claude"):
            write_cli_stub(spec.bin_dir / executable, executable)
        return spec

    def test_enabling_on_machine_a_is_readable_on_machine_b(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            spec_a = self._spec(tmp_path / "machine-a", "alice")
            spec_b = self._spec(tmp_path / "machine-b", "bob")

            container_a = build_backend_container(spec_a.env())
            staged = seed_skill_package(spec_a.home / "staging", "shared-audit", "Shared Audit")
            package_a = container_a.skills_store.ingest(
                source_path=staged,
                declared_name="Shared Audit",
                source_kind="centralized",
                source_locator="centralized:Shared Audit",
            )
            container_a.skills_mutations.enable_managed_package(package_a, "claude")

            # Machine B receives only the store — no ~/.claude, no symlinks.
            store_a = spec_a.xdg_data_home / APP_NAME
            store_b = spec_b.xdg_data_home / APP_NAME
            if store_b.exists():
                shutil.rmtree(store_b)
            shutil.copytree(store_a, store_b)

            container_b = build_backend_container(spec_b.env())
            manifest_b = load_skill_store_manifest(container_b.skills_store.manifest_path)
            entry_b = next(e for e in manifest_b.entries if e.package_dir == "shared-audit")

            # Intent crossed the sync...
            self.assertEqual(entry_b.enabled_harnesses, ("claude",))
            # ...while enablement is still derived from B's disk, which has no link yet.
            self.assertFalse((spec_b.claude_root / "shared-audit").exists())


if __name__ == "__main__":
    unittest.main()
