from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness_asset_manager.application.settings.auto_adopt import (
    DEFAULTS,
    AutoAdoptStore,
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
        self.auto_adopt.set_enabled("agents", False)
        self.support.set_enabled("cursor", False)

        self.assertFalse(self.auto_adopt.is_enabled("agents"))
        self.assertEqual(self.support.load().disabled_harnesses, ("cursor",))

    def test_toggling_auto_adopt_does_not_wipe_disabled_harnesses(self) -> None:
        self.support.set_enabled("cursor", False)
        self.auto_adopt.set_enabled("skills", True)

        self.assertEqual(self.support.load().disabled_harnesses, ("cursor",))
        self.assertTrue(self.auto_adopt.is_enabled("skills"))

    def test_unrelated_keys_survive_both_writers(self) -> None:
        self.path.write_text(json.dumps({"userTheme": "light"}), encoding="utf-8")
        self.support.set_enabled("cursor", False)
        self.auto_adopt.set_enabled("agents", False)
        stored = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(stored["userTheme"], "light")


class AutoAdoptStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "settings.json"
        self.store = AutoAdoptStore(self.path)

    def test_defaults_when_nothing_is_stored(self) -> None:
        """Agents on (every action it can take is provable); skills off (rmtree)."""
        self.assertEqual(self.store.preferences(), dict(DEFAULTS))
        self.assertTrue(self.store.is_enabled("agents"))
        self.assertFalse(self.store.is_enabled("skills"))

    def test_round_trips_a_change(self) -> None:
        self.store.set_enabled("agents", False)
        self.assertFalse(AutoAdoptStore(self.path).is_enabled("agents"))

    def test_an_unreadable_settings_file_falls_back_to_defaults(self) -> None:
        """The kill switch must never fail *open* because of a broken file — but it
        must not fail closed on a typo either. Declared defaults win."""
        self.path.write_text("{broken", encoding="utf-8")
        self.assertEqual(self.store.preferences(), dict(DEFAULTS))

    def test_junk_values_are_ignored_per_family(self) -> None:
        self.path.write_text(
            json.dumps({"autoAdopt": {"agents": "yes", "skills": True, "bogus": True}}),
            encoding="utf-8",
        )
        preferences = self.store.preferences()
        self.assertTrue(preferences["agents"])  # non-bool ignored, default stands
        self.assertTrue(preferences["skills"])
        self.assertNotIn("bogus", preferences)

    def test_an_unknown_family_is_refused(self) -> None:
        with self.assertRaises(KeyError):
            self.store.set_enabled("mcp", True)


if __name__ == "__main__":
    unittest.main()
