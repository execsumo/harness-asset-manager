
import json
import unittest

from tests.support.app_harness import AppTestHarness
from tests.support.fake_home import FakeHomeSpec


def seed_claude_config(spec: FakeHomeSpec) -> None:
    claude_dir = spec.home / ".claude"
    claude_dir.mkdir(parents=True, exist_ok=True)
    cfg = claude_dir / "settings.json"
    cfg.write_text(json.dumps({"theme": "dark", "model": "claude-3-5-sonnet-20241022", "mcpServers": {"test": {}}}))

class ConfigsApiTests(unittest.TestCase):
    def test_configs_round_trip(self) -> None:
        with AppTestHarness(fixture_factory=seed_claude_config) as harness:
            # Starts unmanaged
            diff_res = harness.get_json("/api/configs/claude/diff")
            self.assertEqual(diff_res["state"], "unmanaged")
            
            # Capture
            harness.post_json("/api/configs/capture?explicit=true")
            
            # Now list
            data = harness.get_json("/api/configs/")
            self.assertIn("claude", data)
            
            # Diff should now be managed
            diff_res = harness.get_json("/api/configs/claude/diff")
            self.assertEqual(diff_res["state"], "managed")
            
            # Mutate local file
            cfg = harness.spec.home / ".claude" / "settings.json"
            cfg.write_text(json.dumps({"theme": "light", "mcpServers": {"test": {}}}))
            
            # Diff should be drifted
            diff_res = harness.get_json("/api/configs/claude/diff")
            self.assertEqual(diff_res["state"], "drifted")
            
            # Restore
            harness.post_json("/api/configs/claude/restore")
            
            # Check restored content
            restored = json.loads(cfg.read_text())
            self.assertEqual(restored["theme"], "dark")
            
            # Test byte-identical capture-restore
            cfg_content = '{\n  "theme": "dark",\n  "nested": {\n    "z_key": 1,\n    "a_key": 2\n  }\n}\n'
            cfg.write_text(cfg_content)
            
            harness.post_json("/api/configs/capture?explicit=true")
            harness.post_json("/api/configs/claude/restore")
            
            restored_content = cfg.read_text()
            self.assertEqual(restored_content, cfg_content, "Capture-restore should preserve original key ordering exactly")
            
            # TOML restores through the same document layer, so a comment on an
            # unowned key has to survive a write aimed at a managed one.
            codex_dir = harness.spec.home / ".codex"
            codex_dir.mkdir(exist_ok=True)
            codex_cfg = codex_dir / "config.toml"
            codex_content = (
                '# kept verbatim\n'
                'model = "gpt-5"\n'
                '\n'
                '[projects."/machine/local/path"]\n'
                'trust_level = "trusted"  # unowned, must not be reformatted\n'
            )
            codex_cfg.write_text(codex_content)

            harness.post_json("/api/configs/capture?explicit=true")
            harness.post_json("/api/configs/codex/restore")
            self.assertEqual(codex_cfg.read_text(), codex_content)

    def test_unknown_harness_is_reported_not_answered_ok(self) -> None:
        """A typo must not read as a successful restore of nothing."""
        with AppTestHarness(fixture_factory=seed_claude_config) as harness:
            res = harness.post_json(
                "/api/configs/nosuchharness/restore", expected_status=404
            )
            self.assertEqual(res["code"], "unknown_harness")

            res = harness.get_json("/api/configs/nosuchharness/diff", expected_status=404)
            self.assertEqual(res["code"], "unknown_harness")

    def test_known_but_uncaptured_harness_restore_is_reported(self) -> None:
        """Distinct from an unknown name: the harness exists, the capture does not."""
        with AppTestHarness(fixture_factory=seed_claude_config) as harness:
            res = harness.post_json("/api/configs/claude/restore", expected_status=404)
            self.assertEqual(res["code"], "not_captured")

            # ...while its diff is a legitimate "unmanaged", not an error.
            self.assertEqual(
                harness.get_json("/api/configs/claude/diff")["state"], "unmanaged"
            )
