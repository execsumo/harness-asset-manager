from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness_asset_manager.application.agents import (
    AgentBindingLedger,
    AgentBindingRecord,
    AgentHarnessAdapter,
    AgentInventoryService,
    AgentMutationService,
    AgentStore,
    AgentTarget,
    build_record,
    classify_drift,
)
from harness_asset_manager.hashing import hash_file, hash_text


class ClassifyDriftTests(unittest.TestCase):
    """The decision table of plan-auto-adoption.md §4, one test per row.

    Pure function, no filesystem: the classification is the part that must be
    reviewable on its own, because every automatic action will be gated on it.
    """

    def record(self, store_sha256: str | None) -> AgentBindingRecord:
        return AgentBindingRecord(
            harness="claude",
            target=Path("/store/agents/a.md"),
            linked_at=0.0,
            store_sha256=store_sha256,
        )

    def test_row_1_no_record_is_a_collision(self) -> None:
        self.assertEqual(
            classify_drift(record=None, harness_sha256="sha256:a", store_sha256="sha256:b"),
            "collision",
        )

    def test_row_2_identical_content_is_a_clean_clobber(self) -> None:
        self.assertEqual(
            classify_drift(
                record=self.record("sha256:old"),
                harness_sha256="sha256:same",
                store_sha256="sha256:same",
            ),
            "clobber_clean",
        )

    def test_row_3_store_untouched_since_link_is_one_sided(self) -> None:
        self.assertEqual(
            classify_drift(
                record=self.record("sha256:linked"),
                harness_sha256="sha256:edited",
                store_sha256="sha256:linked",
            ),
            "clobber_one_sided",
        )

    def test_row_4_both_sides_moved_is_a_two_sided_conflict(self) -> None:
        self.assertEqual(
            classify_drift(
                record=self.record("sha256:linked"),
                harness_sha256="sha256:edited",
                store_sha256="sha256:also-edited",
            ),
            "two_sided_conflict",
        )

    def test_record_without_a_baseline_degrades_to_collision(self) -> None:
        """A record we cannot measure against proves nothing, so it must claim nothing."""
        self.assertEqual(
            classify_drift(
                record=self.record(None),
                harness_sha256="sha256:a",
                store_sha256="sha256:b",
            ),
            "collision",
        )

    def test_unreadable_side_degrades_to_collision(self) -> None:
        self.assertEqual(
            classify_drift(
                record=self.record("sha256:linked"),
                harness_sha256=None,
                store_sha256="sha256:linked",
            ),
            "collision",
        )


class LedgerStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        self.path = self.root / "bindings.json"
        self.ledger = AgentBindingLedger(self.path)

    def record(self, harness: str = "claude") -> AgentBindingRecord:
        return AgentBindingRecord(
            harness=harness,
            target=self.root / "agents" / "a.md",
            linked_at=1.0,
            store_sha256="sha256:x",
        )

    def test_upsert_then_read_back(self) -> None:
        self.ledger.upsert("a", self.record())
        found = self.ledger.record_for("a", "claude")
        assert found is not None
        self.assertEqual(found.store_sha256, "sha256:x")
        self.assertEqual(found.target, self.root / "agents" / "a.md")

    def test_forget_drops_the_slug_when_its_last_harness_goes(self) -> None:
        self.ledger.upsert("a", self.record())
        self.ledger.upsert("a", self.record("cursor"))
        self.ledger.forget("a", "claude")
        self.assertIsNone(self.ledger.record_for("a", "claude"))
        self.assertIsNotNone(self.ledger.record_for("a", "cursor"))
        self.ledger.forget("a", "cursor")
        self.assertEqual(self.ledger.load(), {})

    def test_missing_ledger_reads_as_empty(self) -> None:
        self.assertEqual(AgentBindingLedger(self.root / "nope.json").load(), {})

    def test_truncated_ledger_reads_as_empty(self) -> None:
        self.ledger.upsert("a", self.record())
        self.path.write_text('{"version": 1, "agents": {"a"', encoding="utf-8")
        self.assertEqual(self.ledger.load(), {})

    def test_corrupt_records_are_dropped_not_raised(self) -> None:
        """A malformed record must read as 'no record', which is row 1: prompt the user."""
        self.path.write_text(
            json.dumps(
                {
                    "version": 1,
                    "agents": {
                        "a": {
                            "claude": {"target": 12, "linkedAt": 1.0},
                            "cursor": {"target": "/store/a.md"},
                            "opencode": {
                                "target": "/store/a.md",
                                "linkedAt": 2.0,
                                "storeSha256": "sha256:ok",
                            },
                        },
                        "b": "not-a-mapping",
                    },
                }
            ),
            encoding="utf-8",
        )
        state = self.ledger.load()
        self.assertEqual(list(state), ["a"])
        self.assertEqual(list(state["a"]), ["opencode"])

    def test_wrong_shape_at_the_top_level_reads_as_empty(self) -> None:
        self.path.write_text("[]", encoding="utf-8")
        self.assertEqual(self.ledger.load(), {})

    def test_rebaseline_only_touches_the_named_harnesses(self) -> None:
        self.ledger.upsert("a", self.record("claude"))
        self.ledger.upsert("a", self.record("cursor"))
        self.ledger.rebaseline("a", ("claude",), "sha256:new")
        claude = self.ledger.record_for("a", "claude")
        cursor = self.ledger.record_for("a", "cursor")
        assert claude is not None and cursor is not None
        self.assertEqual(claude.store_sha256, "sha256:new")
        self.assertEqual(cursor.store_sha256, "sha256:x")

    def test_rebaseline_preserves_link_time(self) -> None:
        self.ledger.upsert("a", self.record())
        self.ledger.rebaseline("a", ("claude",), "sha256:new")
        found = self.ledger.record_for("a", "claude")
        assert found is not None
        self.assertEqual(found.linked_at, 1.0)

    def test_build_record_hashes_the_store_file(self) -> None:
        store_path = self.root / "agents" / "a.md"
        store_path.parent.mkdir(parents=True)
        store_path.write_text("hello", encoding="utf-8")
        record = build_record(harness="claude", store_path=store_path)
        self.assertEqual(record.store_sha256, hash_text("hello"))
        self.assertIsNone(record.rendered_sha256)

    def test_build_record_survives_a_missing_store_file(self) -> None:
        record = build_record(harness="claude", store_path=self.root / "gone.md")
        self.assertIsNone(record.store_sha256)


class AgentLedgerFixture(unittest.TestCase):
    """Store + one symlinking 'claude' target, wired the way container.py wires them."""

    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.store_root = root / "data" / "agents"
        self.harness_dir = root / "home" / ".claude" / "agents"
        self.store_root.mkdir(parents=True)
        self.harness_dir.mkdir(parents=True)

        self.target = AgentTarget(
            id="claude",
            label="Claude",
            logo_key="claude",
            root_path=self.harness_dir.parent,
            output_dir=self.harness_dir,
            file_glob="*.md",
            render_format="markdown",
            docs_url="",
            installed=True,
        )
        self.adapter = AgentHarnessAdapter(self.target, self.store_root)
        snapshot = lambda: ((self.target,), {"claude": self.adapter})
        self.ledger = AgentBindingLedger(root / "data" / "bindings.json")
        # Mirrors container.py: only live symlinked bindings are re-baselined.
        def rebaseline(slug: str) -> None:
            store_path = self.store.path_for(slug)
            if not store_path.is_file():
                return
            live = tuple(h for h, a in {"claude": self.adapter}.items() if a.is_enabled(slug))
            self.ledger.rebaseline(slug, live, hash_file(store_path))

        self.store = AgentStore(self.store_root, rebaseline)
        self.inventory = AgentInventoryService(self.store, snapshot, self.ledger)
        self.mutations = AgentMutationService(self.store, snapshot, self.ledger)

    def create(self, name: str = "Auditor") -> str:
        return self.store.create(name=name, description="d", prompt="p").slug


