from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness_asset_manager.application.permissions.default_policy import (
    DefaultPolicyStore,
    PolicyRecord,
    claim_default_policy,
    default_policy_path,
    release_default_policy,
)
from harness_asset_manager.application.permissions.store import PermissionStore
from harness_asset_manager.paths import resolve_app_paths
from tests.unit.test_permissions_adapters import _adapter, _spec

KEY = ("permissions", "defaultMode")


class ClaimAndReleaseTests(unittest.TestCase):
    def test_absent_default_is_written_and_released(self) -> None:
        document: dict[str, object] = {"theme": "dark"}
        record: PolicyRecord = {}
        self.assertTrue(claim_default_policy(document, KEY, "bypass", record, legacy=False))
        self.assertEqual(document, {"theme": "dark", "permissions": {"defaultMode": "bypass"}})
        self.assertEqual(record, {"permissions.defaultMode": {"written": "bypass"}})
        release_default_policy(document, record)
        self.assertEqual(document, {"theme": "dark", "permissions": {}})

    def test_user_default_is_kept_and_recorded(self) -> None:
        for value in ("acceptEdits", "bypass"):
            document: dict[str, object] = {"permissions": {"defaultMode": value}}
            record: PolicyRecord = {}
            self.assertFalse(claim_default_policy(document, KEY, "bypass", record, legacy=False))
            self.assertEqual(document, {"permissions": {"defaultMode": value}})
            self.assertEqual(record, {"permissions.defaultMode": {"previous": value}})
            release_default_policy(document, record)
            self.assertEqual(document, {"permissions": {"defaultMode": value}})

    def test_a_default_the_user_changed_after_the_app_wrote_it_is_not_released(self) -> None:
        document: dict[str, object] = {}
        record: PolicyRecord = {}
        claim_default_policy(document, KEY, "bypass", record, legacy=False)
        document["permissions"] = {"defaultMode": "auto"}
        release_default_policy(document, record)
        self.assertEqual(document, {"permissions": {"defaultMode": "auto"}})

    def test_owned_default_is_reapplied_on_re_enable(self) -> None:
        document: dict[str, object] = {}
        record: PolicyRecord = {}
        claim_default_policy(document, KEY, "bypass", record, legacy=False)
        document["permissions"] = {"defaultMode": "auto"}
        self.assertTrue(claim_default_policy(document, KEY, "bypass", record, legacy=False))
        self.assertEqual(document, {"permissions": {"defaultMode": "bypass"}})

    def test_legacy_value_equal_to_the_apps_is_owned(self) -> None:
        document: dict[str, object] = {"permissions": {"defaultMode": "bypass"}}
        record: PolicyRecord = {}
        self.assertTrue(claim_default_policy(document, KEY, "bypass", record, legacy=True))
        release_default_policy(document, record)
        self.assertEqual(document, {"permissions": {}})

    def test_gated_default_is_not_written(self) -> None:
        document: dict[str, object] = {}
        record: PolicyRecord = {}
        self.assertFalse(
            claim_default_policy(document, ("approval_policy",), "never", record, legacy=False, allowed=False)
        )
        self.assertEqual((document, record), ({}, {}))

    def test_store_round_trip_and_clear(self) -> None:
        with TemporaryDirectory() as tmp:
            store = DefaultPolicyStore(Path(tmp) / "permissions" / "default-policy.json")
            self.assertIsNone(store.get("claude"))
            store.put("claude", {"permissions.defaultMode": {"written": "bypass"}})
            store.put("cursor", {"approvalMode": {"previous": "auto-review"}})
            self.assertEqual(store.get("claude"), {"permissions.defaultMode": {"written": "bypass"}})
            store.clear("claude")
            self.assertIsNone(store.get("claude"))
            self.assertEqual(store.get("cursor"), {"approvalMode": {"previous": "auto-review"}})


class LegacyStateTests(unittest.TestCase):
    """Bindings enabled before ownership was recorded, when enable always set the default."""

    def _setup(self, home: Path) -> tuple[Path, DefaultPolicyStore]:
        app_paths = resolve_app_paths({"HOME": str(home), "PATH": ""})
        store = PermissionStore(app_paths.permissions_store_manifest)
        store.upsert_managed(_spec("git-push"))
        store.upsert_managed(_spec("rm", pattern="rm"))
        adapter = _adapter("claude", home=home)
        adapter.config_path.parent.mkdir(parents=True, exist_ok=True)
        adapter.config_path.write_text(
            json.dumps({"permissions": {"defaultMode": "bypassPermissions", "deny": ["Bash(git push)"]}}),
            encoding="utf-8",
        )
        return adapter.config_path, DefaultPolicyStore(default_policy_path(app_paths.permissions_store_manifest))

    def test_disable_without_a_record_removes_the_apps_mode(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            path, policies = self._setup(home)
            _adapter("claude", home=home).disable_permission("git-push")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {})
            self.assertIsNone(policies.get("claude"))

    def test_enable_next_to_a_legacy_rule_takes_ownership_of_the_mode(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            path, policies = self._setup(home)
            adapter = _adapter("claude", home=home)
            adapter.enable_permission(_spec("rm", pattern="rm"))
            self.assertEqual(
                policies.get("claude"), {"permissions.defaultMode": {"written": "bypassPermissions"}}
            )
            adapter.disable_permission("rm")
            adapter.disable_permission("git-push")
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {})
            self.assertIsNone(policies.get("claude"))

    def test_first_enable_does_not_take_a_user_mode_equal_to_the_apps(self) -> None:
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            path, policies = self._setup(home)
            path.write_text(json.dumps({"permissions": {"defaultMode": "bypassPermissions"}}), encoding="utf-8")
            adapter = _adapter("claude", home=home)
            adapter.enable_permission(_spec("git-push"))
            adapter.disable_permission("git-push")
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")),
                {"permissions": {"defaultMode": "bypassPermissions"}},
            )


if __name__ == "__main__":
    unittest.main()
