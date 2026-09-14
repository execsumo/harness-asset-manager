from __future__ import annotations

import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from harness_asset_manager.env_names import (
    FACTORY_ROOT_ENV,
    HERMES_HOME_ENV,
    HERMES_ROOT_ENV,
    legacy_name,
)
from harness_asset_manager.harness.catalog import (
    SUPPORTED_HARNESS_DEFINITIONS,
    _hermes_home,
    _hermes_profile_skills_root,
    _hermes_root,
    supported_harness_definitions,
)
from harness_asset_manager.harness.contracts import (
    AgentFileBindingProfile,
    CommandFileBindingProfile,
    ConfigSubtreeBindingProfile,
    FileTreeBindingProfile,
)
from harness_asset_manager.harness.resolution import resolve_context


@contextmanager
def hermetic_env():
    """Drop the ambient environment entirely.

    ``resolve_platform_context`` *merges* ``os.environ`` with the dict it is handed, so
    a developer or CI runner with ``HERMES_HOME`` exported would fail the default case
    below through no fault of the code. Clearing is the only way these assertions mean
    what they say.
    """
    with mock.patch.dict("os.environ", {}, clear=True):
        yield


class HermesHomePrecedenceTests(unittest.TestCase):
    def test_hermes_home_three_way_precedence(self) -> None:
        with hermetic_env():
            new_val = "/tmp/new-hermes-home"
            legacy_val = "/tmp/legacy-hermes-home"
            plain_val = "/tmp/plain-hermes-home"
            legacy_env_key = legacy_name(HERMES_HOME_ENV)

            # Case 1: Default when no env vars set -> context.home / ".hermes"
            ctx_default = resolve_context({})
            self.assertEqual(_hermes_home(ctx_default), ctx_default.home / ".hermes")

            # Case 2: Plain HERMES_HOME set -> honored when our vars unset
            ctx_plain = resolve_context({"HERMES_HOME": plain_val})
            self.assertEqual(_hermes_home(ctx_plain), Path(plain_val))

            # Case 3: Legacy SKILL_MANAGER_HERMES_HOME set -> takes precedence over plain HERMES_HOME
            ctx_legacy = resolve_context({
                "HERMES_HOME": plain_val,
                legacy_env_key: legacy_val,
            })
            self.assertEqual(_hermes_home(ctx_legacy), Path(legacy_val))

            # Case 4: HARNESS_ASSET_MANAGER_HERMES_HOME set -> takes precedence over legacy and plain
            ctx_new = resolve_context({
                "HERMES_HOME": plain_val,
                legacy_env_key: legacy_val,
                HERMES_HOME_ENV: new_val,
            })
            self.assertEqual(_hermes_home(ctx_new), Path(new_val))

    def test_skills_root_override_does_not_move_hermes_root_or_profile_paths(self) -> None:
        with hermetic_env():
            real_root = Path("/tmp/real-hermes-root")
            skills_root = Path("/tmp/custom-hermes-skills")
            ctx = resolve_context(
                {
                    "HERMES_HOME": str(real_root),
                    HERMES_ROOT_ENV: str(skills_root),
                }
            )

            self.assertEqual(_hermes_root(ctx), real_root)
            self.assertEqual(
                _hermes_profile_skills_root(ctx, "coder"),
                real_root / "profiles" / "coder" / "skills",
            )


