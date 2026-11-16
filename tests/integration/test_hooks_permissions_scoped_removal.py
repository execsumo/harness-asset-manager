"""Pressure test: disabling and uninstalling managed hooks and permissions through
the API removes only the managed entries, never user entries that look like them.

The app writes the managed entries into the real harness config files of a fake
home, the test then adds user look-alikes by hand (same command in other events and
matcher groups, same pattern in other decision lists and scopes, user default-policy
settings), and drives disable and delete through the HTTP API.
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
    path.write_text(tomlkit.dumps(payload), encoding="utf-8")


class HookScopedRemovalPressureTests(unittest.TestCase):
    def _hook_path(self, harness: AppTestHarness, name: str) -> Path:
        return harness.container.hooks_read_models.require_enabled_adapter(name).config_path

    def test_disable_and_uninstall_keep_user_look_alikes(self) -> None:
        with AppTestHarness() as harness:
            harness.post_json(
                "/api/hooks",
                {"id": "lint", "event": "pre_tool_use", "command": "lint.sh", "match": "shell"},
            )
            harness.post_json("/api/hooks", {"id": "notify", "event": "stop", "command": "notify.sh"})
            for name in ("claude", "codex", "cursor"):
                self.assertTrue(harness.post_json("/api/hooks/lint/enable", {"harness": name})["ok"])
            for name in ("opencode", "agy"):
                self.assertTrue(harness.post_json("/api/hooks/notify/enable", {"harness": name})["ok"])

            claude_path = self._hook_path(harness, "claude")
            codex_path = self._hook_path(harness, "codex")
            cursor_path = self._hook_path(harness, "cursor")
            opencode_path = self._hook_path(harness, "opencode")
            agy_path = self._hook_path(harness, "agy")

            # User look-alikes: same command, other events and matcher groups.
            claude = _read_json(claude_path)
            claude["theme"] = "dark"
            claude_hooks = claude["hooks"]
            assert isinstance(claude_hooks, dict)
            claude_hooks["PreToolUse"][0]["hooks"].append(_cmd("lint.sh"))
            claude_hooks["PreToolUse"].append({"matcher": "Read", "hooks": [_cmd("lint.sh")]})
            claude_hooks["PostToolUse"] = [{"matcher": "Bash", "hooks": [_cmd("lint.sh")]}]
            _write_json(claude_path, claude)

            codex = _read_toml(codex_path)
            codex["model"] = "o3"
            codex_hooks = codex["hooks"]
            assert isinstance(codex_hooks, dict)
            codex_hooks["PreToolUse"].append({"matcher": "Read", "hooks": [_cmd("lint.sh")]})
            codex_hooks["PostToolUse"] = [{"matcher": "Bash", "hooks": [_cmd("lint.sh")]}]
            _write_toml(codex_path, codex)

            cursor = _read_json(cursor_path)
            cursor_hooks = cursor["hooks"]
            assert isinstance(cursor_hooks, dict)
            cursor_hooks["afterShellExecution"] = [{"command": "lint.sh"}]
            cursor_hooks["preToolUse"] = [{"command": "lint.sh"}]
            _write_json(cursor_path, cursor)

            opencode = _read_json(opencode_path)
            opencode_hook = opencode["experimental"]["hook"]  # type: ignore[index]
            opencode_hook["file_edited"] = {"*.py": [_argv("notify.sh")]}
            _write_json(opencode_path, opencode)

            agy_user_path = harness.spec.home / ".gemini" / "antigravity-cli" / "hooks.json"
            _write_json(agy_user_path, {"user-notify": {"enabled": True, "Stop": [_cmd("notify.sh")]}})
            agy_user_before = agy_user_path.read_bytes()

            # Disable one binding, then uninstall both hooks everywhere.
            self.assertTrue(harness.post_json("/api/hooks/lint/disable", {"harness": "claude"})["ok"])
            deleted_lint = harness.delete_json("/api/hooks/lint")
            self.assertTrue(deleted_lint["ok"], deleted_lint)
            # Claude may be listed too: the scan still attributes the user's identical
            # id-less copy at the managed location to "lint", and removing nothing there
            # is a success.
            self.assertLessEqual({"codex", "cursor"}, set(deleted_lint["succeeded"]))
            deleted_notify = harness.delete_json("/api/hooks/notify")
            self.assertTrue(deleted_notify["ok"], deleted_notify)
            self.assertEqual(sorted(deleted_notify["succeeded"]), ["agy", "opencode"])

            self.assertEqual(
                _read_json(claude_path),
                {
                    "hooks": {
                        "PreToolUse": [
                            {"matcher": "Bash", "hooks": [_cmd("lint.sh")]},
                            {"matcher": "Read", "hooks": [_cmd("lint.sh")]},
                        ],
                        "PostToolUse": [{"matcher": "Bash", "hooks": [_cmd("lint.sh")]}],
                    },
                    "theme": "dark",
                },
            )
            self.assertEqual(
                _read_toml(codex_path),
                {
                    "hooks": {
                        "PreToolUse": [{"matcher": "Read", "hooks": [_cmd("lint.sh")]}],
                        "PostToolUse": [{"matcher": "Bash", "hooks": [_cmd("lint.sh")]}],
                    },
                    "model": "o3",
                },
            )
            self.assertEqual(
                _read_json(cursor_path),
                {
                    "version": 1,
                    "hooks": {
                        "afterShellExecution": [{"command": "lint.sh"}],
                        "preToolUse": [{"command": "lint.sh"}],
                    },
                },
            )
            self.assertEqual(
                _read_json(opencode_path),
                {"experimental": {"hook": {"file_edited": {"*.py": [_argv("notify.sh")]}}}},
            )
            self.assertEqual(_read_json(agy_path), {})
            self.assertEqual(agy_user_path.read_bytes(), agy_user_before)

            entry_ids = {entry["id"] for entry in harness.get_json("/api/hooks")["entries"]}
            self.assertNotIn("lint", entry_ids)
            self.assertNotIn("notify", entry_ids)

    def test_adopted_hook_uninstall_keeps_same_command_in_other_event(self) -> None:
        with AppTestHarness() as harness:
            claude_path = harness.spec.home / ".claude" / "settings.json"
            _write_json(
                claude_path,
                {
                    "hooks": {
                        "PreToolUse": [{"matcher": "Bash", "hooks": [_cmd("fmt.sh")]}],
                        "Stop": [{"hooks": [_cmd("fmt.sh")]}],
                    }
                },
            )
            entry = next(
                e
                for e in harness.get_json("/api/hooks")["entries"]
                if e.get("spec", {}).get("event") == "pre_tool_use"
            )
            self.assertTrue(harness.post_json(f"/api/hooks/{entry['id']}/promote", {})["ok"])

            deleted = harness.delete_json(f"/api/hooks/{entry['id']}")

            self.assertTrue(deleted["ok"], deleted)
            self.assertEqual(_read_json(claude_path), {"hooks": {"Stop": [{"hooks": [_cmd("fmt.sh")]}]}})

    def test_ambiguous_managed_hook_is_refused_with_409(self) -> None:
        with AppTestHarness() as harness:
            harness.post_json(
                "/api/hooks",
                {"id": "lint", "event": "pre_tool_use", "command": "lint.sh", "match": "shell"},
            )
            harness.post_json("/api/hooks/lint/enable", {"harness": "claude"})
            claude_path = self._hook_path(harness, "claude")
            claude = _read_json(claude_path)
            hooks = claude["hooks"]
            assert isinstance(hooks, dict)
            # The user copied the managed entry, id and all, into another event.
            hooks["PostToolUse"] = [{"matcher": "Bash", "hooks": [_cmd("lint.sh", id="lint")]}]
            _write_json(claude_path, claude)
            before = claude_path.read_bytes()

            refused = harness.post_json(
                "/api/hooks/lint/disable", {"harness": "claude"}, expected_status=409
            )
            self.assertIn("cannot be identified", json.dumps(refused))
            self.assertEqual(claude_path.read_bytes(), before)

            deleted = harness.delete_json("/api/hooks/lint")
            self.assertFalse(deleted["ok"])
            self.assertEqual([failure["harness"] for failure in deleted["failed"]], ["claude"])
            self.assertEqual(claude_path.read_bytes(), before)
            # A refused uninstall keeps the managed record so it can be retried.
            self.assertEqual(harness.get_json("/api/hooks/lint")["id"], "lint")


class PermissionScopedRemovalPressureTests(unittest.TestCase):
    def _permission_path(self, harness: AppTestHarness, name: str) -> Path:
        return harness.container.permissions_read_models.require_enabled_adapter(name).config_path

    def test_disable_and_uninstall_keep_user_look_alikes(self) -> None:
        with AppTestHarness() as harness:
            harness.post_json(
                "/api/permissions",
                {"id": "git-push", "decision": "deny", "scope": "shell", "pattern": "git push"},
            )
            harness.post_json(
                "/api/permissions",
                {"id": "zshrc", "decision": "deny", "scope": "file_read", "pattern": "~/.zshrc"},
            )
            for name in ("claude", "agy"):
                self.assertTrue(harness.post_json("/api/permissions/git-push/enable", {"harness": name})["ok"])
            for name in ("claude", "codex", "cursor"):
                self.assertTrue(harness.post_json("/api/permissions/zshrc/enable", {"harness": name})["ok"])

            claude_path = self._permission_path(harness, "claude")
            agy_path = self._permission_path(harness, "agy")
            cursor_path = self._permission_path(harness, "cursor")
            codex_path = self._permission_path(harness, "codex")

            # User look-alikes: same pattern in other decision lists and scopes,
            # plus user default-policy choices made after the app's.
            claude = _read_json(claude_path)
            claude_permissions = claude["permissions"]
            assert isinstance(claude_permissions, dict)
            claude_permissions["defaultMode"] = "acceptEdits"
            claude_permissions["allow"] = ["Bash(git push)"]
            claude_permissions["ask"] = ["Bash(git push)", "Read(~/.zshrc)"]
            claude_permissions["deny"] += ["Read(git push)", "Edit(~/.zshrc)"]
            _write_json(claude_path, claude)

            agy = _read_json(agy_path)
            agy_permissions = agy["permissions"]
            assert isinstance(agy_permissions, dict)
            agy_permissions["allow"] = ["command(git push)"]
            agy_permissions["deny"] += ["mcp(git push)"]
            _write_json(agy_path, agy)

            cursor = _read_json(cursor_path)
            cursor_permissions = cursor["permissions"]
            assert isinstance(cursor_permissions, dict)
            cursor_permissions["deny"] += ["Write(~/.zshrc)"]
            _write_json(cursor_path, cursor)

            codex = _read_toml(codex_path)
            codex["model"] = "o3"
            codex_permissions = codex["permissions"]
            assert isinstance(codex_permissions, dict)
            codex_permissions["user-profile"] = {"extends": ":read-only", "filesystem": {"~/.zshrc": "deny"}}
            _write_toml(codex_path, codex)

            self.assertTrue(harness.post_json("/api/permissions/git-push/disable", {"harness": "claude"})["ok"])
            deleted_push = harness.delete_json("/api/permissions/git-push")
            self.assertTrue(deleted_push["ok"], deleted_push)
            self.assertEqual(deleted_push["succeeded"], ["agy"])
            deleted_zshrc = harness.delete_json("/api/permissions/zshrc")
            self.assertTrue(deleted_zshrc["ok"], deleted_zshrc)
            self.assertEqual(sorted(deleted_zshrc["succeeded"]), ["claude", "codex", "cursor"])

            self.assertEqual(
                _read_json(claude_path),
                {
                    "permissions": {
                        "defaultMode": "acceptEdits",
                        "allow": ["Bash(git push)"],
                        "ask": ["Bash(git push)", "Read(~/.zshrc)"],
                        "deny": ["Read(git push)", "Edit(~/.zshrc)"],
                    }
                },
            )
            self.assertEqual(
                _read_json(agy_path),
                {
                    "toolPermission": "always-proceed",
                    "permissions": {"allow": ["command(git push)"], "deny": ["mcp(git push)"]},
                },
            )
            cursor_after = _read_json(cursor_path)
            self.assertEqual(cursor_after["permissions"], {"deny": ["Write(~/.zshrc)"]})
            self.assertEqual(cursor_after["approvalMode"], "unrestricted")
            self.assertEqual(
                _read_toml(codex_path),
                {
                    "model": "o3",
                    "permissions": {
                        "user-profile": {"extends": ":read-only", "filesystem": {"~/.zshrc": "deny"}}
                    },
                },
            )

            entry_ids = {entry["id"] for entry in harness.get_json("/api/permissions")["entries"]}
            self.assertNotIn("git-push", entry_ids)
            self.assertNotIn("zshrc", entry_ids)

    def test_ambiguous_managed_rule_is_refused_with_409(self) -> None:
        with AppTestHarness() as harness:
            harness.post_json(
                "/api/permissions",
                {"id": "git-push", "decision": "deny", "scope": "shell", "pattern": "git push"},
            )
            harness.post_json("/api/permissions/git-push/enable", {"harness": "claude"})
            claude_path = self._permission_path(harness, "claude")
            claude = _read_json(claude_path)
            claude_permissions = claude["permissions"]
            assert isinstance(claude_permissions, dict)
            claude_permissions["deny"] += ["Bash(git push)"]
            _write_json(claude_path, claude)
            before = claude_path.read_bytes()

            refused = harness.post_json(
                "/api/permissions/git-push/disable", {"harness": "claude"}, expected_status=409
            )
            self.assertIn("more than once", json.dumps(refused))
            self.assertEqual(claude_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
