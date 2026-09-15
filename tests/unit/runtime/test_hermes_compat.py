import importlib.abc
import importlib.util
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
        sp = hermes_compat._find_hermes_site_packages(self.hermes_home)
        self.assertIsNotNone(sp)
        self.assertEqual(sp.resolve(), self.site_packages.resolve())

    def test_hermes_compat_absent_venv(self):
        # Remove venv
        shutil.rmtree(self.venv)
        self.assertIsNone(hermes_compat._find_hermes_site_packages(self.hermes_home))
        self.assertEqual(hermes_compat.status(self.hermes_home), "not-detected")
        self.assertFalse(hermes_compat.apply_hermes_compat(self.hermes_home))
        self.assertTrue(hermes_compat.remove_hermes_compat(self.hermes_home))

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

class DummyLoader(importlib.abc.Loader):
    def __init__(self, setup_func):
        self.setup_func = setup_func

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        if "." not in module.__name__:
            module.__path__ = []
        if self.setup_func:
            self.setup_func(module)


class DummyFinder(importlib.abc.MetaPathFinder):
    def __init__(self, modules_setup):
        self.modules_setup = modules_setup

    def find_spec(self, fullname, path, target=None):
        if fullname in self.modules_setup:
            spec = importlib.util.spec_from_loader(fullname, DummyLoader(self.modules_setup[fullname]))
            if "." not in fullname:
                spec.submodule_search_locations = []
            return spec
        return None


class TestHermesShimBehavior(unittest.TestCase):
    def setUp(self):
        self.modules_setup = {
            "agent": None,
            "tools": None,
            "agent.skill_utils": None,
        }
        self.dummy_finder = DummyFinder(self.modules_setup)
        sys.meta_path.insert(0, self.dummy_finder)

        # Load the shim
        spec = importlib.util.spec_from_file_location("shim", "harness_asset_manager/data/hermes/harnessam_hermes_compat.py")
        self.shim = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.shim)

        self.temp_dir = Path(tempfile.mkdtemp())
        self.fake_skills_dir = self.temp_dir / "skills"
        self.fake_skills_dir.mkdir()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)
        sys.meta_path.remove(self.dummy_finder)
        sys.meta_path[:] = [h for h in sys.meta_path if type(h).__name__ != "_PatchingFinder"]
        for k in list(sys.modules.keys()):
            if k in self.modules_setup:
                del sys.modules[k]

    def test_meta_path_idempotent(self):
        hooks = [h for h in sys.meta_path if type(h).__name__ == "_PatchingFinder"]
        self.assertEqual(len(hooks), 1)
        self.shim.install_hook()
        hooks2 = [h for h in sys.meta_path if type(h).__name__ == "_PatchingFinder"]
        self.assertEqual(len(hooks2), 1)

    def test_eviction_and_reimport(self):
        def setup_agent_skill_utils(m):
            m.is_external_skill_path = lambda path: False
            m.iter_skill_index_files = lambda base, name: []
        self.modules_setup["agent.skill_utils"] = setup_agent_skill_utils

        def setup(m):
            m._iter_skill_mds = "original"
            m._read_skill_name = lambda p, fallback: fallback
        self.modules_setup["tools.skill_usage"] = setup

        import tools.skill_usage
        self.assertNotEqual(tools.skill_usage._iter_skill_mds, "original")

        del sys.modules["tools.skill_usage"]
        import tools.skill_usage as tools2
        self.assertNotEqual(tools2._iter_skill_mds, "original")

    def test_patch_skill_usage(self):
        def setup_agent_skill_utils(m):
            m.is_external_skill_path = lambda path: "external" in str(path)
            def iter_skill_index_files(base, name):
                yield base / "skill1" / "SKILL.md"
                yield base / "external_skill" / "SKILL.md"
            m.iter_skill_index_files = iter_skill_index_files
        self.modules_setup["agent.skill_utils"] = setup_agent_skill_utils

        def setup(m):
            m._iter_skill_mds = "original"
            m._read_skill_name = lambda p, fallback: fallback
        self.modules_setup["tools.skill_usage"] = setup

        import tools.skill_usage
        self.assertNotEqual(tools.skill_usage._iter_skill_mds, "original")

        res = list(tools.skill_usage._iter_skill_mds(self.fake_skills_dir, local_only=True))
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0][0], "skill1")

    def test_patch_skill_manager_tool(self):
        def setup_agent_skill_utils(m):
            def iter_skill_index_files(base, name):
                yield base / "skill1" / "SKILL.md"
                yield base / "harnessam" / "skill2" / "SKILL.md"
            m.iter_skill_index_files = iter_skill_index_files
            m.get_all_skills_dirs = lambda: [self.fake_skills_dir]
        self.modules_setup["agent.skill_utils"] = setup_agent_skill_utils

        def setup(m):
            m._iter_skill_dirs = "original"
            m._find_skill = "original"
            m._skills_dir = lambda: self.fake_skills_dir
        self.modules_setup["tools.skill_manager_tool"] = setup

        import tools.skill_manager_tool

        res = tools.skill_manager_tool._find_skill("skill1")
        self.assertEqual(res["path"], self.fake_skills_dir / "skill1")

        res_cat = tools.skill_manager_tool._find_skill("harnessam/skill2")
        self.assertEqual(res_cat["path"], self.fake_skills_dir / "harnessam" / "skill2")

    def test_patch_skills_tool_log_security_warnings(self):
        def setup(m):
            m._INJECTION_PATTERNS = ["evil"]
            m.logger = mock.Mock()
            m._log_security_warnings = "original"
            m._under_any = mock.Mock(return_value=False)
        self.modules_setup["tools.skills_tool"] = setup

        import tools.skills_tool

        active_skills_dir = self.fake_skills_dir
        all_dirs = [active_skills_dir]

        # Test 1: Lexically inside trusted root (symlinked package)
        skill_md = active_skills_dir / "harnessam" / "skill1" / "SKILL.md"
        tools.skills_tool._log_security_warnings("skill1", skill_md, "clean", all_dirs, active_skills_dir)
        tools.skills_tool.logger.warning.assert_not_called()

        # Test 2: Genuinely outside trusted root
        outside_md = Path("/tmp/harnessam/evil/SKILL.md")
        tools.skills_tool._log_security_warnings("evil", outside_md, "clean", all_dirs, active_skills_dir)
        tools.skills_tool.logger.warning.assert_called_once()
        warning_msg = tools.skills_tool.logger.warning.call_args[0][2]
        self.assertIn("outside the trusted skills directory", warning_msg)

        tools.skills_tool._under_any.assert_called_once()
        tools.skills_tool.logger.reset_mock()

        # Test 3: Injection arm is independent
        tools.skills_tool._log_security_warnings("evil", skill_md, "evil code", all_dirs, active_skills_dir)
        tools.skills_tool.logger.warning.assert_called_once()
        warning_msg = tools.skills_tool.logger.warning.call_args[0][2]
        self.assertIn("prompt injection", warning_msg)
        self.assertNotIn("outside the trusted skills directory", warning_msg)

    def test_fail_open_behavior(self):
        def setup(m):
            m._iter_skill_mds = "original"
        self.modules_setup["tools.skill_usage"] = setup
        del self.modules_setup["agent.skill_utils"]
        import tools.skill_usage
        self.assertEqual(tools.skill_usage._iter_skill_mds, "original")

if __name__ == '__main__':
    unittest.main()
