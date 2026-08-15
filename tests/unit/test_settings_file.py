from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock

from harness_asset_manager.application.settings.auto_adopt import (
    DEFAULTS,
    AutoAdoptStore,
)
from harness_asset_manager.application.settings.mutations import (
    SettingsMutationService,
)
from harness_asset_manager.harness.support_store import HarnessSupportStore
from harness_asset_manager.settings_file import (
    load_settings_document,
    update_settings_document,
)


class SettingsDocumentTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "settings.json"

    def test_missing_or_malformed_reads_as_an_empty_document(self) -> None:
        self.assertEqual(load_settings_document(self.path), {})
        self.path.write_text("{not json", encoding="utf-8")
        self.assertEqual(load_settings_document(self.path), {})
        self.path.write_text("[]", encoding="utf-8")
        self.assertEqual(load_settings_document(self.path), {})

    def test_update_preserves_keys_it_does_not_own(self) -> None:
        self.path.write_text(json.dumps({"somethingElse": {"a": 1}}), encoding="utf-8")
        update_settings_document(self.path, lambda doc: doc.update({"mine": True}))
        stored = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(stored["somethingElse"], {"a": 1})
        self.assertTrue(stored["mine"])


class SharedSettingsFileTests(unittest.TestCase):
    """settings.json has more than one writer. A store that serialises only its own
    keys silently deletes every other store's — this is the regression guard."""

    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "settings.json"
        self.support = HarnessSupportStore(self.path)
        self.auto_adopt = AutoAdoptStore(self.path)

    def test_toggling_a_harness_does_not_wipe_the_auto_adopt_setting(self) -> None:
        self.auto_adopt.set_default_harnesses("agents", ("claude",))
        self.support.set_enabled("cursor", False)

        self.assertTrue(self.auto_adopt.is_enabled("agents"))
        self.assertEqual(self.support.load().disabled_harnesses, ("cursor",))

    def test_toggling_auto_adopt_does_not_wipe_disabled_harnesses(self) -> None:
        self.support.set_enabled("cursor", False)
        self.auto_adopt.set_default_harnesses("skills", ("claude",))

        self.assertEqual(self.support.load().disabled_harnesses, ("cursor",))
        self.assertTrue(self.auto_adopt.is_enabled("skills"))

    def test_unrelated_keys_survive_both_writers(self) -> None:
        self.path.write_text(json.dumps({"userTheme": "light"}), encoding="utf-8")
        self.support.set_enabled("cursor", False)
        self.auto_adopt.set_default_harnesses("agents", ("claude",))
        stored = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(stored["userTheme"], "light")


class AutoAdoptStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "settings.json"
        self.store = AutoAdoptStore(self.path)

    def test_defaults_when_nothing_is_stored(self) -> None:
        self.assertEqual(self.store.preferences(), {family: False for family in DEFAULTS})
        self.assertFalse(self.store.is_enabled("agents"))
        self.assertFalse(self.store.is_enabled("skills"))

    def test_round_trips_a_change(self) -> None:
        self.store.set_default_harnesses("agents", ("claude",))
        self.assertTrue(AutoAdoptStore(self.path).is_enabled("agents"))

    def test_enabling_skills_is_supported(self) -> None:
        self.store.set_default_harnesses("skills", ("claude",))
        self.assertTrue(self.store.is_enabled("skills"))

    def test_disabling_skills_succeeds(self) -> None:
        self.store.set_default_harnesses("skills", ())
        self.assertFalse(self.store.is_enabled("skills"))

    def test_agents_unaffected_both_ways(self) -> None:
        self.store.set_default_harnesses("agents", ("claude",))
        self.assertTrue(self.store.is_enabled("agents"))
        self.store.set_default_harnesses("agents", ())
        self.assertFalse(self.store.is_enabled("agents"))

    def test_an_unreadable_settings_file_falls_back_to_defaults(self) -> None:
        """The kill switch must never fail *open* because of a broken file — but it
        must not fail closed on a typo either. Declared defaults win."""
        self.path.write_text("{broken", encoding="utf-8")
        self.assertEqual(self.store.preferences(), {family: False for family in DEFAULTS})

    def test_junk_values_are_ignored_per_family(self) -> None:
        self.path.write_text(
            json.dumps({"autoAdopt": {"agents": "yes", "skills": True, "bogus": True}}),
            encoding="utf-8",
        )
        preferences = self.store.preferences()
        self.assertFalse(preferences["agents"])
        self.assertFalse(preferences["skills"])
        self.assertNotIn("bogus", preferences)

    def test_auto_adopt_harness_defaults_round_trip_without_wiping_other_settings(self) -> None:
        defaults = self.store.set_default_harnesses("agents", ("claude", "codex", "claude"))

        self.assertEqual(defaults["agents"], ("claude", "codex"))
        reloaded = AutoAdoptStore(self.path)
        self.assertEqual(reloaded.default_harnesses()["agents"], ("claude", "codex"))
        self.assertTrue(reloaded.is_enabled("agents"))

    def test_auto_adopt_harness_defaults_ignore_malformed_entries(self) -> None:
        self.path.write_text(
            json.dumps({"autoAdoptHarnesses": {"agents": ["claude", 3, "claude"], "bogus": ["cursor"]}}),
            encoding="utf-8",
        )

        self.assertEqual(self.store.default_harnesses()["agents"], ("claude",))
        self.assertNotIn("bogus", self.store.default_harnesses())


class SettingsMutationServiceAutoAdoptTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "settings.json"
        self.auto_adopt_store = AutoAdoptStore(self.path)
        self.support_store = HarnessSupportStore(self.path)
        self.kernel = MagicMock()
        self.kernel.harness_statuses.return_value = (
            SimpleNamespace(harness="claude", installed=True),
            SimpleNamespace(harness="codex", installed=True),
        )
        self.kernel.enabled_harness_ids_for_family.return_value = ("claude", "codex")
        self.service = SettingsMutationService(
            harness_kernel=self.kernel,
            support_store=self.support_store,
            invalidation=MagicMock(),
            auto_adopt_store=self.auto_adopt_store,
        )

    def test_enabling_skills_succeeds(self) -> None:
        result = self.service.set_auto_adopt("skills", True)
        self.assertTrue(result["ok"])
        self.assertTrue(result["autoAdopt"]["skills"])

    def test_disabling_skills_succeeds(self) -> None:
        result = self.service.set_auto_adopt("skills", False)
        self.assertTrue(result["ok"])
        self.assertFalse(result["autoAdopt"]["skills"])

    def test_agents_unaffected_both_ways(self) -> None:
        res_off = self.service.set_auto_adopt("agents", False)
        self.assertTrue(res_off["ok"])
        self.assertFalse(res_off["autoAdopt"]["agents"])

        res_on = self.service.set_auto_adopt("agents", True)
        self.assertTrue(res_on["ok"])
        self.assertTrue(res_on["autoAdopt"]["agents"])

    def test_enabling_any_known_family_selects_eligible_harnesses(self) -> None:
        result = self.service.set_auto_adopt("slash_commands", True)
        self.assertTrue(result["autoAdopt"]["slash_commands"])


if __name__ == "__main__":
    unittest.main()
