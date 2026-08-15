from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlopen

from harness_asset_manager.paths import APP_NAME
from tests.support.app_harness import AppTestHarness
from tests.support.fake_home import (
    seed_divergent_source_fixture,
    seed_managed_linked_fixture,
)


class HttpApiTests(unittest.TestCase):
    def test_empty_fixture_returns_skills_settings_and_health(self) -> None:
        with AppTestHarness() as harness:
            health = harness.get_json("/api/health")
            skills = harness.get_json("/api/skills")
            settings = harness.get_json("/api/settings")

            self.assertTrue(health["ok"])
            self.assertEqual(skills["summary"], {"managed": 0, "unmanaged": 0})
            self.assertEqual(skills["rows"], [])
            self.assertEqual(settings["storage"]["skillsStorePath"], str(harness.spec.skills_store_root))
            self.assertEqual(
                settings["storage"]["marketplaceCachePath"],
                str(harness.spec.xdg_data_home / APP_NAME / "marketplace"),
            )
            self.assertEqual(
                settings["storage"]["settingsPath"],
                str(harness.spec.xdg_config_home / APP_NAME / "settings.json"),
            )
            self.assertEqual(len(settings["harnesses"]), 7)
            opencode = next(item for item in settings["harnesses"] if item["harness"] == "opencode")
            self.assertTrue(opencode["installed"])
            self.assertTrue(opencode["supportEnabled"])
            self.assertEqual(opencode["managedLocation"], str(harness.spec.opencode_root.parent))
            self.assertNotIn("discoveryMode", opencode)
            self.assertNotIn("centralStore", settings)
            self.assertNotIn("topology", settings)

    def test_health_skills_and_settings_work_without_opencode_state(self) -> None:
        with AppTestHarness(omit_clis=("opencode",)) as harness:
            health = harness.get_json("/api/health")
            skills = harness.get_json("/api/skills")
            settings = harness.get_json("/api/settings")

            self.assertTrue(health["ok"])
            self.assertEqual(skills["summary"], {"managed": 0, "unmanaged": 0})
            self.assertEqual(skills["rows"], [])
            opencode = next(item for item in settings["harnesses"] if item["harness"] == "opencode")
            self.assertFalse(opencode["installed"])
            self.assertFalse(opencode["supportEnabled"])
            self.assertEqual(opencode["managedLocation"], str(harness.spec.opencode_root.parent))

    def test_undetected_harness_cannot_be_enabled(self) -> None:
        with AppTestHarness(omit_clis=("opencode",)) as harness:
            harness.put_json(
                "/api/settings/harnesses/opencode/support",
                {"enabled": True},
                expected_status=400,
            )
            opencode = next(item for item in harness.get_json("/api/settings")["harnesses"] if item["harness"] == "opencode")
            self.assertFalse(opencode["supportEnabled"])

    def test_settings_support_toggle_hides_disabled_harness_from_skills_inventory(self) -> None:
        with AppTestHarness(mixed=True) as harness:
            settings = harness.get_json("/api/settings")
            codex = next(item for item in settings["harnesses"] if item["harness"] == "codex")

            self.assertTrue(codex["supportEnabled"])

            harness.put_json("/api/settings/harnesses/codex/support", {"enabled": False})

            updated_settings = harness.get_json("/api/settings")
            updated_codex = next(item for item in updated_settings["harnesses"] if item["harness"] == "codex")
            skills = harness.get_json("/api/skills")

            self.assertFalse(updated_codex["supportEnabled"])
            self.assertNotIn("codex", [column["harness"] for column in skills["harnessColumns"]])

    def test_mixed_fixture_returns_skills_page_and_detail(self) -> None:
        with AppTestHarness(mixed=True) as harness:
            skills = harness.get_json("/api/skills")

            shared_audit = next(row for row in skills["rows"] if row["name"] == "Shared Audit")
            trace_lens = next(row for row in skills["rows"] if row["name"] == "Trace Lens")
            detail = harness.get_json(f"/api/skills/{shared_audit['skillRef']}")
            source_status = harness.get_json(f"/api/skills/{shared_audit['skillRef']}/source-status")

            self.assertEqual(skills["summary"], {"managed": 1, "unmanaged": 2})
            self.assertEqual(shared_audit["displayStatus"], "Managed")
            self.assertEqual(shared_audit["actions"], {"canManage": False, "canStopManaging": False, "canDelete": True})
            self.assertEqual(trace_lens["displayStatus"], "Unmanaged")
            self.assertEqual(trace_lens["actions"], {"canManage": True, "canStopManaging": False, "canDelete": False})
            self.assertEqual(detail["displayStatus"], "Managed")
            self.assertEqual(
                [cell["label"] for cell in detail["harnessCells"]],
                ["Claude", "Codex", "Antigravity", "Cursor", "OpenCode", "Factory Droid", "Hermes Agent"],
            )
            self.assertNotIn("updateStatus", detail["actions"])
            self.assertEqual(source_status["updateStatus"], "no_update_available")
            self.assertEqual(detail["actions"]["stopManagingStatus"], "disabled_no_enabled")
            self.assertEqual(detail["actions"]["stopManagingHarnessLabels"], [])
            self.assertTrue(detail["actions"]["canDelete"])
            self.assertEqual(detail["actions"]["deleteHarnessLabels"], [])
            self.assertIn("Shared package fixture.", detail["documentMarkdown"])
            self.assertNotIn("statusMessage", detail)
            self.assertNotIn("source", detail)
            self.assertNotIn("advanced", detail)
            self.assertEqual(detail["sourceLinks"], {
                "repoLabel": "mode-io/shared-audit",
                "repoUrl": "https://github.com/mode-io/shared-audit",
                "folderUrl": None,
            })

    def test_managed_detail_returns_shared_store_location_before_tool_links(self) -> None:
        with AppTestHarness(fixture_factory=seed_managed_linked_fixture) as harness:
            skills = harness.get_json("/api/skills")
            shared_audit = next(row for row in skills["rows"] if row["name"] == "Shared Audit")
            detail = harness.get_json(f"/api/skills/{shared_audit['skillRef']}")

            self.assertEqual([location["label"] for location in detail["locations"]], ["Shared Store", "Antigravity", "Codex", "OpenCode"])
            self.assertEqual(detail["actions"]["stopManagingStatus"], "available")
            self.assertEqual(detail["actions"]["stopManagingHarnessLabels"], ["Codex"])
            self.assertEqual(detail["actions"]["deleteHarnessLabels"], ["Codex"])

    def test_divergent_source_fixture_returns_separate_found_rows(self) -> None:
        with AppTestHarness(fixture_factory=seed_divergent_source_fixture) as harness:
            skills = harness.get_json("/api/skills")
            policy_rows = [row for row in skills["rows"] if row["name"] == "Policy Kit"]

            self.assertEqual(len(policy_rows), 2)
            self.assertTrue(all(row["displayStatus"] == "Unmanaged" for row in policy_rows))

    def test_unknown_skill_detail_returns_404_payload(self) -> None:
        with AppTestHarness() as harness:
            payload = harness.get_json("/api/skills/missing-entry", expected_status=404)
            self.assertEqual(payload["code"], "skill_not_found")
            self.assertIn("unknown skill ref", payload["error"])

    def test_validation_error_payload_has_stable_code(self) -> None:
        with AppTestHarness() as harness:
            payload = harness.put_json(
                "/api/settings/auto-adopt/agents",
                {},
                expected_status=422,
            )
            self.assertEqual(payload["code"], "validation_error")
            self.assertIn("enabled", payload["error"])

    def test_unknown_api_path_has_not_found_code(self) -> None:
        with AppTestHarness() as harness:
            payload = harness.get_json("/api/no-such-resource", expected_status=404)
            self.assertEqual(payload["code"], "not_found")

    def test_frontend_routes_return_spa_shell_when_dist_is_present(self) -> None:
        with TemporaryDirectory(prefix="harnessam-dist-") as tempdir:
            dist = Path(tempdir)
            (dist / "index.html").write_text("<!doctype html><html><body><div id='root'>harness-asset-manager</div></body></html>", encoding="utf-8")

            with AppTestHarness(frontend_dist=dist) as harness:
                for path in ("/", "/skills", "/skills/managed", "/skills/unmanaged", "/marketplace", "/settings"):
                    with urlopen(f"{harness.base_url}{path}") as response:
                        body = response.read().decode("utf-8")
                    self.assertEqual(response.status, 200)
                    self.assertIn("<div id='root'>harness-asset-manager</div>", body)


    def test_auto_adopt_enable_skills_succeeds(self) -> None:
        with AppTestHarness() as harness:
            res = harness.put_json("/api/settings/auto-adopt/skills", {"enabled": True})
            self.assertTrue(res["autoAdopt"]["skills"])

    def test_auto_adopt_disable_skills_returns_200(self) -> None:
        with AppTestHarness() as harness:
            res = harness.put_json("/api/settings/auto-adopt/skills", {"enabled": False}, expected_status=200)
            self.assertTrue(res["ok"])
            self.assertFalse(res["autoAdopt"]["skills"])

    def test_auto_adopt_agents_toggles_successfully(self) -> None:
        with AppTestHarness() as harness:
            res_off = harness.put_json("/api/settings/auto-adopt/agents", {"enabled": False}, expected_status=200)
            self.assertTrue(res_off["ok"])
            self.assertFalse(res_off["autoAdopt"]["agents"])

            res_on = harness.put_json("/api/settings/auto-adopt/agents", {"enabled": True}, expected_status=200)
            self.assertTrue(res_on["ok"])
            self.assertTrue(res_on["autoAdopt"]["agents"])

    def test_auto_adopt_unknown_family_returns_404(self) -> None:
        with AppTestHarness() as harness:
            res = harness.put_json("/api/settings/auto-adopt/slash_commands", {"enabled": True})
            self.assertTrue(res["autoAdopt"]["slash_commands"])

    def test_get_settings_retains_both_auto_adopt_keys(self) -> None:
        with AppTestHarness() as harness:
            settings = harness.get_json("/api/settings")
            self.assertIn("slash_commands", settings["autoAdopt"])

    def test_auto_adopt_defaults_validate_and_round_trip(self) -> None:
        with AppTestHarness() as harness:
            result = harness.put_json(
                "/api/settings/auto-adopt/agents/harnesses",
                {"harnesses": ["claude", "codex"]},
            )
            self.assertEqual(result["autoAdoptHarnesses"]["agents"], ["claude", "codex"])
            settings = harness.get_json("/api/settings")
            self.assertEqual(settings["autoAdoptHarnesses"]["agents"], ["claude", "codex"])
            self.assertTrue(settings["autoAdopt"]["agents"])

            harness.put_json(
                "/api/settings/auto-adopt/agents/harnesses",
                {"harnesses": []},
            )
            settings = harness.get_json("/api/settings")
            self.assertFalse(settings["autoAdopt"]["agents"])

            harness.put_json(
                "/api/settings/auto-adopt/agents/harnesses",
                {"harnesses": ["not-a-harness"]},
                expected_status=404,
            )

    def test_auto_adopt_options_include_every_agent_binding_in_catalog_order(self) -> None:
        with AppTestHarness() as harness:
            settings = harness.get_json("/api/settings")

            self.assertEqual(
                settings["autoAdoptHarnessOptions"]["agents"],
                ["claude", "codex", "agy", "cursor", "opencode", "droid", "hermes"],
            )


if __name__ == "__main__":
    unittest.main()
