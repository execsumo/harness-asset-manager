from __future__ import annotations

import unittest

from harness_asset_manager.application.permissions.mappers import (
    AntigravityPermissionsMapper,
    ClaudeCodePermissionsMapper,
    CodexPermissionsMapper,
)
from harness_asset_manager.application.permissions.store import PermissionSpec


class ClaudeCodePermissionsMapperTests(unittest.TestCase):
    def test_representable(self) -> None:
        mapper = ClaudeCodePermissionsMapper()
        # Supported decision (deny), scope, and pattern
        is_repr, _, _ = mapper.representable(PermissionSpec("p1", "deny", "shell", "git push"))
        self.assertTrue(is_repr)
        # Unsupported decision (allow/ask)
        is_repr, _, _ = mapper.representable(PermissionSpec("p1", "allow", "shell", "git push"))
        self.assertFalse(is_repr)
        # Unsupported scope
        is_repr, _, _ = mapper.representable(PermissionSpec("p1", "deny", "any", "git push"))
        self.assertFalse(is_repr)

    def test_file_write_dual_rule_round_trip_and_drift(self) -> None:
        mapper = ClaudeCodePermissionsMapper()
        doc = {}
        spec = PermissionSpec("p-write", "deny", "file_write", "~/.zshrc")

        # Enable - must write both Edit and Write rules under deny
        mapper.enable_permission(doc, spec)
        self.assertIn("permissions", doc)
        self.assertEqual(doc["permissions"]["defaultMode"], "bypassPermissions")
        self.assertIn("deny", doc["permissions"])
        rules = doc["permissions"]["deny"]
        self.assertIn("Edit(~/.zshrc)", rules)
        self.assertIn("Write(~/.zshrc)", rules)

        # Read back
        entries = mapper.read_entries(doc, [spec])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].id, "p-write")
        self.assertEqual(entries[0].decision, "deny")
        self.assertEqual(entries[0].scope, "file_write")
        self.assertEqual(entries[0].pattern, "~/.zshrc")
        self.assertEqual(sorted(entries[0].payload["rules"]), ["Edit(~/.zshrc)", "Write(~/.zshrc)"])

        # Drift case: only Edit(~/.zshrc) is present, Write is missing
        doc_drifted = {
            "permissions": {
                "deny": ["Edit(~/.zshrc)"]
            }
        }
        entries_drifted = mapper.read_entries(doc_drifted, [spec])
        self.assertEqual(len(entries_drifted), 1)
        self.assertEqual(entries_drifted[0].id, "p-write")
        self.assertEqual(entries_drifted[0].payload["rules"], ["Edit(~/.zshrc)"])

        # Disable
        mapper.disable_permission(doc, "p-write", "~/.zshrc")
        self.assertNotIn("permissions", doc)


class AntigravityPermissionsMapperTests(unittest.TestCase):
    def test_representable(self) -> None:
        mapper = AntigravityPermissionsMapper()
        # Supported shell and mcp with deny decision
        self.assertTrue(mapper.representable(PermissionSpec("p1", "deny", "shell", "git push"))[0])
        self.assertTrue(mapper.representable(PermissionSpec("p2", "deny", "mcp", "server/tool"))[0])
        
        # Unsupported decision allow
        self.assertFalse(mapper.representable(PermissionSpec("p1", "allow", "shell", "git push"))[0])

        # Unsupported file/web
        is_repr, reason, _ = mapper.representable(PermissionSpec("p3", "deny", "file_read", "~/.zshrc"))
        self.assertFalse(is_repr)
        self.assertEqual(reason, "Scope 'file_read' is not supported by Antigravity")

    def test_round_trip_shell_and_mcp(self) -> None:
        mapper = AntigravityPermissionsMapper()
        doc = {}
        spec_shell = PermissionSpec("p-shell", "deny", "shell", "git push")
        spec_mcp = PermissionSpec("p-mcp", "deny", "mcp", "server/tool")

        # Enable shell
        mapper.enable_permission(doc, spec_shell)
        self.assertIn("permissions", doc)
        self.assertEqual(doc["toolPermission"], "always-proceed")
        self.assertEqual(doc["permissions"]["deny"], ["command(git push)"])

        # Enable mcp
        mapper.enable_permission(doc, spec_mcp)
        self.assertIn("mcp(server/tool)", doc["permissions"]["deny"])

        # Read back
        entries = mapper.read_entries(doc, [spec_shell, spec_mcp])
        self.assertEqual(len(entries), 2)
        
        # Disable
        mapper.disable_permission(doc, "p-shell", "git push")
        self.assertNotIn("command(git push)", doc["permissions"]["deny"])