class PiHarnessCatalogTests(unittest.TestCase):
    def test_pi_uses_the_global_agent_store_for_supported_file_families(self) -> None:
        with hermetic_env():
            context = resolve_context({"HOME": "/tmp/pi-home"})
            definition = next(item for item in supported_harness_definitions() if item.harness == "pi")
            self.assertEqual(definition.logo_key, "pi")

            skills = definition.binding_for("skills")
            self.assertIsInstance(skills, FileTreeBindingProfile)
            self.assertEqual(
                skills.resolve_managed_root(context),
                Path("/tmp/pi-home/.pi/agent/skills"),
            )

            agents = definition.binding_for("agents")
            self.assertIsInstance(agents, AgentFileBindingProfile)
            self.assertEqual(
                agents.resolve_output_dir(context),
                Path("/tmp/pi-home/.pi/agent/agents"),
            )

            commands = definition.binding_for("slash_commands")
            self.assertIsInstance(commands, CommandFileBindingProfile)
            self.assertEqual(
                commands.resolve_output_dir(context),
                Path("/tmp/pi-home/.pi/agent/prompts"),
            )
            self.assertEqual(commands.invocation_prefix, "/")
            self.assertEqual(commands.render_format, "frontmatter_markdown")

    def test_pi_configs_bind_the_user_settings_file(self) -> None:
        with hermetic_env():
            context = resolve_context({"HOME": "/tmp/pi-home"})
            definition = next(item for item in supported_harness_definitions() if item.harness == "pi")

            configs = definition.binding_for("configs")
            self.assertIsInstance(configs, ConfigSubtreeBindingProfile)
            self.assertEqual(
                configs.resolve_config_path(context),
                Path("/tmp/pi-home/.pi/agent/settings.json"),
            )
            self.assertEqual(configs.file_format, "json")
            self.assertEqual(configs.subtree_path, ())
            # ``skills``/``prompts`` are resource path lists the file families own,
            # and ``trackingId`` is a per-install analytics UUID.
            self.assertEqual(
                configs.exclusion_keys,
                frozenset({"skills", "prompts", "trackingId"}),
            )


class FactoryDroidHarnessCatalogTests(unittest.TestCase):
    def test_droid_configs_bind_the_personal_settings_file(self) -> None:
        with hermetic_env():
            context = resolve_context({"HOME": "/tmp/droid-home"})
            definition = next(
                item for item in supported_harness_definitions() if item.harness == "droid"
            )

            configs = definition.binding_for("configs")
            self.assertIsInstance(configs, ConfigSubtreeBindingProfile)
            self.assertEqual(
                configs.resolve_config_path(context),
                Path("/tmp/droid-home/.factory/settings.json"),
            )
            self.assertEqual(configs.file_format, "json")
            # Command policy stays with the (deliberately unmapped) permissions
            # family rather than travelling as a preference — docs/factory-droid.md.
            for key in ("hooks", "commandAllowlist", "commandDenylist", "commandBlocklist"):
                self.assertIn(key, configs.exclusion_keys)

    def test_droid_configs_follow_the_factory_root_override(self) -> None:
        with hermetic_env():
            context = resolve_context(
                {"HOME": "/tmp/droid-home", FACTORY_ROOT_ENV: "/tmp/factory-elsewhere"}
            )
            definition = next(
                item for item in supported_harness_definitions() if item.harness == "droid"
            )

            self.assertEqual(
                definition.binding_for("configs").resolve_config_path(context),
                Path("/tmp/factory-elsewhere/settings.json"),
            )


class ConfigsBindingExclusionTests(unittest.TestCase):
    """Every family sharing a harness's config file must be excluded from Configs.

    Configs captures *the whole document minus ``exclusion_keys``*, so a family that
    writes into the same file and is not named there gets silently copied into the
    portable manifest and re-applied on the next machine. That is how OpenCode's
    ``mcp`` block leaked: the exclusions carried Claude's ``mcpServers`` spelling.
    """

    def test_same_file_family_keys_are_excluded_from_configs(self) -> None:
        with hermetic_env():
            context = resolve_context({"HOME": "/tmp/parity-home"})
            for definition in SUPPORTED_HARNESS_DEFINITIONS:
                configs = definition.binding_for("configs")
                if not isinstance(configs, ConfigSubtreeBindingProfile):
                    continue
                configs_path = configs.resolve_config_path(context)

                for family, profile in definition.bindings.items():
                    if family == "configs":
                        continue
                    if not isinstance(profile, ConfigSubtreeBindingProfile):
                        continue
                    if profile.resolve_config_path(context) != configs_path:
                        continue
                    if not profile.subtree_path:
                        continue
                    with self.subTest(harness=definition.harness, family=family):
                        self.assertIn(
                            profile.subtree_path[0],
                            configs.exclusion_keys,
                            f"{definition.harness}/{family} writes "
                            f"{'.'.join(profile.subtree_path)} into the same file as "
                            f"configs; add {profile.subtree_path[0]!r} to exclusion_keys.",
                        )


if __name__ == "__main__":
    unittest.main()
