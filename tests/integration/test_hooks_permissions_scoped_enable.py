"""Pressure test: enabling a managed hook or permission through the API writes only
the managed entry, never removing or rewriting user entries that look like it.

The test seeds the real harness config files of a fake home with user entries (the
same hook command under other events, the same permission pattern in other decision
lists, user default-policy settings), enables managed hooks and permissions through
the HTTP API, then disables them, and checks the user's entries survive both steps.
"""

from __future__ import annotations

import json
import tomllib
import unittest
from pathlib import Path

import tomlkit

from tests.support.app_harness import AppTestHarness


def _cmd(command: str, **extra: object) -> dict[str, object]:
    return {"type": "command", "command": command, **extra}


def _argv(command: str) -> dict[str, object]:
    return {"command": ["/bin/sh", "-c", command]}


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_toml(path: Path) -> dict[str, object]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def _write_toml(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(tomlkit.dumps(payload), encoding="utf-8")


class HookScopedEnablePressureTests(unittest.TestCase):
    def _hook_path(self, harness: AppTestHarness, name: str) -> Path:
        return harness.container.hooks_read_models.require_enabled_adapter(name).config_path

    def test_cursor_enable_keeps_same_command_in_other_events(self) -> None:
        with AppTestHarness() as harness:
            cursor_path = self._hook_path(harness, "cursor")
            user = {
                "version": 1,
                "hooks": {
                    "afterShellExecution": [{"command": "lint.sh"}],
                    "preToolUse": [{"command": "lint.sh"}],
                },
            }
            _write_json(cursor_path, user)
            harness.post_json(
                "/api/hooks",
                {"id": "lint", "event": "pre_tool_use", "command": "lint.sh", "match": "shell"},
            )

            self.assertTrue(harness.post_json("/api/hooks/lint/enable", {"harness": "cursor"})["ok"])
            self.assertEqual(
                _read_json(cursor_path),
                {
                    "version": 1,
                    "hooks": {
                        "afterShellExecution": [{"command": "lint.sh"}],
                        "preToolUse": [{"command": "lint.sh"}],
                        "beforeShellExecution": [{"command": "lint.sh"}],
                    },
                },
            )

            self.assertTrue(harness.post_json("/api/hooks/lint/disable", {"harness": "cursor"})["ok"])
            self.assertEqual(_read_json(cursor_path), user)

    def test_opencode_enable_keeps_same_command_in_other_events(self) -> None:
        with AppTestHarness() as harness:
            opencode_path = self._hook_path(harness, "opencode")
            user = {
                "experimental": {
                    "hook": {
                        "file_edited": {"*": [_argv("notify.sh")], "*.py": [_argv("notify.sh")]},
                        "session_completed": [_argv("fmt.sh")],
                    }
                }
            }
            _write_json(opencode_path, user)
            harness.post_json("/api/hooks", {"id": "notify", "event": "stop", "command": "notify.sh"})
            harness.post_json(
                "/api/hooks",
                {"id": "fmt", "event": "post_tool_use", "command": "fmt.sh", "match": "file_write"},
            )

            self.assertTrue(harness.post_json("/api/hooks/notify/enable", {"harness": "opencode"})["ok"])
            self.assertTrue(harness.post_json("/api/hooks/fmt/enable", {"harness": "opencode"})["ok"])
            self.assertEqual(
                _read_json(opencode_path),
                {
                    "experimental": {
                        "hook": {
                            "file_edited": {
                                "*": [_argv("notify.sh"), _argv("fmt.sh")],
                                "*.py": [_argv("notify.sh")],
                            },
                            "session_completed": [_argv("fmt.sh"), _argv("notify.sh")],
                        }
                    }
                },
            )

            self.assertTrue(harness.post_json("/api/hooks/notify/disable", {"harness": "opencode"})["ok"])
            self.assertTrue(harness.post_json("/api/hooks/fmt/disable", {"harness": "opencode"})["ok"])
            self.assertEqual(_read_json(opencode_path), user)


class PermissionScopedEnablePressureTests(unittest.TestCase):
    def _permission_path(self, harness: AppTestHarness, name: str) -> Path:
        return harness.container.permissions_read_models.require_enabled_adapter(name).config_path

    def _create(self, harness: AppTestHarness, id: str, scope: str, pattern: str) -> None:
        harness.post_json(
            "/api/permissions",
            {"id": id, "decision": "deny", "scope": scope, "pattern": pattern},
        )

    def test_enable_keeps_user_rules_and_default_policy(self) -> None:
        with AppTestHarness() as harness:
            self._create(harness, "git-push", "shell", "git push")
            self._create(harness, "zshrc", "file_read", "~/.zshrc")
            claude_path = self._permission_path(harness, "claude")
            agy_path = self._permission_path(harness, "agy")
            cursor_path = self._permission_path(harness, "cursor")
            codex_path = self._permission_path(harness, "codex")

            claude_user = {
                "theme": "dark",
                "permissions": {
                    "defaultMode": "acceptEdits",
                    "allow": ["Bash(git push)"],
                    "ask": ["Bash(git push)", "Read(~/.zshrc)"],
                },
            }
            agy_user = {
                "toolPermission": "request-review",
                "permissions": {"allow": ["command(git push)"], "ask": ["command(git push)"]},
            }
            cursor_user = {"version": 1, "editor": {"vimMode": True}, "approvalMode": "auto-review"}
            codex_user = {"model": "o3", "approval_policy": "on-request"}
            _write_json(claude_path, claude_user)
            _write_json(agy_path, agy_user)
            _write_json(cursor_path, cursor_user)
            _write_toml(codex_path, codex_user)

            for name in ("claude", "agy"):
                self.assertTrue(harness.post_json("/api/permissions/git-push/enable", {"harness": name})["ok"])
            for name in ("claude", "codex", "cursor"):
                self.assertTrue(harness.post_json("/api/permissions/zshrc/enable", {"harness": name})["ok"])

            self.assertEqual(
                _read_json(claude_path),
                {
                    "theme": "dark",
                    "permissions": {
                        "defaultMode": "acceptEdits",
                        "allow": ["Bash(git push)"],
                        "ask": ["Bash(git push)", "Read(~/.zshrc)"],
                        "deny": ["Bash(git push)", "Read(~/.zshrc)"],
                    },
                },
            )
            self.assertEqual(
                _read_json(agy_path),
                {
                    "toolPermission": "request-review",
                    "permissions": {
                        "allow": ["command(git push)"],
                        "ask": ["command(git push)"],
                        "deny": ["command(git push)"],
                    },
                },
            )
            cursor_enabled = _read_json(cursor_path)
            self.assertEqual(cursor_enabled["approvalMode"], "auto-review")
            self.assertEqual(cursor_enabled["permissions"], {"deny": ["Read(~/.zshrc)"]})
            codex_enabled = _read_toml(codex_path)
            self.assertEqual(codex_enabled["approval_policy"], "on-request")
            self.assertEqual(codex_enabled["default_permissions"], "harness-asset-manager")

            # Every managed binding still reads as enabled.
            for id, names in (("git-push", {"claude", "agy"}), ("zshrc", {"claude", "codex", "cursor"})):
                sightings = harness.get_json(f"/api/permissions/{id}")["sightings"]
                managed = {s["harness"] for s in sightings if s["state"] == "managed"}
                self.assertEqual(managed, names)

            deleted_push = harness.delete_json("/api/permissions/git-push")
            self.assertTrue(deleted_push["ok"], deleted_push)
            deleted_zshrc = harness.delete_json("/api/permissions/zshrc")
            self.assertTrue(deleted_zshrc["ok"], deleted_zshrc)

            self.assertEqual(_read_json(claude_path), claude_user)
            self.assertEqual(_read_json(agy_path), agy_user)
            self.assertEqual(_read_json(cursor_path), cursor_user)
            self.assertEqual(_read_toml(codex_path), codex_user)

    def test_disable_restores_the_recorded_default_policy_not_a_guess(self) -> None:
        with AppTestHarness() as harness:
            self._create(harness, "git-push", "shell", "git push")
            self._create(harness, "zshrc", "file_read", "~/.zshrc")
            claude_path = self._permission_path(harness, "claude")
            agy_path = self._permission_path(harness, "agy")
            cursor_path = self._permission_path(harness, "cursor")
            codex_path = self._permission_path(harness, "codex")

            # The user already chose the same values the app would write.
            claude_user = {"permissions": {"defaultMode": "bypassPermissions"}}
            agy_user = {"toolPermission": "always-proceed"}
            cursor_user = {"version": 1, "editor": {"vimMode": False}, "approvalMode": "unrestricted"}
            codex_user = {"approval_policy": "never"}
            _write_json(claude_path, claude_user)
            _write_json(agy_path, agy_user)
            _write_json(cursor_path, cursor_user)
            _write_toml(codex_path, codex_user)

            for name in ("claude", "agy"):
                self.assertTrue(harness.post_json("/api/permissions/git-push/enable", {"harness": name})["ok"])
            for name in ("codex", "cursor"):
                self.assertTrue(harness.post_json("/api/permissions/zshrc/enable", {"harness": name})["ok"])
            for name in ("claude", "agy"):
                self.assertTrue(harness.post_json("/api/permissions/git-push/disable", {"harness": name})["ok"])
            for name in ("codex", "cursor"):
                self.assertTrue(harness.post_json("/api/permissions/zshrc/disable", {"harness": name})["ok"])

            self.assertEqual(_read_json(claude_path), claude_user)
            self.assertEqual(_read_json(agy_path), agy_user)
            self.assertEqual(_read_json(cursor_path), cursor_user)
            self.assertEqual(_read_toml(codex_path), codex_user)

    def test_disable_removes_the_default_policy_the_app_wrote(self) -> None:
        with AppTestHarness() as harness:
            self._create(harness, "git-push", "shell", "git push")
            claude_path = self._permission_path(harness, "claude")
            _write_json(claude_path, {"theme": "dark"})

            harness.post_json("/api/permissions/git-push/enable", {"harness": "claude"})
            enabled = _read_json(claude_path)["permissions"]
            assert isinstance(enabled, dict)
            self.assertEqual(enabled["defaultMode"], "bypassPermissions")

            harness.post_json("/api/permissions/git-push/disable", {"harness": "claude"})
            self.assertEqual(_read_json(claude_path), {"theme": "dark"})

    def test_codex_enable_keeps_user_default_permissions_profile(self) -> None:
        with AppTestHarness() as harness:
            self._create(harness, "zshrc", "file_read", "~/.zshrc")
            codex_path = self._permission_path(harness, "codex")
            codex_user = {
                "default_permissions": "user-profile",
                "permissions": {"user-profile": {"extends": ":read-only"}},
            }
            _write_toml(codex_path, codex_user)

            harness.post_json("/api/permissions/zshrc/enable", {"harness": "codex"})
            enabled = _read_toml(codex_path)
            self.assertEqual(enabled["default_permissions"], "user-profile")
            self.assertNotIn("approval_policy", enabled)

            harness.post_json("/api/permissions/zshrc/disable", {"harness": "codex"})
            self.assertEqual(_read_toml(codex_path), codex_user)


if __name__ == "__main__":
    unittest.main()