class CodexPermissionsMapperTests(unittest.TestCase):
    def test_representable(self) -> None:
        mapper = CodexPermissionsMapper()
        
        # Supported file_read, file_write, web with deny decision
        self.assertTrue(mapper.representable(PermissionSpec("p1", "deny", "file_read", "~/.zshrc"))[0])
        self.assertTrue(mapper.representable(PermissionSpec("p2", "deny", "file_write", "~/.zshrc"))[0])
        self.assertTrue(mapper.representable(PermissionSpec("p3", "deny", "web", "api.example.com"))[0])

        # Unsupported decision allow/ask
        is_repr, reason, _ = mapper.representable(PermissionSpec("p4", "allow", "file_read", "~/.zshrc"))
        self.assertFalse(is_repr)
        self.assertIn("Denylist ONLY mode", reason or "")

    def test_round_trip(self) -> None:
        mapper = CodexPermissionsMapper()
        doc = {}
        spec_read = PermissionSpec("p-read", "deny", "file_read", "~/.zshrc")
        spec_write = PermissionSpec("p-write", "deny", "file_write", "./secrets/**")
        spec_web = PermissionSpec("p-web", "deny", "web", "api.example.com")

        # Enable all
        mapper.enable_permission(doc, spec_read)
        mapper.enable_permission(doc, spec_write)
        mapper.enable_permission(doc, spec_web)

        profile = doc["permissions"]["harness-asset-manager"]
        self.assertEqual(doc["approval_policy"], "never")
        self.assertEqual(doc["default_permissions"], "harness-asset-manager")
        self.assertEqual(profile["extends"], ":workspace")
        self.assertEqual(profile["filesystem"]["~/.zshrc"], "deny")
        self.assertEqual(profile["filesystem"]["./secrets/**"], "deny")
        self.assertEqual(profile["network"]["enabled"], True)
        self.assertEqual(profile["network"]["mode"], "allow")
        self.assertEqual(profile["network"]["domains"]["api.example.com"], "deny")

        # Read back
        entries = mapper.read_entries(doc, [spec_read, spec_write, spec_web])
        self.assertEqual(len(entries), 3)

        # Disable one by one
        mapper.disable_permission(doc, "p-read", "~/.zshrc")
        self.assertNotIn("~/.zshrc", doc["permissions"]["harness-asset-manager"]["filesystem"])

    def test_user_authored_profile_preservation(self) -> None:
        mapper = CodexPermissionsMapper()
        doc = {
            "permissions": {
                "user-profile": {
                    "extends": ":read-only",
                    "filesystem": {
                        "~/.bashrc": "deny"
                    }
                }
            }
        }

        spec = PermissionSpec("p-read", "deny", "file_read", "~/.zshrc")
        mapper.enable_permission(doc, spec)

        # The harness-asset-manager profile should be created, and user-profile preserved
        self.assertIn("harness-asset-manager", doc["permissions"])
        self.assertIn("user-profile", doc["permissions"])
        self.assertEqual(doc["permissions"]["user-profile"]["filesystem"]["~/.bashrc"], "deny")

        # Disable managed permission
        mapper.disable_permission(doc, "p-read", "~/.zshrc")
        
        # harness-asset-manager profile should be cleaned up, user-profile preserved
        self.assertNotIn("harness-asset-manager", doc["permissions"])
        self.assertIn("user-profile", doc["permissions"])
        self.assertEqual(doc["permissions"]["user-profile"]["filesystem"]["~/.bashrc"], "deny")


if __name__ == "__main__":
    unittest.main()
