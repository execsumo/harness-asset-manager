from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness_asset_manager.application.container import build_backend_container
from harness_asset_manager.application.hooks.store import (
    HookSpec,
    HookStore,
)
from harness_asset_manager.application.mcp.store import (
    McpServerSpec,
    McpServerStore,
    McpSource,
)
from harness_asset_manager.application.permissions.store import (
    PermissionSpec,
    PermissionStore,
)
from tests.support.fake_home import FakeHomeSpec, write_cli_stub


def _mcp_spec(name: str = "test-mcp", **overrides: object) -> McpServerSpec:
    fields: dict[str, object] = {
        "name": name,
        "display_name": "Test MCP",
        "source": McpSource.manual(name),
        "transport": "stdio",
        "command": "test-cmd",
    }
    fields.update(overrides)
    return McpServerSpec(**fields)  # type: ignore[arg-type]


def _hook_spec(id: str = "test-hook", **overrides: object) -> HookSpec:
    fields: dict[str, object] = {
        "id": id,
        "event": "pre_tool_use",
        "command": "echo test",
        "match": "file_write",
    }
    fields.update(overrides)
    return HookSpec(**fields)  # type: ignore[arg-type]


def _perm_spec(id: str = "test-perm", **overrides: object) -> PermissionSpec:
    fields: dict[str, object] = {
        "id": id,
        "decision": "deny",
        "scope": "file_read",
        "pattern": "/secrets/**",
    }
    fields.update(overrides)
    return PermissionSpec(**fields)  # type: ignore[arg-type]