class LedgerLifecycleTests(AgentLedgerFixture):
    """Stage 1: the ledger follows real binding mutations."""

    def test_enable_records_and_disable_forgets(self) -> None:
        slug = self.create()
        self.mutations.enable(slug, "claude")
        record = self.ledger.record_for(slug, "claude")
        assert record is not None
        self.assertEqual(record.target, self.store.path_for(slug))
        self.assertEqual(record.store_sha256, hash_file(self.store.path_for(slug)))

        self.mutations.disable(slug, "claude")
        self.assertIsNone(self.ledger.record_for(slug, "claude"))

    def test_delete_clears_every_record_for_the_slug(self) -> None:
        slug = self.create()
        self.mutations.enable(slug, "claude")
        # A harness the user has since disabled in Settings is not in `targets`, so it
        # is never asked to unbind — its record still has to go.
        self.ledger.upsert(
            slug,
            AgentBindingRecord(
                harness="hermes", target=self.store.path_for(slug), linked_at=1.0
            ),
        )
        self.mutations.delete(slug)
        self.assertEqual(self.ledger.load(), {})

    def test_set_harnesses_records_only_what_succeeded(self) -> None:
        slug = self.create()
        self.mutations.set_harnesses(slug, ["claude"])
        self.assertIsNotNone(self.ledger.record_for(slug, "claude"))
        self.mutations.set_harnesses(slug, [])
        self.assertIsNone(self.ledger.record_for(slug, "claude"))

    def test_adopt_records_the_binding_it_creates(self) -> None:
        (self.harness_dir / "local.md").write_text(
            "---\nname: Local\ndescription: d\n---\nbody\n", encoding="utf-8"
        )
        self.mutations.adopt("claude/local")
        self.assertIsNotNone(self.ledger.record_for("local", "claude"))

    def test_store_edit_rebaselines_a_live_binding(self) -> None:
        slug = self.create()
        self.mutations.enable(slug, "claude")
        self.store.update(slug, prompt="rewritten")
        record = self.ledger.record_for(slug, "claude")
        assert record is not None
        self.assertEqual(record.store_sha256, hash_file(self.store.path_for(slug)))

    def test_store_edit_does_not_rebaseline_a_clobbered_binding(self) -> None:
        """The load-bearing safety rule: re-baselining a broken binding would turn a
        genuine two-sided conflict into an automatic adopt that discards this edit."""
        slug = self.create()
        self.mutations.enable(slug, "claude")
        linked_hash = hash_file(self.store.path_for(slug))

        binding = self.adapter.binding_path(slug)
        binding.unlink()
        binding.write_text("---\nname: Auditor\ndescription: d\n---\nharness edit\n", "utf-8")

        self.store.update(slug, prompt="store edit")
        record = self.ledger.record_for(slug, "claude")
        assert record is not None
        self.assertEqual(record.store_sha256, linked_hash)
        self.assertEqual(
            classify_drift(
                record=record,
                harness_sha256=hash_file(binding),
                store_sha256=hash_file(self.store.path_for(slug)),
            ),
            "two_sided_conflict",
        )


class ClobberDiagnosisTests(AgentLedgerFixture):
    """Stage 2: the inventory names the drift. It still takes no action."""

    def clobber(self, slug: str, body: str) -> Path:
        binding = self.adapter.binding_path(slug)
        binding.unlink()
        binding.write_text(body, encoding="utf-8")
        return binding

    def build(self, slug: str):
        inventory = self.inventory.build()
        entry = next(e for e in inventory.entries if e.ref == slug)
        return inventory, entry

    def test_clean_clobber_is_named_and_raised_as_an_issue(self) -> None:
        slug = self.create()
        self.mutations.enable(slug, "claude")
        contents = self.store.path_for(slug).read_text(encoding="utf-8")
        self.clobber(slug, contents)

        inventory, entry = self.build(slug)
        self.assertEqual(entry.bindings[0].state, "disabled")
        self.assertEqual(entry.bindings[0].detail, "the link was replaced by an identical file")
        self.assertIn("nothing is lost", " ".join(i.reason for i in inventory.issues))

    def test_one_sided_clobber_is_named(self) -> None:
        slug = self.create()
        self.mutations.enable(slug, "claude")
        self.clobber(slug, "---\nname: Auditor\ndescription: d\n---\nharness edit\n")

        inventory, entry = self.build(slug)
        self.assertEqual(entry.bindings[0].detail, "the link was replaced by an edited file")
        self.assertIn("only edit", " ".join(i.reason for i in inventory.issues))

    def test_two_sided_conflict_is_named_and_never_resolved(self) -> None:
        slug = self.create()
        self.mutations.enable(slug, "claude")
        binding = self.clobber(slug, "---\nname: Auditor\ndescription: d\n---\nharness edit\n")
        self.store.update(slug, prompt="store edit")

        inventory, entry = self.build(slug)
        self.assertEqual(
            entry.bindings[0].detail, "the link was replaced and both copies have changed"
        )
        self.assertIn("Both sides hold edits", " ".join(i.reason for i in inventory.issues))
        # Read-only: neither copy was touched.
        self.assertIn("harness edit", binding.read_text(encoding="utf-8"))
        self.assertIn("store edit", self.store.path_for(slug).read_text(encoding="utf-8"))

    def test_without_a_ledger_record_the_wording_is_unchanged(self) -> None:
        """Invariant 4: a lost ledger degrades to exactly the pre-ledger behaviour."""
        slug = self.create()
        self.mutations.enable(slug, "claude")
        self.clobber(slug, "---\nname: Auditor\ndescription: d\n---\nharness edit\n")
        self.ledger.path.unlink()

        inventory, entry = self.build(slug)
        self.assertEqual(
            entry.bindings[0].detail, "a file we do not manage occupies this name"
        )
        self.assertEqual(inventory.issues, ())

    def test_an_unrelated_file_at_the_binding_path_is_not_called_a_clobber(self) -> None:
        slug = self.create()
        (self.harness_dir / f"{slug}.md").write_text("someone else's agent\n", encoding="utf-8")
        _inventory, entry = self.build(slug)
        self.assertEqual(
            entry.bindings[0].detail, "a file we do not manage occupies this name"
        )

    def test_diagnosis_is_idempotent(self) -> None:
        slug = self.create()
        self.mutations.enable(slug, "claude")
        self.clobber(slug, "---\nname: Auditor\ndescription: d\n---\nharness edit\n")
        first = self.inventory.build()
        second = self.inventory.build()
        self.assertEqual(
            [i.reason for i in first.issues], [i.reason for i in second.issues]
        )
        self.assertEqual(self.ledger.load().keys(), {slug})

    def test_detail_view_reports_the_same_diagnosis(self) -> None:
        slug = self.create()
        self.mutations.enable(slug, "claude")
        self.clobber(slug, "---\nname: Auditor\ndescription: d\n---\nharness edit\n")
        detail = self.inventory.detail(slug)
        assert detail is not None
        self.assertEqual(detail.harnesses[0].detail, "the link was replaced by an edited file")


