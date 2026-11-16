import json
import tempfile
import unittest
from pathlib import Path

from harness_asset_manager.application.asset_archive import AssetArchiveStore


class AssetArchiveStoreTests(unittest.TestCase):
    def test_flags_persist_and_preserve_other_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "asset-archive.json"
            path.write_text(json.dumps({"version": 1, "future": {"value": 1}}))
            store = AssetArchiveStore(path)
            store.set_archived("skills", "shared:first", archived=True)
            store.set_archived("agents", "second", archived=True)
            store.set_archived("skills", "shared:first", archived=True)
            self.assertEqual(AssetArchiveStore(path).load(), {"skills:shared:first", "agents:second"})
            store.set_archived("skills", "shared:first", archived=False)
            store.set_archived("skills", "shared:first", archived=False)
            self.assertEqual(store.load(), {"agents:second"})
            self.assertEqual(json.loads(path.read_text())["future"], {"value": 1})

    def test_corrupt_store_reads_as_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "asset-archive.json"
            path.write_text("{")
            store = AssetArchiveStore(path)
            self.assertEqual(store.load(), set())
            store.set_archived("skills", "shared:first", archived=True)
            self.assertTrue(store.is_archived("skills", "shared:first"))
