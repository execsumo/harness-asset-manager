from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from skill_manager.application.agents import (
    AgentAdoptConflict,
    AgentHarnessAdapter,
    AgentInventoryService,
    AgentMutationService,
    AgentParseError,
    AgentStore,
    AgentTarget,
    parse_agent_document,
    render_agent_document,
)
from skill_manager.errors import MutationError

AGENT_DOC = """---
name: Chief of Staff
description: Orchestrates tasks and delegates work.
tools: Read, Bash
---
You are the Chief of Staff. Delegate; do not code.
"""

# The retired compile model wrote these keys. Files on disk still carry them.
LEGACY_AGENT_DOC = """---
name: Legacy Agent
description: Written by the old compile model.
capabilities:
  skills:
    - project-context
  mcps:
    - github-mcp
  tools:
    allowed:
      - read_file
    denied:
      - execute_sql
harnesses:
  claude:
    model: claude-sonnet-5
---
Legacy prompt body.
"""


def _write(path: Path, document: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document, encoding="utf-8")
    return path


class AgentParserTests(unittest.TestCase):
    def test_parses_name_description_prompt_and_tools(self) -> None:
        agent = parse_agent_document(AGENT_DOC, slug="chief", path=Path("chief.md"))
        self.assertEqual(agent.name, "Chief of Staff")
        self.assertEqual(agent.description, "Orchestrates tasks and delegates work.")
        self.assertEqual(agent.tools, ("Read", "Bash"))
        self.assertEqual(agent.prompt, "You are the Chief of Staff. Delegate; do not code.")

    def test_legacy_capability_keys_are_ignored_not_fatal(self) -> None:
        agent = parse_agent_document(LEGACY_AGENT_DOC, slug="legacy", path=Path("legacy.md"))
        self.assertEqual(agent.name, "Legacy Agent")
        self.assertEqual(agent.tools, ())
        self.assertEqual(agent.prompt, "Legacy prompt body.")

    def test_tools_accepts_a_yaml_list(self) -> None:
        document = "---\nname: L\ndescription: d\ntools:\n  - Read\n  - Edit\n---\nbody\n"
        agent = parse_agent_document(document, slug="l", path=Path("l.md"))
        self.assertEqual(agent.tools, ("Read", "Edit"))

    def test_missing_frontmatter_is_an_error(self) -> None:
        with self.assertRaises(AgentParseError):
            parse_agent_document("no frontmatter here", slug="x", path=Path("x.md"))

    def test_unterminated_frontmatter_is_an_error(self) -> None:
        with self.assertRaises(AgentParseError):
            parse_agent_document("---\nname: X\nbody", slug="x", path=Path("x.md"))

    def test_render_drops_legacy_keys(self) -> None:
        agent = parse_agent_document(LEGACY_AGENT_DOC, slug="legacy", path=Path("legacy.md"))
        rendered = render_agent_document(
            name=agent.name,
            description=agent.description,
            prompt=agent.prompt,
            tools=agent.tools,
        )
        self.assertNotIn("capabilities", rendered)
        self.assertNotIn("harnesses", rendered)
        self.assertIn("name: Legacy Agent", rendered)


class AgentsFixture(unittest.TestCase):
    """Store + a single 'claude' harness target wired to a temp directory."""

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
            docs_url="",
            installed=True,
            enabled=True,
        )
        self.store = AgentStore(self.store_root)
        self.adapter = AgentHarnessAdapter(self.target, self.store_root)
        self.adapters = {"claude": self.adapter}
        self.inventory = AgentInventoryService(self.store, (self.target,), self.adapters)
        self.mutations = AgentMutationService(self.store, (self.target,), self.adapters)

    def entry(self, ref: str):
        return next(e for e in self.inventory.build().entries if e.ref == ref)


