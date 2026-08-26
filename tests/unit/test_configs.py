import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness_asset_manager.application.configs.extraction import extract_preferences
from harness_asset_manager.application.configs.model import ConfigRecord
from harness_asset_manager.application.configs.service import ConfigsService
from harness_asset_manager.application.configs.store import ConfigStore


class DummyAssetTagService:
    def get_tags(self, family, harness):
        return []

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
            
            s = ConfigsService(store, kernel, DummyAssetTagService())
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
        
        s = ConfigsService(store, kernel, DummyAssetTagService())
        s._extract_local = lambda h: {"pref": 2}
        
        s.capture(explicit=False)
        store.write_config.assert_not_called()
    def test_disable_removes_record_leaves_file_byte_identical(self):
        from pathlib import Path
        from unittest.mock import MagicMock
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "cfg.json"
            content = '{\n  "unowned": 1,\n  "pref1": 2\n}\n'
            p.write_text(content)
            
            kernel = MagicMock()
            prof = MagicMock()
            prof.resolve_config_path.return_value = p
            prof.file_format = "json"
            
            store = MagicMock()
            s = ConfigsService(store, kernel, DummyAssetTagService())
            s._get_binding_profile = lambda h: prof
            
            s.disable("dummy")
            
            store.remove_config.assert_called_once_with("dummy")
            self.assertEqual(p.read_text(), content)

    def test_enable_on_never_captured_captures_it(self):
        from unittest.mock import MagicMock
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "cfg.json"
            p.write_text('{"pref1": 2}')
            
            kernel = MagicMock()
            prof = MagicMock()
            prof.resolve_config_path.return_value = p
            prof.file_format = "json"
            
            store = MagicMock()
            
            s = ConfigsService(store, kernel, DummyAssetTagService())
            s._get_binding_profile = lambda h: prof
            s._extract_local = lambda h: {"pref1": 2}
            
            s.enable("dummy")
            
            store.write_config.assert_called_once()
            args = store.write_config.call_args[0]
            self.assertEqual(args[0], "dummy")
            self.assertEqual(args[1].preferences, {"pref1": 2})

    def test_capture_skips_unmanaged_harnesses(self):
        from unittest.mock import MagicMock
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "cfg.json"
            p.write_text('{"pref1": 2}')
            
            store = MagicMock()
            man = MagicMock()
            man.configs = {} # No configs managed yet!
            store.load.return_value = man
            
            kernel = MagicMock()
            b = MagicMock()
            b.definition.harness = "dummy"
            b.profile.resolve_config_path.return_value = p
            kernel.bindings_for_family.return_value = [b]
            
            s = ConfigsService(store, kernel, DummyAssetTagService())
            s.capture(explicit=True)
            store.write_config.assert_not_called()

    def test_managed_set_survives_manifest_round_trip(self):
        with TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            manifest_path.write_text('{"configs": {"claude": {"sourceFile": "a", "preferences": {"a": 1}, "capturedAt": "2024-01-01T00:00:00Z", "revision": "123"}}}')
            
            store = ConfigStore(manifest_path)
            
            manifest1 = store.load()
            store.write_config("claude", manifest1.configs["claude"])
            
            manifest2 = store.load()
            self.assertIn("claude", manifest2.configs)
            self.assertEqual(manifest2.configs["claude"].preferences, {"a": 1})

    def test_capture_leaves_record_alone_if_config_absent(self):
        from unittest.mock import MagicMock
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "absent.json"
            
            store = MagicMock()
            man = MagicMock()
            man.configs = {"dummy": ConfigRecord("a", {"pref1": 2}, "b", "c")} 
            store.load.return_value = man
            
            kernel = MagicMock()
            b = MagicMock()
            b.definition.harness = "dummy"
            b.profile.resolve_config_path.return_value = p
            kernel.bindings_for_family.return_value = [b]
            
            s = ConfigsService(store, kernel, DummyAssetTagService())
            s.capture(explicit=False)
            
            # The risk of silently deleting another machine's managed state means we leave it alone.
            store.remove_config.assert_not_called()
            store.write_config.assert_not_called()

    def test_list_exposes_has_record_for_absent_configs(self):
        from unittest.mock import MagicMock
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "absent.json"
            
            store = MagicMock()
            man = MagicMock()
            man.configs = {"dummy": ConfigRecord("a", {"pref1": 2}, "b", "c")} 
            store.load.return_value = man
            
            kernel = MagicMock()
            b = MagicMock()
            b.definition.harness = "dummy"
            b.profile.resolve_config_path.return_value = p
            kernel.bindings_for_family.return_value = [b]
            
            s = ConfigsService(store, kernel, DummyAssetTagService())
            res = s.list()
            
            self.assertEqual(res["dummy"]["managed"], False)
            self.assertEqual(res["dummy"]["hasRecord"], True)
