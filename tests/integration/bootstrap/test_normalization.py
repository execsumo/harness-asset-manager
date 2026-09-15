from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness_asset_manager.application.bootstrap.applier import BootstrapApplier
from harness_asset_manager.application.bootstrap.planner import BootstrapPlanner
from harness_asset_manager.application.container import build_backend_container
from tests.support.fake_home import FakeHomeSpec, seed_skill_package, write_cli_stub


class TestNormalizationIntegration(unittest.TestCase):
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
        ):
            p.mkdir(parents=True, exist_ok=True)
            
        write_cli_stub(self.spec.bin_dir / "hermes", "hermes")
        self.container = build_backend_container(self.spec.env())

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_legacy_binding_normalization(self):
        # Seed a skill in HAM store
        skill_src = self.spec.home / "downloads" / "tailnet-web-serving"
        seed_skill_package(skill_src.parent, "tailnet-web-serving", "tailnet-web-serving")
        dest1 = self.container.skills_store.ingest(
            source_path=skill_src,
            declared_name="tailnet-web-serving",
            source_kind="github",
            source_locator="github:org/tailnet-web-serving"
        )
        self.container.skills_mutations.enable_managed_package(dest1, "hermes")
        skill_ref1 = dest1.name
        
        # Manually create a legacy Hermes binding directly in ~/.hermes/skills/
        legacy_path = self.spec.hermes_skills_root / "tailnet-web-serving"
        legacy_path.symlink_to(self.spec.skills_store_root / skill_ref1)
        
        # Also seed a native Hermes skill (must not be touched)
        native_skill = self.spec.hermes_skills_root / "native-skill"
        native_skill.mkdir()
        (native_skill / "SKILL.md").write_text("native")
        
        # Also create a foreign content collision in the canonical harnessam/ category
        canonical_dir = self.spec.hermes_skills_root / "harnessam"
        canonical_dir.mkdir(exist_ok=True)
        conflict_path = canonical_dir / "other-skill"
        conflict_path.mkdir()
        (conflict_path / "SKILL.md").write_text("conflict")
        
        # Setup manifest so other-skill is enabled for Hermes without triggering immediate linking
        other_src = self.spec.home / "downloads" / "other-skill"
        seed_skill_package(other_src.parent, "other-skill", "other-skill")
        dest2 = self.container.skills_store.ingest(
            source_path=other_src,
            declared_name="other-skill",
            source_kind="github",
            source_locator="github:org/other-skill"
        )
        skill_ref2 = dest2.name
        
        # Manually append other-skill to the manifest to simulate drift
        manifest_path = self.container.skills_store.manifest_path
        manifest_data = json.loads(manifest_path.read_text())
        for entry in manifest_data["entries"]:
            if entry["packageDir"] == skill_ref2:
                entry.setdefault("enabledHarnesses", []).append("hermes")
        manifest_path.write_text(json.dumps(manifest_data))
        
        planner = BootstrapPlanner.from_container(self.container)
        plan = planner.plan()
        
        # Tailnet should be relinked, other-skill should conflict
        tailnet_action = next(a for a in plan.actions if a.ref == f"shared:{skill_ref1}")
        other_action = next(a for a in plan.actions if a.ref == f"shared:{skill_ref2}")
        
        self.assertEqual(tailnet_action.action, "relink")
        self.assertEqual(len(tailnet_action.legacy_targets), 1)
        self.assertEqual(tailnet_action.legacy_targets[0], legacy_path)
        
        self.assertEqual(other_action.action, "conflict")
        
        # Now apply
        applier = BootstrapApplier(self.container)
        applier.apply(plan.actions)
        
        # Validate additive & destructive behaviour
        canonical_target = canonical_dir / skill_ref1
        self.assertTrue(canonical_target.is_symlink())
        self.assertEqual(canonical_target.resolve(), self.spec.skills_store_root / skill_ref1)
        
        # Legacy target unlinked
        self.assertFalse(legacy_path.exists())
        self.assertFalse(legacy_path.is_symlink())
        
        # Foreign target never overwritten
        self.assertTrue(conflict_path.is_dir())
        self.assertFalse(conflict_path.is_symlink())
        
        # Native skill untouched
        self.assertTrue(native_skill.is_dir())
        
        # Verify no foreign-machine absolute path written to manifest
        manifest_content = json.loads(manifest_path.read_text())
        tailnet_entry = next(e for e in manifest_content["entries"] if e["packageDir"] == skill_ref1)
        self.assertEqual(tailnet_entry["enabledHarnesses"], ["hermes"])
        
        # Idempotent: run again, should be a no-op
        plan2 = planner.plan()
        tailnet_action2 = next(a for a in plan2.actions if a.ref == f"shared:{skill_ref1}")
        self.assertEqual(tailnet_action2.action, "skip")
        
if __name__ == '__main__':
    unittest.main()
