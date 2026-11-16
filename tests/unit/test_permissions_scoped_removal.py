"""Disabling a managed permission removes only the rule and policy the app owns.

Each case seeds a harness config holding the managed rule next to user rules that
share its pattern (other decision lists, other scopes) and user default-policy
settings, disables the managed rule, and asserts the user's rules and settings
survive.
"""

from __future__ import annotations

import hashlib
import json
import tomllib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness_asset_manager.application.permissions.adapters import (
    FileBackedPermissionsAdapter,
)
from harness_asset_manager.application.permissions.store import (
    PermissionSpec,
    PermissionStore,
)
from harness_asset_manager.errors import MutationError
from harness_asset_manager.harness import HarnessKernelService, HarnessSupportStore
from harness_asset_manager.paths import resolve_app_paths


def _env(home: Path) -> dict[str, str]:
    return {"HOME": str(home), "PATH": ""}


def _adapter(harness: str, *, home: Path) -> FileBackedPermissionsAdapter:
    kernel = HarnessKernelService.from_environment(
        _env(home),
        support_store=HarnessSupportStore(home / "settings.json"),
    )
    binding = next(
        binding
        for binding in kernel.bindings_for_family("permissions")
        if binding.definition.harness == harness
    )
    return FileBackedPermissionsAdapter(
        definition=binding.definition,
        profile=binding.profile,
        context=kernel.context,
    )


def _manage(home: Path, *specs: PermissionSpec) -> None:
    # The adapter resolves the managed spec from the env-derived manifest path.
    store = PermissionStore(resolve_app_paths(_env(home)).permissions_store_manifest)
    for spec in specs:
        store.upsert_managed(spec)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


