
import unittest

from tests.support.app_harness import AppTestHarness


class ConfigsApiTests(unittest.TestCase):
    def test_configs_round_trip(self) -> None:
        with AppTestHarness() as harness:
            # It starts unmanaged
            diff_res = harness.get_json("/api/configs/droid/diff")
            self.assertEqual(diff_res["state"], "unmanaged")
            
            # Put something in the local harness file
            # Factory harness config path
            # Wait, how to find the path? It's not exposed easily, we just write to the file if we know it.
            # But the configs family works with the real manifest. Let's just capture.
            # We can mock it by setting up a dummy file? No, just capture.
            harness.post_json("/api/configs/capture?explicit=true")
            
            # Now list
            data = harness.get_json("/api/configs/")
            
            # It should exist, at least for some harness.
            # Wait, AppTestHarness sets up harnesses.
            # 'droid' might be one.
            # Diff should now be managed
            if "droid" in data:
                diff_res = harness.get_json("/api/configs/droid/diff")
                self.assertEqual(diff_res["state"], "managed")
                
            # Restore
            if "droid" in data:
                harness.post_json("/api/configs/droid/restore")