class AgentBindingTests(AgentsFixture):
    def test_enable_creates_a_symlink_into_the_store(self) -> None:
        agent = self.store.create(name="Red Team", description="probe", prompt="be adversarial")
        self.mutations.enable("red-team", "claude")
        link = self.harness_dir / "red-team.md"
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), agent.path.resolve())
        self.assertEqual(self.entry("red-team").bindings[0].state, "enabled")

    def test_disable_removes_the_symlink_but_keeps_the_store_file(self) -> None:
        self.store.create(name="Red Team", description="probe", prompt="p")
        self.mutations.enable("red-team", "claude")
        self.mutations.disable("red-team", "claude")
        self.assertFalse((self.harness_dir / "red-team.md").exists())
        self.assertTrue((self.store_root / "red-team.md").is_file())

    def test_disable_refuses_to_delete_a_real_file(self) -> None:
        self.store.create(name="Red Team", description="probe", prompt="p")
        _write(self.harness_dir / "red-team.md", "---\nname: theirs\ndescription: d\n---\nbody\n")
        with self.assertRaises(MutationError):
            self.mutations.disable("red-team", "claude")
        self.assertTrue((self.harness_dir / "red-team.md").is_file())

    def test_enable_refuses_to_overwrite_a_real_file(self) -> None:
        self.store.create(name="Red Team", description="probe", prompt="p")
        _write(self.harness_dir / "red-team.md", "---\nname: theirs\ndescription: d\n---\nbody\n")
        with self.assertRaises(MutationError):
            self.mutations.enable("red-team", "claude")

    def test_unknown_harness_is_rejected(self) -> None:
        self.store.create(name="Red Team", description="probe", prompt="p")
        with self.assertRaises(MutationError):
            self.mutations.enable("red-team", "cursor")

    def test_set_harnesses_enables_listed_and_disables_the_rest(self) -> None:
        self.store.create(name="Red Team", description="probe", prompt="p")
        self.mutations.enable("red-team", "claude")
        succeeded, failed = self.mutations.set_harnesses("red-team", [])
        self.assertEqual(failed, [])
        self.assertEqual(succeeded, ["claude"])
        self.assertFalse((self.harness_dir / "red-team.md").exists())

    def test_delete_removes_bindings_and_the_store_file(self) -> None:
        self.store.create(name="Red Team", description="probe", prompt="p")
        self.mutations.enable("red-team", "claude")
        self.mutations.delete("red-team")
        self.assertFalse((self.harness_dir / "red-team.md").exists())
        self.assertFalse((self.store_root / "red-team.md").exists())


class AgentInventoryTests(AgentsFixture):
    def test_real_harness_file_is_reported_unmanaged_and_adoptable(self) -> None:
        _write(self.harness_dir / "stray.md", "---\nname: Stray\ndescription: d\n---\nbody\n")
        entry = self.entry("claude/stray")
        self.assertEqual(entry.kind, "unmanaged")
        self.assertTrue(entry.can_adopt)
        self.assertEqual(entry.harness_path, self.harness_dir / "stray.md")

    def test_dangling_symlink_is_disabled_with_a_detail(self) -> None:
        # The store entry still exists, but the link points somewhere that is gone —
        # e.g. it was written against an older store path.
        self.store.create(name="Red Team", description="probe", prompt="p")
        link = self.harness_dir / "red-team.md"
        link.symlink_to(self.store_root / "moved-away.md")
        binding = self.entry("red-team").bindings[0]
        self.assertEqual(binding.state, "disabled")
        self.assertEqual(binding.detail, "symlink points at a missing file")

    def test_orphaned_link_is_reported_as_an_issue(self) -> None:
        # Store file deleted out from under us: the agent has no row left to hang a
        # binding off, so the dead link must surface as an issue rather than silently.
        agent = self.store.create(name="Red Team", description="probe", prompt="p")
        self.mutations.enable("red-team", "claude")
        agent.path.unlink()

        inventory = self.inventory.build()

        self.assertEqual([e.ref for e in inventory.entries], [])
        self.assertEqual([issue.name for issue in inventory.issues], ["claude/red-team"])
        self.assertIn("no longer in the store", inventory.issues[0].reason)

    def test_our_symlink_is_never_listed_as_unmanaged(self) -> None:
        self.store.create(name="Red Team", description="probe", prompt="p")
        self.mutations.enable("red-team", "claude")
        refs = [e.ref for e in self.inventory.build().entries]
        self.assertEqual(refs, ["red-team"])

    def test_unparseable_store_file_becomes_an_issue(self) -> None:
        _write(self.store_root / "broken.md", "not frontmatter")
        issues = self.inventory.build().issues
        self.assertEqual([issue.name for issue in issues], ["broken"])