class ConfigBindingIntentTests(unittest.TestCase):
    def test_mcp_absent_field_loads_as_no_intent(self) -> None:
        spec = McpServerSpec.from_dict({
            "name": "exa",
            "source": {"kind": "manual", "locator": "exa"},
            "transport": "stdio",
        })
        self.assertEqual(spec.enabled_harnesses, ())

    def test_mcp_empty_intent_is_omitted_from_json(self) -> None:
        self.assertNotIn("enabledHarnesses", _mcp_spec().to_dict())

    def test_mcp_round_trip_preserves_intent(self) -> None:
        spec = _mcp_spec(enabled_harnesses=("claude", "cursor"))
        d = spec.to_dict()
        self.assertEqual(d["enabledHarnesses"], ["claude", "cursor"])
        restored = McpServerSpec.from_dict(d)
        self.assertEqual(restored.enabled_harnesses, ("claude", "cursor"))

    def test_mcp_intent_is_sorted_and_deduplicated_on_read(self) -> None:
        spec = McpServerSpec.from_dict({
            "name": "exa",
            "source": {"kind": "manual", "locator": "exa"},
            "transport": "stdio",
            "enabledHarnesses": ["cursor", "claude", "cursor"],
        })
        self.assertEqual(spec.enabled_harnesses, ("claude", "cursor"))

    def test_mcp_malformed_intent_degrades_safely(self) -> None:
        for malformed in ("not a list", 123, [None, 42, "claude"], {"claude": True}):
            spec = McpServerSpec.from_dict({
                "name": "exa",
                "source": {"kind": "manual", "locator": "exa"},
                "transport": "stdio",
                "enabledHarnesses": malformed,
            })
            self.assertIsInstance(spec.enabled_harnesses, tuple)

    def test_mcp_with_binding(self) -> None:
        spec = _mcp_spec(enabled_harnesses=("claude",))
        # Adding existing is a no-op
        self.assertIs(spec.with_binding("claude", bound=True), spec)
        # Adding new returns updated
        added = spec.with_binding("codex", bound=True)
        self.assertEqual(added.enabled_harnesses, ("claude", "codex"))
        # Removing existing
        removed = added.with_binding("claude", bound=False)
        self.assertEqual(removed.enabled_harnesses, ("codex",))
        # Removing non-existing is a no-op
        self.assertIs(removed.with_binding("claude", bound=False), removed)

    def test_mcp_store_record_binding(self) -> None:
        with TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            store = McpServerStore(manifest_path)
            spec = _mcp_spec("exa")
            store.upsert_managed(spec)

            store.record_binding("exa", "claude", bound=True)
            loaded = store.get_managed("exa")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.enabled_harnesses, ("claude",))  # type: ignore[union-attr]

            store.record_binding("exa", "cursor", bound=True)
            loaded = store.get_managed("exa")
            self.assertEqual(loaded.enabled_harnesses, ("claude", "cursor"))  # type: ignore[union-attr]

            store.record_binding("exa", "claude", bound=False)
            loaded = store.get_managed("exa")
            self.assertEqual(loaded.enabled_harnesses, ("cursor",))  # type: ignore[union-attr]

    # Hook tests -------------------------------------------------------------

    def test_hook_absent_field_loads_as_no_intent(self) -> None:
        spec = HookSpec.from_dict({
            "id": "format",
            "event": "pre_tool_use",
            "command": "prettier",
        })
        self.assertEqual(spec.enabled_harnesses, ())

    def test_hook_empty_intent_is_omitted_from_json(self) -> None:
        self.assertNotIn("enabledHarnesses", _hook_spec().to_dict())

    def test_hook_round_trip_preserves_intent(self) -> None:
        spec = _hook_spec(enabled_harnesses=("claude", "cursor"))
        d = spec.to_dict()
        self.assertEqual(d["enabledHarnesses"], ["claude", "cursor"])
        restored = HookSpec.from_dict(d)
        self.assertEqual(restored.enabled_harnesses, ("claude", "cursor"))

    def test_hook_intent_is_sorted_and_deduplicated_on_read(self) -> None:
        spec = HookSpec.from_dict({
            "id": "format",
            "event": "pre_tool_use",
            "command": "prettier",
            "enabledHarnesses": ["cursor", "claude", "cursor"],
        })
        self.assertEqual(spec.enabled_harnesses, ("claude", "cursor"))

    def test_hook_malformed_intent_degrades_safely(self) -> None:
        for malformed in ("not a list", 123, [None, 42, "claude"], {"claude": True}):
            spec = HookSpec.from_dict({
                "id": "format",
                "event": "pre_tool_use",
                "command": "prettier",
                "enabledHarnesses": malformed,
            })
            self.assertIsInstance(spec.enabled_harnesses, tuple)

    def test_hook_with_binding(self) -> None:
        spec = _hook_spec(enabled_harnesses=("claude",))
        self.assertIs(spec.with_binding("claude", bound=True), spec)
        added = spec.with_binding("cursor", bound=True)
        self.assertEqual(added.enabled_harnesses, ("claude", "cursor"))
        removed = added.with_binding("claude", bound=False)
        self.assertEqual(removed.enabled_harnesses, ("cursor",))
        self.assertIs(removed.with_binding("claude", bound=False), removed)

    def test_hook_store_record_binding(self) -> None:
        with TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            store = HookStore(manifest_path)
            spec = _hook_spec("lint")
            store.upsert_managed(spec)

            store.record_binding("lint", "claude", bound=True)
            loaded = store.get_managed("lint")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.enabled_harnesses, ("claude",))  # type: ignore[union-attr]

            store.record_binding("lint", "cursor", bound=True)
            loaded = store.get_managed("lint")
            self.assertEqual(loaded.enabled_harnesses, ("claude", "cursor"))  # type: ignore[union-attr]

            store.record_binding("lint", "claude", bound=False)
            loaded = store.get_managed("lint")
            self.assertEqual(loaded.enabled_harnesses, ("cursor",))  # type: ignore[union-attr]

    # Permission tests -------------------------------------------------------

    def test_perm_absent_field_loads_as_no_intent(self) -> None:
        spec = PermissionSpec.from_dict({
            "id": "protect-secrets",
            "decision": "deny",
            "scope": "file_read",
            "pattern": "/secrets/**",
        })
        self.assertEqual(spec.enabled_harnesses, ())

    def test_perm_empty_intent_is_omitted_from_json(self) -> None:
        self.assertNotIn("enabledHarnesses", _perm_spec().to_dict())

    def test_perm_round_trip_preserves_intent(self) -> None:
        spec = _perm_spec(enabled_harnesses=("claude", "codex"))
        d = spec.to_dict()
        self.assertEqual(d["enabledHarnesses"], ["claude", "codex"])
        restored = PermissionSpec.from_dict(d)
        self.assertEqual(restored.enabled_harnesses, ("claude", "codex"))

    def test_perm_intent_is_sorted_and_deduplicated_on_read(self) -> None:
        spec = PermissionSpec.from_dict({
            "id": "protect-secrets",
            "decision": "deny",
            "scope": "file_read",
            "pattern": "/secrets/**",
            "enabledHarnesses": ["codex", "claude", "codex"],
        })
        self.assertEqual(spec.enabled_harnesses, ("claude", "codex"))

    def test_perm_malformed_intent_degrades_safely(self) -> None:
        for malformed in ("not a list", 123, [None, 42, "claude"], {"claude": True}):
            spec = PermissionSpec.from_dict({
                "id": "protect-secrets",
                "decision": "deny",
                "scope": "file_read",
                "pattern": "/secrets/**",
                "enabledHarnesses": malformed,
            })
            self.assertIsInstance(spec.enabled_harnesses, tuple)

    def test_perm_with_binding(self) -> None:
        spec = _perm_spec(enabled_harnesses=("claude",))
        self.assertIs(spec.with_binding("claude", bound=True), spec)
        added = spec.with_binding("codex", bound=True)
        self.assertEqual(added.enabled_harnesses, ("claude", "codex"))
        removed = added.with_binding("claude", bound=False)
        self.assertEqual(removed.enabled_harnesses, ("codex",))
        self.assertIs(removed.with_binding("claude", bound=False), removed)

    def test_perm_store_record_binding(self) -> None:
        with TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.json"
            store = PermissionStore(manifest_path)
            spec = _perm_spec("block-rm")
            store.upsert_managed(spec)

            store.record_binding("block-rm", "claude", bound=True)
            loaded = store.get_managed("block-rm")
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.enabled_harnesses, ("claude",))  # type: ignore[union-attr]

            store.record_binding("block-rm", "codex", bound=True)
            loaded = store.get_managed("block-rm")
            self.assertEqual(loaded.enabled_harnesses, ("claude", "codex"))  # type: ignore[union-attr]

            store.record_binding("block-rm", "claude", bound=False)
            loaded = store.get_managed("block-rm")
            self.assertEqual(loaded.enabled_harnesses, ("codex",))  # type: ignore[union-attr]

    # Integration: Mutation services record intent on enable/disable ----------

    def test_mutation_services_record_intent_in_container(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            spec = FakeHomeSpec(
                root=tmp_path,
                home=tmp_path / "home" / "user",
                xdg_config_home=tmp_path / "home" / "user" / ".config",
                xdg_data_home=tmp_path / "home" / "user" / ".local" / "share",
                xdg_state_home=tmp_path / "home" / "user" / ".local" / "state",
            )
            for p in (spec.claude_root, spec.cursor_root, spec.codex_root, spec.bin_dir):
                p.mkdir(parents=True, exist_ok=True)
            for exe in ("claude", "cursor-agent", "codex"):
                write_cli_stub(spec.bin_dir / exe, exe)

            container = build_backend_container(spec.env())

            # MCP
            container.mcp_store.upsert_managed(_mcp_spec("exa"))
            container.mcp_mutations.enable_server("exa", "claude")
            loaded_mcp = container.mcp_store.get_managed("exa")
            self.assertIsNotNone(loaded_mcp)
            self.assertIn("claude", loaded_mcp.enabled_harnesses)  # type: ignore[union-attr]

            container.mcp_mutations.disable_server("exa", "claude")
            loaded_mcp = container.mcp_store.get_managed("exa")
            self.assertNotIn("claude", loaded_mcp.enabled_harnesses)  # type: ignore[union-attr]

            # Hooks
            container.hooks_store.upsert_managed(_hook_spec("lint"))
            container.hooks_mutations.enable_hook("lint", "claude")
            loaded_hook = container.hooks_store.get_managed("lint")
            self.assertIsNotNone(loaded_hook)
            self.assertIn("claude", loaded_hook.enabled_harnesses)  # type: ignore[union-attr]

            container.hooks_mutations.disable_hook("lint", "claude")
            loaded_hook = container.hooks_store.get_managed("lint")
            self.assertNotIn("claude", loaded_hook.enabled_harnesses)  # type: ignore[union-attr]

            # Permissions
            container.permissions_store.upsert_managed(_perm_spec("block-env"))
            container.permissions_mutations.enable_permission("block-env", "claude")
            loaded_perm = container.permissions_store.get_managed("block-env")
            self.assertIsNotNone(loaded_perm)
            self.assertIn("claude", loaded_perm.enabled_harnesses)  # type: ignore[union-attr]

            container.permissions_mutations.disable_permission("block-env", "claude")
            loaded_perm = container.permissions_store.get_managed("block-env")
            self.assertNotIn("claude", loaded_perm.enabled_harnesses)  # type: ignore[union-attr]
