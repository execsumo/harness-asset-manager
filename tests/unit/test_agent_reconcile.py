from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from harness_asset_manager.application.agents import (
    AgentAuditLog,
    AgentBindingLedger,
    AgentHarnessAdapter,
    AgentMutationService,
    AgentReconcileService,
    AgentStore,
    AgentTarget,
    AuditEntry,
)
from harness_asset_manager.hashing import hash_file


class AgentReconcileFixture(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)

        self.store_root = root / "data" / "agents"
        self.claude_dir = root / "home" / ".claude" / "agents"
        self.cursor_dir = root / "home" / ".cursor" / "agents"
        self.opencode_dir = root / "home" / ".opencode" / "agents"
        self.codex_dir = root / "home" / ".codex" / "agents"
        self.conflicts_root = self.store_root / "conflicts"

        for directory in (
            self.store_root,
            self.claude_dir,
            self.cursor_dir,
            self.opencode_dir,
            self.codex_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

        self.claude_target = AgentTarget(
            id="claude",
            label="Claude",
            logo_key="claude",
            root_path=self.claude_dir.parent,
            output_dir=self.claude_dir,
            file_glob="*.md",
            render_format="markdown",
            docs_url="",
            installed=True,
        )
        self.cursor_target = AgentTarget(
            id="cursor",
            label="Cursor",
            logo_key="cursor",
            root_path=self.cursor_dir.parent,
            output_dir=self.cursor_dir,
            file_glob="*.md",
            render_format="markdown",
            docs_url="",
            installed=True,
        )
        self.opencode_target = AgentTarget(
            id="opencode",
            label="OpenCode",
            logo_key="opencode",
            root_path=self.opencode_dir.parent,
            output_dir=self.opencode_dir,
            file_glob="*.md",
            render_format="markdown",
            docs_url="",
            installed=True,
        )
        self.codex_target = AgentTarget(
            id="codex",
            label="Codex",
            logo_key="codex",
            root_path=self.codex_dir.parent,
            output_dir=self.codex_dir,
            file_glob="*.toml",
            render_format="codex_toml",
            docs_url="",
            installed=True,
        )

        self.adapters = {
            "claude": AgentHarnessAdapter(self.claude_target, self.store_root),
            "cursor": AgentHarnessAdapter(self.cursor_target, self.store_root),
            "opencode": AgentHarnessAdapter(self.opencode_target, self.store_root),
            "codex": AgentHarnessAdapter(self.codex_target, self.store_root),
        }

        self.targets = (
            self.claude_target,
            self.cursor_target,
            self.opencode_target,
            self.codex_target,
        )
        self.resolve = lambda: (self.targets, self.adapters)

        self.ledger_path = root / "data" / "bindings.json"
        self.audit_path = root / "data" / "audit.json"
        self.lock_path = root / "data" / "reconcile.lock"

        self.ledger = AgentBindingLedger(self.ledger_path)
        self.audit = AgentAuditLog(self.audit_path)

        def rebaseline(slug: str) -> None:
            store_path = self.store.path_for(slug)
            if not store_path.is_file():
                return
            live = tuple(h for h, a in self.adapters.items() if a.is_enabled(slug))
            self.ledger.rebaseline(slug, live, hash_file(store_path))

        self.store = AgentStore(self.store_root, rebaseline)
        self.mutations = AgentMutationService(self.store, self.resolve, self.ledger)

        self.enabled_setting = True
        self.service = AgentReconcileService(
            store=self.store,
            resolve=self.resolve,
            ledger=self.ledger,
            audit=self.audit,
            conflicts_root=self.conflicts_root,
            is_enabled=lambda: self.enabled_setting,
            lock_path=self.lock_path,
        )

    def create(self, name: str = "Auditor") -> str:
        return self.store.create(name=name, description="d", prompt="p").slug

    def clobber(self, slug: str, harness: str, content: str) -> Path:
        adapter = self.adapters[harness]
        path = adapter.binding_path(slug)
        if path.is_symlink() or path.exists():
            path.unlink()
        path.write_text(content, encoding="utf-8")
        return path


class TestAgentReconcile(AgentReconcileFixture):
    def test_1_clean_clobber_relinks_and_refreshes_ledger(self) -> None:
        slug = self.create()
        self.mutations.enable(slug, "claude")
        store_content = self.store.path_for(slug).read_text(encoding="utf-8")
        harness_path = self.clobber(slug, "claude", store_content)

        outcome = self.service.reconcile()
        self.assertTrue(harness_path.is_symlink())
        self.assertEqual(harness_path.read_text(encoding="utf-8"), store_content)
        self.assertEqual(len(outcome.actions), 1)
        self.assertEqual(outcome.actions[0].action, "relinked")
        self.assertEqual(outcome.actions[0].harness, "claude")
        record = self.ledger.record_for(slug, "claude")
        assert record is not None
        self.assertEqual(record.store_sha256, hash_file(self.store.path_for(slug)))

    def test_2_one_sided_clobber_adopts_and_relinks(self) -> None:
        slug = self.create()
        self.mutations.enable(slug, "claude")
        edited_content = "---\nname: Auditor\ndescription: d\n---\nharness edit\n"
        harness_path = self.clobber(slug, "claude", edited_content)

        outcome = self.service.reconcile()
        self.assertEqual(self.store.path_for(slug).read_text(encoding="utf-8"), edited_content)
        self.assertTrue(harness_path.is_symlink())
        self.assertEqual(len(outcome.actions), 1)
        self.assertEqual(outcome.actions[0].action, "adopted")
        self.assertEqual(outcome.actions[0].harness, "claude")

    def test_3_two_sided_conflict_changes_nothing(self) -> None:
        slug = self.create()
        self.mutations.enable(slug, "claude")
        harness_path = self.clobber(slug, "claude", "harness edit\n")
        self.store.update(slug, prompt="store edit")

        store_before = self.store.path_for(slug).read_text(encoding="utf-8")
        harness_before = harness_path.read_text(encoding="utf-8")
        ledger_before = self.ledger.load()

        outcome = self.service.reconcile()
        self.assertEqual(self.store.path_for(slug).read_text(encoding="utf-8"), store_before)
        self.assertEqual(harness_path.read_text(encoding="utf-8"), harness_before)
        self.assertEqual(self.ledger.load(), ledger_before)
        self.assertEqual(outcome.actions, ())
        self.assertEqual(self.audit.recent(), ())

    def test_4_three_harnesses_one_diverged_two_clean(self) -> None:
        slug = self.create()
        self.mutations.enable(slug, "claude")
        self.mutations.enable(slug, "cursor")
        self.mutations.enable(slug, "opencode")

        store_content = self.store.path_for(slug).read_text(encoding="utf-8")
        h_claude = self.clobber(slug, "claude", "claude edit\n")
        h_cursor = self.clobber(slug, "cursor", store_content)

        outcome = self.service.reconcile()
        self.assertEqual(self.store.path_for(slug).read_text(encoding="utf-8"), "claude edit\n")
        self.assertTrue(h_claude.is_symlink())
        self.assertTrue(h_cursor.is_symlink())
        self.assertTrue(self.adapters["opencode"].binding_path(slug).is_symlink())

        actions_by_harness = {a.harness: a.action for a in outcome.actions}
        self.assertEqual(actions_by_harness.get("claude"), "adopted")
        self.assertEqual(actions_by_harness.get("cursor"), "relinked")

    def test_5_three_harnesses_two_diverged_identical_content(self) -> None:
        slug = self.create()
        self.mutations.enable(slug, "claude")
        self.mutations.enable(slug, "cursor")
        self.mutations.enable(slug, "opencode")

        h_claude = self.clobber(slug, "claude", "same edit\n")
        h_cursor = self.clobber(slug, "cursor", "same edit\n")

        outcome = self.service.reconcile()
        self.assertEqual(self.store.path_for(slug).read_text(encoding="utf-8"), "same edit\n")
        self.assertTrue(h_claude.is_symlink())
        self.assertTrue(h_cursor.is_symlink())
        self.assertTrue(self.adapters["opencode"].binding_path(slug).is_symlink())
        self.assertEqual(len(outcome.actions), 2)
        actions = {a.action for a in outcome.actions}
        self.assertIn("adopted", actions)

    def test_6_three_harnesses_two_diverged_differing_content(self) -> None:
        slug = self.create()
        self.mutations.enable(slug, "claude")
        self.mutations.enable(slug, "cursor")
        self.mutations.enable(slug, "opencode")

        store_before = self.store.path_for(slug).read_text(encoding="utf-8")
        h_claude = self.clobber(slug, "claude", "claude edit\n")
        h_cursor = self.clobber(slug, "cursor", "cursor edit\n")

        outcome = self.service.reconcile()
        self.assertEqual(self.store.path_for(slug).read_text(encoding="utf-8"), store_before)
        self.assertFalse(h_claude.is_symlink())
        self.assertFalse(h_cursor.is_symlink())
        self.assertEqual(h_claude.read_text(encoding="utf-8"), "claude edit\n")
        self.assertEqual(h_cursor.read_text(encoding="utf-8"), "cursor edit\n")

        conflict_claude = self.conflicts_root / f"{slug}.claude.md"
        conflict_cursor = self.conflicts_root / f"{slug}.cursor.md"
        self.assertTrue(conflict_claude.is_file())
        self.assertTrue(conflict_cursor.is_file())
        self.assertEqual(conflict_claude.read_text(encoding="utf-8"), "claude edit\n")
        self.assertEqual(conflict_cursor.read_text(encoding="utf-8"), "cursor edit\n")

        self.assertEqual(len(outcome.issues), 1)
        self.assertIn("claude", outcome.issues[0][1])
        self.assertIn("cursor", outcome.issues[0][1])

    def test_7_is_enabled_false_takes_no_action(self) -> None:
        slug = self.create()
        self.mutations.enable(slug, "claude")
        h_claude = self.clobber(slug, "claude", "edit\n")
        self.enabled_setting = False

        outcome = self.service.reconcile()
        self.assertEqual(outcome.actions, ())
        self.assertFalse(h_claude.is_symlink())
        self.assertEqual(h_claude.read_text(encoding="utf-8"), "edit\n")
        self.assertEqual(self.audit.recent(), ())

    def test_8_codex_renders_harness_never_adopted(self) -> None:
        slug = self.create()
        self.mutations.enable(slug, "codex")
        codex_path = self.adapters["codex"].binding_path(slug)
        codex_path.write_text(codex_path.read_text(encoding="utf-8") + '\nextra = "mine"\n', encoding="utf-8")

        outcome = self.service.reconcile()
        self.assertEqual(outcome.actions, ())
        self.assertTrue(codex_path.is_file())
        self.assertIn('extra = "mine"', codex_path.read_text(encoding="utf-8"))

    def test_9_reconcile_is_idempotent(self) -> None:
        slug = self.create()
        self.mutations.enable(slug, "claude")
        self.clobber(slug, "claude", "edit\n")

        first = self.service.reconcile()
        self.assertEqual(len(first.actions), 1)

        second = self.service.reconcile()
        self.assertEqual(second.actions, ())
        self.assertEqual(len(self.audit.recent()), 1)

    def test_10_ledger_deleted_mid_life_does_nothing(self) -> None:
        slug = self.create()
        self.mutations.enable(slug, "claude")
        h_claude = self.clobber(slug, "claude", "edit\n")
        self.ledger_path.unlink()

        outcome = self.service.reconcile()
        self.assertEqual(outcome.actions, ())
        self.assertFalse(h_claude.is_symlink())
        self.assertEqual(h_claude.read_text(encoding="utf-8"), "edit\n")

    def test_11_adopt_corrupted_store_write_refuses(self) -> None:
        slug = self.create()
        self.mutations.enable(slug, "claude")
        h_claude = self.clobber(slug, "claude", "edit\n")

        def corrupt_write_raw(s: str, doc: str) -> None:
            self.store.agents_root.mkdir(parents=True, exist_ok=True)
            self.store.path_for(s).write_text("corrupted content\n", encoding="utf-8")

        with patch.object(self.store, "write_raw", side_effect=corrupt_write_raw):
            outcome = self.service.reconcile()

        self.assertFalse(h_claude.is_symlink())
        self.assertEqual(h_claude.read_text(encoding="utf-8"), "edit\n")
        self.assertEqual(len(outcome.actions), 1)
        self.assertEqual(outcome.actions[0].action, "refused")

    def test_12_audit_log_degrades_corrupt_file(self) -> None:
        self.audit_path.write_text("corrupt json{{{", encoding="utf-8")
        self.assertEqual(self.audit.recent(), ())

        self.audit.append(
            [
                AuditEntry(
                    at=1.0,
                    ref="a",
                    harness="claude",
                    action="relinked",
                    detail="restored link",
                )
            ]
        )
        recent = self.audit.recent()
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0].detail, "restored link")

    def test_sequential_reconcile_completes_without_deadlock(self) -> None:
        slug = self.create()
        self.mutations.enable(slug, "claude")
        self.clobber(slug, "claude", "edit\n")

        self.service.reconcile()
        self.service.reconcile()


if __name__ == "__main__":
    unittest.main()