class RenderedDriftTests(unittest.TestCase):
    """Codex is rendered, not linked: detection only, never automatic adoption."""

    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.store_root = root / "data" / "agents"
        self.harness_dir = root / "home" / ".codex" / "agents"
        self.store_root.mkdir(parents=True)
        self.harness_dir.mkdir(parents=True)
        self.target = AgentTarget(
            id="codex",
            label="Codex",
            logo_key="codex",
            root_path=self.harness_dir.parent,
            output_dir=self.harness_dir,
            file_glob="*.toml",
            render_format="codex_toml",
            docs_url="",
            installed=True,
        )
        self.adapter = AgentHarnessAdapter(self.target, self.store_root)
        snapshot = lambda: ((self.target,), {"codex": self.adapter})
        self.ledger = AgentBindingLedger(root / "data" / "bindings.json")
        self.store = AgentStore(self.store_root)
        self.inventory = AgentInventoryService(self.store, snapshot, self.ledger)
        self.mutations = AgentMutationService(self.store, snapshot, self.ledger)

    def test_enable_records_the_rendered_hash(self) -> None:
        self.store.create(name="Auditor", description="d", prompt="p")
        self.mutations.enable("auditor", "codex")
        record = self.ledger.record_for("auditor", "codex")
        assert record is not None
        self.assertEqual(
            record.rendered_sha256, hash_file(self.harness_dir / "auditor.toml")
        )
        self.assertIsNotNone(record.rendered_size)

    def test_a_locally_edited_rendered_file_is_reported_but_left_alone(self) -> None:
        self.store.create(name="Auditor", description="d", prompt="p")
        self.mutations.enable("auditor", "codex")
        rendered = self.harness_dir / "auditor.toml"
        rendered.write_text(
            rendered.read_text(encoding="utf-8") + '\nextra = "mine"\n', encoding="utf-8"
        )

        inventory = self.inventory.build()
        entry = next(e for e in inventory.entries if e.ref == "auditor")
        # Still owned, still enabled — the file is ours, it has just been edited.
        self.assertEqual(entry.bindings[0].state, "enabled")
        self.assertIn("re-enabling this agent overwrites", " ".join(i.reason for i in inventory.issues))
        self.assertIn('extra = "mine"', rendered.read_text(encoding="utf-8"))

    def test_an_untouched_rendered_file_raises_nothing(self) -> None:
        self.store.create(name="Auditor", description="d", prompt="p")
        self.mutations.enable("auditor", "codex")
        self.assertEqual(self.inventory.build().issues, ())


if __name__ == "__main__":
    unittest.main()
