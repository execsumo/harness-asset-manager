from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from harness_asset_manager.application.agents.hermes_profile import (
    detach_profile,
    ensure_profile,
)
from harness_asset_manager.application.agents.model import AgentDefinition
from harness_asset_manager.errors import MutationError
from harness_asset_manager.harness.catalog import _hermes_root
from harness_asset_manager.harness.hermes_profiles import (
    HermesProfileNameError,
    hermes_profile_name,
    validate_slug_collisions,
)

class MockContext:
    def __init__(self, home: Path, env: dict[str, str]) -> None:
        self.home = home
        self.env = env

class HermesProfileNameTests(unittest.TestCase):
    def test_plain_slug_passes_through(self) -> None:
        self.assertEqual(hermes_profile_name("plain-slug"), "plain-slug")

    def test_dotted_slug_maps_to_hyphens(self) -> None:
        self.assertEqual(hermes_profile_name("my.agent"), "my-agent")

    def test_illegal_first_char_is_stripped_to_yield_legal_first_char(self) -> None:
        self.assertEqual(hermes_profile_name("-my-agent"), "my-agent")
        self.assertEqual(hermes_profile_name("_my-agent"), "my-agent")
        # Note: Hermes regex ^[a-z0-9] means digit is actually legal, wait! 
        # But let's check what `isalnum` does. It keeps digits!
        self.assertEqual(hermes_profile_name("1agent"), "1agent")

    def test_long_slug_truncates_without_trailing_separator(self) -> None:
        long_slug = "a" * 63 + "-b" # 65 chars
        # truncate to 64 chars will leave a trailing hyphen: "a"*63 + "-"
        # so the hyphen is removed, giving "a"*63
        self.assertEqual(hermes_profile_name(long_slug), "a" * 63)

    def test_refuses_reserved_name(self) -> None:
        with self.assertRaises(HermesProfileNameError) as ctx:
            hermes_profile_name("test")
        self.assertEqual(ctx.exception.slug, "test")
        self.assertEqual(ctx.exception.attempted_name, "test")
        self.assertIn("reserved", ctx.exception.reason)

    def test_refuses_subcommand(self) -> None:
        with self.assertRaises(HermesProfileNameError) as ctx:
            hermes_profile_name("config")
        self.assertEqual(ctx.exception.slug, "config")
        self.assertEqual(ctx.exception.attempted_name, "config")
        self.assertIn("subcommand", ctx.exception.reason)

    def test_refuses_empty_mapped_name(self) -> None:
        with self.assertRaises(HermesProfileNameError) as ctx:
            hermes_profile_name("---")
        self.assertEqual(ctx.exception.slug, "---")
        self.assertEqual(ctx.exception.attempted_name, "")
        self.assertIn("empty", ctx.exception.reason)

    def test_collision_refusal(self) -> None:
        with self.assertRaises(MutationError) as ctx:
            validate_slug_collisions({"my.agent", "my-agent"})
        self.assertIn("both map to the same Hermes profile name", str(ctx.exception))
        self.assertIn("my.agent", str(ctx.exception))
        self.assertIn("my-agent", str(ctx.exception))


class HermesRootDerivationTests(unittest.TestCase):
    def test_no_override(self) -> None:
        with TemporaryDirectory() as temp:
            home = Path(temp)
            ctx = MockContext(home, {})
            self.assertEqual(_hermes_root(ctx), home / ".hermes")

    def test_override_at_plain_root(self) -> None:
        with TemporaryDirectory() as temp:
            override = Path(temp) / "my_hermes"
            ctx = MockContext(Path(temp), {"HERMES_HOME": str(override)})
            self.assertEqual(_hermes_root(ctx), override)

    def test_override_at_named_profile(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp) / "hermes_root"
            profile_dir = root / "profiles" / "my-agent"
            profile_dir.parent.mkdir(parents=True, exist_ok=True)
            # Create a marker: config.yaml
            (root / "config.yaml").touch()

            ctx = MockContext(Path(temp), {"HERMES_HOME": str(profile_dir)})
            self.assertEqual(_hermes_root(ctx), root)

    def test_decoy_path_lacking_markers(self) -> None:
        with TemporaryDirectory() as temp:
            root = Path(temp) / "hermes_root"
            profile_dir = root / "profiles" / "my-agent"
            profile_dir.mkdir(parents=True, exist_ok=True)
            # NO markers created

            ctx = MockContext(Path(temp), {"HERMES_HOME": str(profile_dir)})
            # Path itself is returned
            self.assertEqual(_hermes_root(ctx), profile_dir)

