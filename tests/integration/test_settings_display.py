from __future__ import annotations

import json
import unittest

from tests.support.app_harness import AppTestHarness


class SettingsDisplayPreferenceTests(unittest.TestCase):
    def test_agent_tags_default_on_and_round_trip(self) -> None:
        with AppTestHarness() as harness:
            self.assertEqual(harness.get_json("/api/settings")["display"], {"showSkillAgentTags": True})

            result = harness.put_json("/api/settings/display/showSkillAgentTags", {"value": False})
            self.assertEqual(result, {"ok": True, "display": {"showSkillAgentTags": False}})
            self.assertFalse(harness.get_json("/api/settings")["display"]["showSkillAgentTags"])

            harness.put_json("/api/settings/display/showSkillAgentTags", {"value": True})
            self.assertTrue(harness.get_json("/api/settings")["display"]["showSkillAgentTags"])

    def test_preserves_other_settings_keys(self) -> None:
        with AppTestHarness() as harness:
            settings_path = harness.container.paths.settings_path
            harness.put_json("/api/settings/auto-adopt/skills/harnesses", {"harnesses": []})
            before = json.loads(settings_path.read_text(encoding="utf-8"))
            harness.put_json("/api/settings/display/showSkillAgentTags", {"value": False})
            after = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertEqual(after["display"], {"showSkillAgentTags": False})
            for key, value in before.items():
                self.assertEqual(after[key], value)

    def test_malformed_value_falls_back_to_default(self) -> None:
        with AppTestHarness() as harness:
            settings_path = harness.container.paths.settings_path
            document = json.loads(settings_path.read_text(encoding="utf-8")) if settings_path.is_file() else {}
            document["display"] = {"showSkillAgentTags": "nope"}
            settings_path.write_text(json.dumps(document), encoding="utf-8")
            self.assertTrue(harness.get_json("/api/settings")["display"]["showSkillAgentTags"])

    def test_unknown_preference_is_rejected(self) -> None:
        with AppTestHarness() as harness:
            harness.put_json("/api/settings/display/nope", {"value": True}, expected_status=404)
            harness.put_json("/api/settings/display/showSkillAgentTags", {"value": "maybe"}, expected_status=422)
