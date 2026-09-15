import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from harness_asset_manager.runtime import hermes_compat


class TestHermesCompat(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.hermes_home = self.temp_dir / ".hermes"

        self.venv = self.hermes_home / "hermes-agent" / "venv"
        self.site_packages = self.venv / "lib" / "python3.11" / "site-packages"
        self.site_packages.mkdir(parents=True, exist_ok=True)

        self.env_patcher = mock.patch.dict("os.environ", {"HERMES_HOME": str(self.hermes_home)})
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()
        shutil.rmtree(self.temp_dir)

    def test_hermes_compat_detects_layout(self):
        sp = hermes_compat._find_hermes_site_packages()
        self.assertIsNotNone(sp)
        self.assertEqual(sp.resolve(), self.site_packages.resolve())

    def test_hermes_compat_absent_venv(self):
        # Remove venv
        shutil.rmtree(self.venv)
        self.assertIsNone(hermes_compat._find_hermes_site_packages())
        self.assertEqual(hermes_compat.status(self.hermes_home), "not-detected")
        self.assertFalse(hermes_compat.apply_hermes_compat(self.hermes_home))
        self.assertFalse(hermes_compat.remove_hermes_compat(self.hermes_home))

    @mock.patch("harness_asset_manager.runtime.hermes_compat._get_shim_content")
    def test_hermes_compat_install_and_remove(self, mock_shim):
        mock_shim.return_value = hermes_compat.STAMP_MARKER + "\nprint('shim')"

        self.assertEqual(hermes_compat.status(self.hermes_home), "absent")

        self.assertTrue(hermes_compat.apply_hermes_compat(self.hermes_home))
        self.assertEqual(hermes_compat.status(self.hermes_home), "current")

        self.assertTrue((self.site_packages / "harnessam_hermes_compat.pth").exists())
        self.assertTrue((self.site_packages / "harnessam_hermes_compat.py").exists())

        self.assertTrue(hermes_compat.apply_hermes_compat(self.hermes_home)) # idempotent

        self.assertTrue(hermes_compat.remove_hermes_compat(self.hermes_home))
        self.assertEqual(hermes_compat.status(self.hermes_home), "absent")
        self.assertFalse((self.site_packages / "harnessam_hermes_compat.pth").exists())

    @mock.patch("harness_asset_manager.runtime.hermes_compat._get_shim_content")
    def test_hermes_compat_rewrite_stale(self, mock_shim):
        mock_shim.return_value = hermes_compat.STAMP_MARKER + "\nnew"

        (self.site_packages / "harnessam_hermes_compat.py").write_text("# STAMP_VERSION: 0.0.1\nold")
        (self.site_packages / "harnessam_hermes_compat.pth").write_text("import harnessam_hermes_compat\n")

        self.assertEqual(hermes_compat.status(self.hermes_home), "stale")
        self.assertTrue(hermes_compat.apply_hermes_compat(self.hermes_home))
        self.assertEqual(hermes_compat.status(self.hermes_home), "current")

        content = (self.site_packages / "harnessam_hermes_compat.py").read_text()
        self.assertIn("new", content)

    def test_shim_behavior(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("shim", "harness_asset_manager/data/hermes/harnessam_hermes_compat.py")
        shim = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(shim)

        hooks = [h for h in sys.meta_path if type(h).__name__ == "_PatchingFinder"]
        self.assertEqual(len(hooks), 1)

        spec.loader.exec_module(shim)
        hooks2 = [h for h in sys.meta_path if type(h).__name__ == "_PatchingFinder"]
        self.assertEqual(len(hooks2), 1)

        sys.meta_path.remove(hooks[0])

if __name__ == '__main__':
    unittest.main()