class HermesProvisioningTests(unittest.TestCase):
    def _create_agent(self, slug: str) -> AgentDefinition:
        return AgentDefinition(
            slug=slug,
            name="My Agent",
            description="A test agent",
            prompt="You are a test agent.",
            tools=(),
            path=Path("/dummy"),
        )

    def test_provisioning_seeds_files_and_directories(self) -> None:
        with TemporaryDirectory() as temp:
            hermes_root = Path(temp) / ".hermes"
            agent = self._create_agent("test-agent")
            ensure_profile(agent, hermes_root)

            home = hermes_root / "profiles" / "test-agent"
            self.assertTrue(home.is_dir())
            
            env_file = home / ".env"
            self.assertTrue(env_file.is_file())
            self.assertEqual(env_file.stat().st_mode & 0o777, 0o600)
            self.assertIn("Hermes environment variables", env_file.read_text())
            self.assertNotIn("secret", env_file.read_text())

            soul_file = home / "SOUL.md"
            self.assertTrue(soul_file.is_file())
            self.assertEqual(soul_file.read_text(), "You are a test agent.")

            self.assertTrue((home / ".no-bundled-skills").is_file())
            self.assertTrue((home / "skills" / "harnessam").is_dir())

            for subdir in ("memories", "sessions", "skills", "skins", "logs", "plans", "workspace", "cron", "home"):
                self.assertTrue((home / subdir).is_dir())

    def test_config_yaml_mirrors_version_and_absent_when_root_missing(self) -> None:
        with TemporaryDirectory() as temp:
            hermes_root = Path(temp) / ".hermes"
            agent = self._create_agent("test-agent")
            
            # Root config missing
            ensure_profile(agent, hermes_root)
            config_yaml = hermes_root / "profiles" / "test-agent" / "config.yaml"
            self.assertTrue(config_yaml.is_file())
            self.assertNotIn("_config_version", config_yaml.read_text())

            # Root config has version
            hermes_root.mkdir(parents=True, exist_ok=True)
            (hermes_root / "config.yaml").write_text("_config_version: 42\n")
            
            ensure_profile(self._create_agent("test-agent-2"), hermes_root)
            config_yaml2 = hermes_root / "profiles" / "test-agent-2" / "config.yaml"
            self.assertIn("_config_version: 42", config_yaml2.read_text())

    def test_config_yaml_round_trip_preserves_unrelated_keys(self) -> None:
        with TemporaryDirectory() as temp:
            hermes_root = Path(temp) / ".hermes"
            hermes_root.mkdir(parents=True, exist_ok=True)
            (hermes_root / "config.yaml").write_text("_config_version: 42\n")

            home = hermes_root / "profiles" / "test-agent"
            home.mkdir(parents=True, exist_ok=True)
            config_yaml = home / "config.yaml"
            config_yaml.write_text("# my comment\ncustom_key: 123\n_config_version: 41\n")

            agent = self._create_agent("test-agent")
            ensure_profile(agent, hermes_root)

            content = config_yaml.read_text()
            self.assertIn("# my comment", content)
            self.assertIn("custom_key: 123", content)
            self.assertIn("_config_version: 42", content)

    def test_provisioning_is_idempotent(self) -> None:
        with TemporaryDirectory() as temp:
            hermes_root = Path(temp) / ".hermes"
            agent = self._create_agent("test-agent")
            
            ensure_profile(agent, hermes_root)
            
            env_file = hermes_root / "profiles" / "test-agent" / ".env"
            env_file.write_text("MY_SECRET=123")
            
            # Update soul prompt
            agent = AgentDefinition(
                slug="test-agent",
                name="My Agent",
                description="A test agent",
                prompt="New prompt.",
                tools=(),
                path=Path("/dummy"),
            )
            ensure_profile(agent, hermes_root)
            
            # SOUL.md is updated
            soul_file = hermes_root / "profiles" / "test-agent" / "SOUL.md"
            self.assertEqual(soul_file.read_text(), "New prompt.")
            
            # .env is untouched
            self.assertEqual(env_file.read_text(), "MY_SECRET=123")

    def test_tombstone_refusal(self) -> None:
        with TemporaryDirectory() as temp:
            hermes_root = Path(temp) / ".hermes"
            home = hermes_root / "profiles" / "test-agent"
            home.mkdir(parents=True, exist_ok=True)
            
            tombstone_dir = hermes_root / "profiles" / ".deleted"
            tombstone_dir.mkdir(parents=True, exist_ok=True)
            tombstone = tombstone_dir / "test-agent"
            tombstone.touch()

            # Empty shell is reclaimable
            agent = self._create_agent("test-agent")
            ensure_profile(agent, hermes_root)
            self.assertTrue((home / "SOUL.md").exists())
            self.assertFalse(tombstone.exists(), "Tombstone should be cleared when profile is reclaimed")
            
            # Carrying identity files makes provisioning fail
            tombstone.touch() # recreate tombstone
            (home / ".env").touch()
            with self.assertRaises(MutationError) as ctx:
                ensure_profile(agent, hermes_root)
            self.assertIn("deleted but still contains identity files", str(ctx.exception))

    def test_detach_is_orphan_safe(self) -> None:
        with TemporaryDirectory() as temp:
            hermes_root = Path(temp) / ".hermes"
            agent = self._create_agent("test-agent")
            ensure_profile(agent, hermes_root)
            
            home = hermes_root / "profiles" / "test-agent"
            (home / "sessions").mkdir(parents=True, exist_ok=True)
            (home / "sessions" / "123.json").touch()
            
            detach_profile(agent, hermes_root)
            
            # SOUL.md and .no-bundled-skills should survive
            self.assertTrue((home / "SOUL.md").exists())
            self.assertTrue((home / ".no-bundled-skills").exists())
            self.assertTrue(home.is_dir())
            self.assertTrue((home / "sessions" / "123.json").exists())

    def test_failing_profile_operation_does_not_roll_back_ham_state(self) -> None:
        with TemporaryDirectory() as temp:
            hermes_root = Path(temp) / ".hermes"
            agent = self._create_agent("test-agent")
            
            # Force a failure midway, e.g. permission error writing SOUL.md
            with mock.patch("harness_asset_manager.application.agents.hermes_profile.atomic_write_text", side_effect=OSError("boom")):
                with self.assertRaises(OSError):
                    ensure_profile(agent, hermes_root)
                    
            # Check what was created remains (no rollback)
            home = hermes_root / "profiles" / "test-agent"
            self.assertTrue(home.is_dir())
            self.assertTrue((home / "memories").is_dir())

if __name__ == "__main__":
    unittest.main()
