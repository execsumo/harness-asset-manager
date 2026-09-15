from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness_asset_manager.application.container import build_backend_container
from tests.support.fake_home import FakeHomeSpec, seed_skill_package, write_cli_stub


class TestHermesBindingContracts(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)
        self.spec = FakeHomeSpec(
            root=self.tmp_path,
            home=self.tmp_path / "Users" / "alice",
            xdg_config_home=self.tmp_path / "Users" / "alice" / ".config",
            xdg_data_home=self.tmp_path / "Users" / "alice" / ".local" / "share",
            xdg_state_home=self.tmp_path / "Users" / "alice" / ".local" / "state",
        )
        for p in (
            self.spec.skills_store_root,
            self.spec.agents_root,
            self.spec.claude_root,
            self.spec.xdg_state_home,
            self.spec.bin_dir,
            self.spec.hermes_skills_root,
            self.spec.hermes_home / "profiles" / "work" / "skills",
        ):
            p.mkdir(parents=True, exist_ok=True)
            
        write_cli_stub(self.spec.bin_dir / "hermes", "hermes")
        self.container = build_backend_container(self.spec.env())

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_enable_disable_contract(self):
        # 1. Seed a skill
        skill_src = self.spec.home / "downloads" / "my-skill"
        seed_skill_package(skill_src.parent, "my-skill", "My Skill")
        dest = self.container.skills_store.ingest(
            source_path=skill_src,
            declared_name="my-skill",
            source_kind="github",
            source_locator="github:org/my-skill"
        )
        
        # 2. Seed a native Hermes skill to ensure it remains untouched
        native_skill = self.spec.hermes_skills_root / "native-skill"
        native_skill.mkdir()
        (native_skill / "SKILL.md").write_text("native")

        # 3. Enable for hermes (creates a DIRECTORY symlink containing WHOLE package)
        self.container.skills_mutations.enable_managed_package(dest, "hermes")
        
        canonical_symlink = self.spec.hermes_skills_root / "harnessam" / dest.name
        self.assertTrue(canonical_symlink.is_symlink())
        self.assertEqual(canonical_symlink.resolve(), dest)
        self.assertTrue((canonical_symlink / "SKILL.md").exists())
        
        # Enable is idempotent
        self.container.skills_mutations.enable_managed_package(dest, "hermes")
        self.assertTrue(canonical_symlink.is_symlink())
        
        # 4. Disable removes ONLY the binding
        self.container.skills_mutations.disable_skill(f"shared:{dest.name}", "hermes")
        self.assertFalse(canonical_symlink.exists())
        self.assertFalse(canonical_symlink.is_symlink())
        
        # Canonical package remains untouched
        self.assertTrue(dest.exists())
        # Native skill remains untouched
        self.assertTrue(native_skill.exists())
        
        # Disable is idempotent
        self.container.skills_mutations.disable_skill(f"shared:{dest.name}", "hermes")
        
    def test_scoped_profile_binding(self):
        # 1. Seed a skill
        skill_src = self.spec.home / "downloads" / "my-skill"
        seed_skill_package(skill_src.parent, "my-skill", "My Skill")
        dest = self.container.skills_store.ingest(
            source_path=skill_src,
            declared_name="my-skill",
            source_kind="github",
            source_locator="github:org/my-skill"
        )
        
        # 2. Enable for hermes:work
        self.container.skills_mutations.enable_managed_package(dest, "hermes:work")
        
        # 3. Assert it links only in that profile
        profile_symlink = self.spec.hermes_home / "profiles" / "work" / "skills" / "harnessam" / dest.name
        self.assertTrue(profile_symlink.is_symlink())
        self.assertEqual(profile_symlink.resolve(), dest)
        
        # Not linked in main profile
        main_symlink = self.spec.hermes_skills_root / "harnessam" / dest.name
        self.assertFalse(main_symlink.exists())
        
        self.container.skills_mutations.disable_skill(f"shared:{dest.name}", "hermes:work")
        self.assertFalse(profile_symlink.exists())

if __name__ == '__main__':
    unittest.main()
