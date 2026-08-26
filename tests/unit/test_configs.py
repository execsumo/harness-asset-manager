import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness_asset_manager.application.configs.extraction import extract_preferences
from harness_asset_manager.application.configs.model import ConfigRecord
from harness_asset_manager.application.configs.service import ConfigsService
from harness_asset_manager.application.configs.store import ConfigStore


class ConfigsTests(unittest.TestCase):
    def test_extraction_filters(self):
        doc = {
            "mcpServers": {"something": 1},  # family-owned
            "legitimate": "survives",
            "providers": {
                "anthropic": {
                    "api_key": "sk-1234"  # nested secret
                }
            },
            "projects": {
                "/home/dev/some/project": True  # absolute path in key
            },
            "nested_path": {
                "workspace": "/home/dev/some/project"  # nested absolute path
            },
            "trustedWorkspaces": [
                "/Users/hgill/projects/foo"  # foreign-home path
            ]
        }
        
        home_dir = "/home/dev"
        family_keys = {"mcpServers"}
        
        prefs = extract_preferences(doc, family_keys, home_dir)
        
        self.assertNotIn("mcpServers", prefs)
        self.assertEqual(prefs["legitimate"], "survives")
        self.assertNotIn("providers", prefs)
        self.assertNotIn("projects", prefs)
        self.assertNotIn("nested_path", prefs)
        self.assertNotIn("trustedWorkspaces", prefs)

    def test_manifest_unknown_key_preservation(self):
        with TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            manifest_path.write_text('{"unknown_top_level": "value"}')
            store = ConfigStore(manifest_path)
            
            manifest = store.load()
            store.write_config("dummy", ConfigRecord("file", {}, "2024-01-01T00:00:00Z", "rev"))
            
            content = manifest_path.read_text()
            self.assertIn('"unknown_top_level": "value"', content)


    def test_restore_preserving_unowned_keys(self):
        import json
        from pathlib import Path
        from unittest.mock import MagicMock
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "cfg.json"
            p.write_text('{"unowned": 1, "pref1": 2}')
            
            kernel = MagicMock()
            prof = MagicMock()
            prof.resolve_config_path.return_value = p
            prof.file_format = "json"
            b = MagicMock()
            b.profile = prof
            kernel.bindings_for_family.return_value = [b]
            
            store = MagicMock()
            man = MagicMock()
            man.configs = {"dummy": ConfigRecord("f", {"pref1": 3, "newpref": 4}, "t", "rev")}
            store.load.return_value = man
            
            s = ConfigsService(store, kernel)
            s._get_binding_profile = lambda h: prof
            s.restore("dummy")
            
            res = json.loads(p.read_text())
            self.assertEqual(res["unowned"], 1)
            self.assertEqual(res["pref1"], 3)
            self.assertEqual(res["newpref"], 4)

    def test_two_sided_change_case(self):
        from unittest.mock import MagicMock
        
        store = MagicMock()
        man = MagicMock()
        man.configs = {"dummy": ConfigRecord("f", {"pref": 1}, "t", "old_rev")}
        store.load.return_value = man
        
        kernel = MagicMock()
        b = MagicMock()
        b.definition.harness = "dummy"
        kernel.bindings_for_family.return_value = [b]
        
        s = ConfigsService(store, kernel)
        s._extract_local = lambda h: {"pref": 2}
        
        s.capture(explicit=False)
        store.write_config.assert_not_called()