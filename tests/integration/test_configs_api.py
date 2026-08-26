
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
            
            # Refusal test for toml
            # Create codex config
            codex_dir = harness.spec.home / ".codex"
            codex_dir.mkdir(exist_ok=True)
            codex_cfg = codex_dir / "config.toml"
            codex_cfg.write_text('theme = "dark"')
            
            harness.post_json("/api/configs/capture?explicit=true")
            res = harness.post_json("/api/configs/codex/restore", expected_status=400)
            self.assertIn("Cannot restore", res["error"])