class AgentAdoptTests(AgentsFixture):
    def test_adopt_moves_the_file_into_the_store_and_leaves_a_symlink(self) -> None:
        _write(self.harness_dir / "stray.md", "---\nname: Stray\ndescription: d\n---\nbody\n")
        self.assertEqual(self.mutations.adopt("claude/stray"), "stray")
        self.assertTrue((self.store_root / "stray.md").is_file())
        link = self.harness_dir / "stray.md"
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.resolve(), (self.store_root / "stray.md").resolve())

    def test_bare_adopt_on_a_collision_raises_and_mutates_nothing(self) -> None:
        self.store.create(name="Stray", description="ours", prompt="ours")
        store_before = (self.store_root / "stray.md").read_text(encoding="utf-8")
        harness_doc = "---\nname: Stray\ndescription: theirs\n---\ntheirs\n"
        _write(self.harness_dir / "stray.md", harness_doc)

        with self.assertRaises(AgentAdoptConflict) as caught:
            self.mutations.adopt("claude/stray")

        self.assertEqual(caught.exception.slug, "stray")
        self.assertEqual(caught.exception.store_path, self.store_root / "stray.md")
        self.assertEqual(caught.exception.harness_path, self.harness_dir / "stray.md")
        # Both sides untouched.
        self.assertEqual((self.store_root / "stray.md").read_text(encoding="utf-8"), store_before)
        self.assertEqual((self.harness_dir / "stray.md").read_text(encoding="utf-8"), harness_doc)
        self.assertFalse((self.harness_dir / "stray.md").is_symlink())

    def test_keep_store_discards_the_harness_file(self) -> None:
        self.store.create(name="Stray", description="ours", prompt="ours")
        store_before = (self.store_root / "stray.md").read_text(encoding="utf-8")
        _write(self.harness_dir / "stray.md", "---\nname: Stray\ndescription: theirs\n---\ntheirs\n")

        self.mutations.adopt("claude/stray", "keep_store")

        self.assertEqual((self.store_root / "stray.md").read_text(encoding="utf-8"), store_before)
        self.assertTrue((self.harness_dir / "stray.md").is_symlink())

    def test_replace_store_takes_the_harness_version(self) -> None:
        self.store.create(name="Stray", description="ours", prompt="ours")
        harness_doc = "---\nname: Stray\ndescription: theirs\n---\ntheirs\n"
        _write(self.harness_dir / "stray.md", harness_doc)

        self.mutations.adopt("claude/stray", "replace_store")

        self.assertEqual((self.store_root / "stray.md").read_text(encoding="utf-8"), harness_doc)
        self.assertTrue((self.harness_dir / "stray.md").is_symlink())

    def test_adopt_all_skips_conflicts_and_reports_them(self) -> None:
        self.store.create(name="Stray", description="ours", prompt="ours")
        _write(self.harness_dir / "stray.md", "---\nname: Stray\ndescription: theirs\n---\nt\n")
        _write(self.harness_dir / "fresh.md", "---\nname: Fresh\ndescription: d\n---\nbody\n")

        result = self.mutations.adopt_all()

        self.assertEqual(result.adopted, ("fresh",))
        self.assertEqual([ref for ref, _ in result.skipped], ["claude/stray"])
        self.assertFalse((self.harness_dir / "stray.md").is_symlink())

    def test_adopt_rejects_a_traversal_ref(self) -> None:
        with self.assertRaises(MutationError):
            self.mutations.adopt("claude/../../etc/passwd")

    def test_adopt_rejects_a_ref_without_a_harness(self) -> None:
        with self.assertRaises(MutationError):
            self.mutations.adopt("stray")


class AgentStoreTests(AgentsFixture):
    def test_create_slugifies_the_name(self) -> None:
        agent = self.store.create(name="Chief of Staff", description="d", prompt="p")
        self.assertEqual(agent.slug, "chief-of-staff")
        self.assertTrue((self.store_root / "chief-of-staff.md").is_file())

    def test_create_refuses_a_duplicate(self) -> None:
        self.store.create(name="Dup", description="d", prompt="p")
        with self.assertRaises(MutationError):
            self.store.create(name="Dup", description="d2", prompt="p2")

    def test_update_preserves_unspecified_fields(self) -> None:
        self.store.create(name="Keep", description="original", prompt="body")
        updated = self.store.update("keep", description="changed")
        self.assertEqual(updated.description, "changed")
        self.assertEqual(updated.prompt, "body")
        self.assertEqual(updated.name, "Keep")

    def test_path_for_rejects_traversal(self) -> None:
        with self.assertRaises(MutationError):
            self.store.path_for("../escape")


if __name__ == "__main__":
    unittest.main()