class ClaudeScopedPermissionRemovalTests(unittest.TestCase):
    def test_disable_keeps_pattern_in_other_lists_and_scopes(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            _manage(home, PermissionSpec("git-push", "deny", "shell", "git push"))
            adapter = _adapter("claude", home=home)
            _write_json(
                adapter.config_path,
                {
                    "permissions": {
                        "defaultMode": "bypassPermissions",
                        "allow": ["Bash(git push)"],
                        "ask": ["Bash(git push)"],
                        "deny": ["Bash(git push)", "Read(git push)", "WebFetch(git push)"],
                    }
                },
            )

            adapter.disable_permission("git-push")

            self.assertEqual(
                _read_json(adapter.config_path),
                {
                    "permissions": {
                        "defaultMode": "bypassPermissions",
                        "allow": ["Bash(git push)"],
                        "ask": ["Bash(git push)"],
                        "deny": ["Read(git push)", "WebFetch(git push)"],
                    }
                },
            )

    def test_disable_file_write_keeps_other_edit_tool_rules(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            _manage(home, PermissionSpec("secrets", "deny", "file_write", "./secrets/**"))
            adapter = _adapter("claude", home=home)
            _write_json(
                adapter.config_path,
                {
                    "permissions": {
                        "defaultMode": "bypassPermissions",
                        "deny": [
                            "Edit(./secrets/**)",
                            "MultiEdit(./secrets/**)",
                            "Write(./secrets/**)",
                            "NotebookEdit(./secrets/**)",
                        ],
                    }
                },
            )

            adapter.disable_permission("secrets")

            self.assertEqual(
                _read_json(adapter.config_path),
                {
                    "permissions": {
                        "defaultMode": "bypassPermissions",
                        "deny": ["MultiEdit(./secrets/**)", "NotebookEdit(./secrets/**)"],
                    }
                },
            )

    def test_disable_last_rule_keeps_a_user_chosen_default_mode(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            _manage(home, PermissionSpec("git-push", "deny", "shell", "git push"))
            adapter = _adapter("claude", home=home)
            _write_json(
                adapter.config_path,
                {"permissions": {"defaultMode": "acceptEdits", "deny": ["Bash(git push)"]}},
            )

            adapter.disable_permission("git-push")

            self.assertEqual(
                _read_json(adapter.config_path),
                {"permissions": {"defaultMode": "acceptEdits"}},
            )

    def test_duplicate_rule_refuses_with_409(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            _manage(home, PermissionSpec("git-push", "deny", "shell", "git push"))
            adapter = _adapter("claude", home=home)
            _write_json(
                adapter.config_path,
                {"permissions": {"deny": ["Bash(git push)", "Bash(git push)"]}},
            )
            before = adapter.config_path.read_bytes()

            with self.assertRaises(MutationError) as ctx:
                adapter.disable_permission("git-push")

            self.assertEqual(ctx.exception.status, 409)
            self.assertEqual(adapter.config_path.read_bytes(), before)


class AntigravityScopedPermissionRemovalTests(unittest.TestCase):
    def test_disable_keeps_pattern_in_other_lists_and_scopes(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            _manage(home, PermissionSpec("git-push", "deny", "shell", "git push"))
            adapter = _adapter("agy", home=home)
            _write_json(
                adapter.config_path,
                {
                    "toolPermission": "always-proceed",
                    "permissions": {
                        "allow": ["command(git push)"],
                        "deny": ["command(git push)", "mcp(git push)"],
                    },
                },
            )

            adapter.disable_permission("git-push")

            self.assertEqual(
                _read_json(adapter.config_path),
                {
                    "toolPermission": "always-proceed",
                    "permissions": {"allow": ["command(git push)"], "deny": ["mcp(git push)"]},
                },
            )


class CursorScopedPermissionRemovalTests(unittest.TestCase):
    def test_disable_keeps_pattern_under_other_scope_and_policy(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            _manage(home, PermissionSpec("zshrc", "deny", "file_read", "~/.zshrc"))
            adapter = _adapter("cursor", home=home)
            _write_json(
                adapter.config_path,
                {
                    "version": 1,
                    "approvalMode": "unrestricted",
                    "permissions": {"deny": ["Read(~/.zshrc)", "Write(~/.zshrc)"]},
                },
            )

            adapter.disable_permission("zshrc")

            self.assertEqual(
                _read_json(adapter.config_path),
                {
                    "version": 1,
                    "approvalMode": "unrestricted",
                    "permissions": {"deny": ["Write(~/.zshrc)"]},
                },
            )


_CODEX_CROSS_SCOPE = """\
approval_policy = "never"
default_permissions = "harness-asset-manager"

[permissions.harness-asset-manager]
extends = ":workspace"

[permissions.harness-asset-manager.filesystem]
"intranet.example" = "deny"

[permissions.harness-asset-manager.network]
enabled = true
mode = "allow"

[permissions.harness-asset-manager.network.domains]
"intranet.example" = "deny"
"""

_CODEX_USER_POLICY = """\
approval_policy = "never"
default_permissions = "user-profile"

[permissions.user-profile]
extends = ":read-only"

[permissions.harness-asset-manager]
extends = ":workspace"

[permissions.harness-asset-manager.filesystem]
"~/.zshrc" = "deny"

[permissions.harness-asset-manager.network]
enabled = true
mode = "allow"
"""


class CodexScopedPermissionRemovalTests(unittest.TestCase):
    def test_disable_web_rule_keeps_same_pattern_on_filesystem(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            _manage(home, PermissionSpec("intranet", "deny", "web", "intranet.example"))
            adapter = _adapter("codex", home=home)
            adapter.config_path.parent.mkdir(parents=True, exist_ok=True)
            adapter.config_path.write_text(_CODEX_CROSS_SCOPE, encoding="utf-8")

            adapter.disable_permission("intranet")

            config = tomllib.loads(adapter.config_path.read_text(encoding="utf-8"))
            self.assertEqual(
                config,
                {
                    "approval_policy": "never",
                    "default_permissions": "harness-asset-manager",
                    "permissions": {
                        "harness-asset-manager": {
                            "extends": ":workspace",
                            "filesystem": {"intranet.example": "deny"},
                            "network": {"enabled": True, "mode": "allow", "domains": {}},
                        }
                    },
                },
            )

    def test_disable_last_rule_keeps_user_approval_policy(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            _manage(home, PermissionSpec("zshrc", "deny", "file_read", "~/.zshrc"))
            adapter = _adapter("codex", home=home)
            adapter.config_path.parent.mkdir(parents=True, exist_ok=True)
            adapter.config_path.write_text(_CODEX_USER_POLICY, encoding="utf-8")

            adapter.disable_permission("zshrc")

            config = tomllib.loads(adapter.config_path.read_text(encoding="utf-8"))
            self.assertEqual(
                config,
                {
                    "approval_policy": "never",
                    "default_permissions": "user-profile",
                    "permissions": {"user-profile": {"extends": ":read-only"}},
                },
            )


class AdoptedPermissionRemovalTests(unittest.TestCase):
    def test_adopted_rule_is_removed_by_its_own_identity(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            rule = "MultiEdit(./secrets/**)"
            rule_id = "manual:" + hashlib.sha256(rule.encode("utf-8")).hexdigest()[:16]
            _manage(home, PermissionSpec(rule_id, "deny", "file_write", "./secrets/**"))
            adapter = _adapter("claude", home=home)
            _write_json(
                adapter.config_path,
                {"permissions": {"deny": ["Edit(./secrets/**)", rule, "Write(./secrets/**)"]}},
            )

            adapter.disable_permission(rule_id)

            self.assertEqual(
                _read_json(adapter.config_path),
                {"permissions": {"deny": ["Edit(./secrets/**)", "Write(./secrets/**)"]}},
            )

    def test_adopted_rule_bound_to_another_harness_uses_the_rendered_rule(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            rule_id = "manual:" + hashlib.sha256(b"Bash(git status)").hexdigest()[:16]
            _manage(home, PermissionSpec(rule_id, "deny", "shell", "git status"))
            adapter = _adapter("agy", home=home)
            _write_json(
                adapter.config_path,
                {
                    "toolPermission": "always-proceed",
                    "permissions": {"deny": ["command(git status)", "mcp(git status)"]},
                },
            )

            adapter.disable_permission(rule_id)

            self.assertEqual(
                _read_json(adapter.config_path),
                {"toolPermission": "always-proceed", "permissions": {"deny": ["mcp(git status)"]}},
            )

    def test_unchanged_config_is_not_rewritten(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            _manage(home, PermissionSpec("git-push", "deny", "shell", "git push"))
            adapter = _adapter("claude", home=home)
            adapter.config_path.parent.mkdir(parents=True, exist_ok=True)
            adapter.config_path.write_text(
                '{"permissions":   {"deny": ["Bash(rm)"]}}', encoding="utf-8"
            )
            before = adapter.config_path.read_bytes()

            adapter.disable_permission("git-push")

            self.assertEqual(adapter.config_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
