from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness_asset_manager.application.container import build_backend_container
from harness_asset_manager.application.skills.identity import SourceDescriptor
from harness_asset_manager.application.skills.inventory import (
    InventoryColumn,
    InventoryEntry,
    InventorySighting,
)
from harness_asset_manager.application.skills.manifest import (
    SkillStoreEntry,
    SkillStoreManifest,
    load_skill_store_manifest,
    write_skill_store_manifest,
)
from harness_asset_manager.application.skills.presenters import linked_harness_labels
from harness_asset_manager.harness.binding_targets import BindingTarget
from tests.support.fake_home import create_fake_home_spec, seed_skill_package


def _entry(**overrides: object) -> SkillStoreEntry:
    fields: dict[str, object] = {
        "package_dir": "audit",
        "declared_name": "Audit Skill",
        "source_kind": "centralized",
        "source_locator": "centralized:audit",
        "revision": "rev-1",
    }
    fields.update(overrides)
    return SkillStoreEntry(**fields)  # type: ignore[arg-type]


class BindingTargetTests(unittest.TestCase):
    def test_round_trips_harness_wide_and_scoped_targets(self) -> None:
        self.assertEqual(BindingTarget.parse("hermes"), BindingTarget("hermes", None))
        self.assertEqual(str(BindingTarget.parse("hermes")), "hermes")
        self.assertEqual(BindingTarget.parse("hermes:coder"), BindingTarget("hermes", "coder"))
        self.assertEqual(str(BindingTarget.parse("hermes:coder")), "hermes:coder")

    def test_empty_harness_part_degrades_to_unscoped_remainder(self) -> None:
        self.assertEqual(BindingTarget.parse(":coder"), BindingTarget("coder", None))

    def test_empty_scope_part_degrades_to_harness_wide_target(self) -> None:
        self.assertEqual(BindingTarget.parse("hermes:"), BindingTarget("hermes", None))

    def test_empty_value_degrades_without_raising(self) -> None:
        self.assertEqual(BindingTarget.parse(""), BindingTarget("", None))


class BindingTargetPersistenceTests(unittest.TestCase):
    def test_scoped_intent_reload_is_byte_identical(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            write_skill_store_manifest(
                path,
                SkillStoreManifest(entries=(_entry(enabled_harnesses=("hermes:coder",)),)),
            )
            before = path.read_bytes()
            write_skill_store_manifest(path, load_skill_store_manifest(path))
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(load_skill_store_manifest(path).entries[0].enabled_harnesses, ("hermes:coder",))

    def test_unscoped_store_is_unchanged_by_load_save(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            write_skill_store_manifest(path, SkillStoreManifest(entries=(_entry(),)))
            before = path.read_bytes()
            write_skill_store_manifest(path, load_skill_store_manifest(path))
            self.assertEqual(path.read_bytes(), before)
            self.assertNotIn("enabledHarnesses", json.loads(path.read_text(encoding="utf-8"))["entries"][0])


class ScopedInventoryTests(unittest.TestCase):
    def _entry_with_targets(self, targets: tuple[str, ...]) -> InventoryEntry:
        entry = InventoryEntry(
            skill_ref="shared:audit",
            name="Audit Skill",
            description="",
            kind="managed",
            source=SourceDescriptor("centralized", "centralized:audit"),
        )
        for target in targets:
            entry.add_sighting(
                InventorySighting(
                    kind="harness",
                    harness=target,
                    label="Hermes",
                    scope="canonical",
                    path=None,
                    revision="rev-1",
                    source=entry.source,
                )
            )
        return entry

    def test_scoped_binding_lights_harness_column(self) -> None:
        entry = self._entry_with_targets(("hermes:coder",))
        columns = (InventoryColumn("hermes", "Hermes", "hermes", True),)
        self.assertEqual(linked_harness_labels(entry, columns), ["Hermes"])

    def test_multiple_scoped_bindings_remain_visible_and_light_once(self) -> None:
        entry = self._entry_with_targets(("hermes:coder", "hermes:reviewer"))
        columns = (InventoryColumn("hermes", "Hermes", "hermes", True),)
        self.assertEqual(entry.linked_targets(), {"hermes:coder", "hermes:reviewer"})
        self.assertEqual(linked_harness_labels(entry, columns), ["Hermes"])


class ScopedBootstrapTests(unittest.TestCase):
    def test_missing_scope_is_proposed_and_mixed_apply_continues(self) -> None:
        with TemporaryDirectory() as tmp:
            spec = create_fake_home_spec(Path(tmp))
            container = build_backend_container(spec.env())
            source = seed_skill_package(spec.home / "downloads", "audit", "Audit Skill")
            container.skills_store.ingest(
                source_path=source,
                declared_name="Audit Skill",
                source_kind="centralized",
                source_locator="centralized:audit",
            )
            container.skills_store.record_binding("audit", "hermes:coder", bound=True)
            container.skills_store.record_binding("audit", "claude", bound=True)

            plan = container.bootstrap_planner.plan()
            missing = next(action for action in plan.actions if action.binding_target == "hermes:coder")
            linkable = next(action for action in plan.linkable if action.harness == "claude")
            self.assertEqual(missing.reason, "harness-scope-missing")
            self.assertIsNone(missing.target)  # no path exists for a profile this device lacks
            self.assertEqual(missing.target_display, "")
            self.assertIn("coder", missing.detail or "")

            results = container.bootstrap_applier.apply([missing, linkable])
            self.assertEqual([result.status for result in results], ["skipped", "applied"])
            self.assertIn("coder", results[0].error or "")
            self.assertTrue((spec.claude_root / "audit").is_symlink())
