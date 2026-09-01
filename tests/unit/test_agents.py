from __future__ import annotations

import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from harness_asset_manager.api.routers.agents import create_agent
from harness_asset_manager.api.schemas.agents import CreateAgentRequest
from harness_asset_manager.application import build_backend_container
from harness_asset_manager.application.agents import (
    AgentAdoptConflict,
    AgentBindingLedger,
    AgentHarnessAdapter,
    AgentInventoryService,
    AgentMutationService,
    AgentParseError,
    AgentStore,
    AgentTarget,
    parse_agent_document,
    render_agent_document,
)
from harness_asset_manager.application.agents.model import (
    ALLOWED_SUBAGENTS_VALUES,
    COLOR_VALUES,
    CONTRACT_KEYS,
    EFFORT_VALUES,
    ISOLATION_VALUES,
    MAX_TURNS_DEFAULT,
    validate_allowed_subagents,
    validate_color,
    validate_effort,
    validate_isolation,
    validate_max_turns,
)
from harness_asset_manager.errors import MutationError
from tests.support.app_harness import AppTestHarness
from tests.support.fake_home import create_fake_home_spec

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
    def test_skills_accepts_a_yaml_list(self) -> None:
        document = "---\nname: L\ndescription: d\nskills:\n  - code-review\n  - test-debugging\n---\nbody\n"
        agent = parse_agent_document(document, slug="l", path=Path("l.md"))
        self.assertEqual(agent.skills, ("code-review", "test-debugging"))

    def test_skills_accepts_an_inline_list(self) -> None:
        document = "---\nname: L\ndescription: d\nskills: [code-review, test-debugging]\n---\nbody\n"
        agent = parse_agent_document(document, slug="l", path=Path("l.md"))
        self.assertEqual(agent.skills, ("code-review", "test-debugging"))

    def test_skills_accepts_a_comma_separated_string(self) -> None:
        document = "---\nname: L\ndescription: d\nskills: code-review, test-debugging\n---\nbody\n"
        agent = parse_agent_document(document, slug="l", path=Path("l.md"))
        self.assertEqual(agent.skills, ("code-review", "test-debugging"))

    def test_skills_dedupes_and_preserves_order(self) -> None:
        document = "---\nname: L\ndescription: d\nskills: [code-review, code-review, test-debugging]\n---\nbody\n"
        agent = parse_agent_document(document, slug="l", path=Path("l.md"))
        self.assertEqual(agent.skills, ("code-review", "test-debugging"))

    def test_render_agent_document_renders_skills_as_yaml_list(self) -> None:
        doc = render_agent_document(
            name="Skills Agent",
            description="Agent with skills",
            prompt="Prompt body",
            tools=("Read",),
            skills=("code-review", "frontend-debugging"),
        )
        self.assertIn("skills:\n  - code-review\n  - frontend-debugging", doc)
        parsed = parse_agent_document(doc, slug="skills-agent", path=Path("skills-agent.md"))
        self.assertEqual(parsed.skills, ("code-review", "frontend-debugging"))

    def test_missing_frontmatter_is_an_error(self) -> None:
        with self.assertRaises(AgentParseError):
            parse_agent_document("no frontmatter here", slug="x", path=Path("x.md"))

    def test_unterminated_frontmatter_is_an_error(self) -> None:
        with self.assertRaises(AgentParseError):
            parse_agent_document("---\nname: X\nbody", slug="x", path=Path("x.md"))

    def test_unknown_frontmatter_survives_an_edit(self) -> None:
        """The keys a harness owns must never be collateral damage of an edit.

        Real Claude agents carry model / permissionMode / maxTurns / hooks and more.
        Re-rendering from just name+description+tools deleted all of it.
        """
        document = (
            "---\n"
            "name: Bookman\n"
            "description: Vault librarian.\n"
            "model: sonnet\n"
            "tools: Read, Grep\n"
            'permissionMode: "acceptEdits"\n'
            "maxTurns: 50\n"
            "disallowedTools: []\n"
            "hooks:\n"
            "  PreToolUse:\n"
            "    - matcher: Bash\n"
            "---\n\nIndex the vault.\n"
        )
        agent = parse_agent_document(document, slug="bookman", path=Path("bookman.md"))

        rewritten = render_agent_document(
            name=agent.name,
            description="Vault librarian, updated.",
            prompt=agent.prompt,
            tools=agent.tools,
            base_metadata=agent.metadata,
        )

        reparsed = parse_agent_document(rewritten, slug="bookman", path=Path("bookman.md"))
        self.assertEqual(reparsed.description, "Vault librarian, updated.")
        self.assertEqual(reparsed.name, "Bookman")
        self.assertEqual(reparsed.prompt, "Index the vault.")
        self.assertEqual(
            [key for key, _ in reparsed.extra_metadata],
            ["permissionMode", "maxTurns", "disallowedTools", "hooks"],
        )
        self.assertEqual(reparsed.metadata["model"], "sonnet")
        self.assertEqual(reparsed.metadata["maxTurns"], 50)
        self.assertEqual(reparsed.metadata["permissionMode"], "acceptEdits")
        self.assertEqual(reparsed.metadata["hooks"], {"PreToolUse": [{"matcher": "Bash"}]})

    def test_empty_string_values_round_trip_as_empty_strings(self) -> None:
        """`effort: ""` must not silently become null on the way back out."""
        document = '---\nname: A\ndescription: d\neffort: ""\n---\n\nbody\n'
        agent = parse_agent_document(document, slug="a", path=Path("a.md"))
        self.assertEqual(agent.metadata["effort"], "")

        rewritten = render_agent_document(
            name=agent.name,
            description=agent.description,
            prompt=agent.prompt,
            tools=agent.tools,
            base_metadata=agent.metadata,
        )
        self.assertIn('effort: ""', rewritten)
        self.assertEqual(
            parse_agent_document(rewritten, slug="a", path=Path("a.md")).metadata["effort"], ""
        )

    def test_extra_metadata_excludes_the_fields_shown_on_their_own(self) -> None:
        agent = parse_agent_document(AGENT_DOC, slug="chief", path=Path("chief.md"))
        keys = [key for key, _ in agent.extra_metadata]
        self.assertNotIn("name", keys)
        self.assertNotIn("description", keys)
        self.assertNotIn("tools", keys)
        self.assertNotIn("model", keys)
        self.assertNotIn("skills", keys)
        self.assertNotIn("effort", keys)

    def test_model_and_effort_are_contract_fields(self) -> None:
        """`model` and `effort` parse into their own fields and render canonically."""
        document = (
            "---\n"
            "name: A\n"
            "description: d\n"
            "customKey: v\n"
            "---\n\nbody\n"
        )
        rendered = render_agent_document(
            name="A",
            description="d",
            prompt="body",
            tools=("Read",),
            skills=("code-review",),
            model="sonnet",
            effort="high",
            base_metadata=parse_agent_document(document, slug="a", path=Path("a.md")).metadata,
        )
        self.assertIn("name: A\ndescription: d\nmodel: sonnet\neffort: high\ntools: Read\nskills:\n  - code-review", rendered)
        reparsed = parse_agent_document(rendered, slug="a", path=Path("a.md"))
        self.assertEqual(reparsed.model, "sonnet")
        self.assertEqual(reparsed.effort, "high")

    def test_render_without_model_or_effort_arguments_leaves_them_untouched(self) -> None:
        """A direct render that omits the kwargs must never drop existing keys."""
        document = '---\nname: A\ndescription: d\nmodel: sonnet\neffort: ""\n---\n\nbody\n'
        agent = parse_agent_document(document, slug="a", path=Path("a.md"))
        rendered = render_agent_document(
            name=agent.name,
            description=agent.description,
            prompt=agent.prompt,
            tools=agent.tools,
            base_metadata=agent.metadata,
        )
        self.assertIn("model: sonnet", rendered)
        self.assertIn('effort: ""', rendered)

    def test_explicit_empty_model_clears_the_key(self) -> None:
        """An explicit empty-string edit removes the key instead of writing null."""
        document = "---\nname: A\ndescription: d\nmodel: sonnet\n---\n\nbody\n"
        agent = parse_agent_document(document, slug="a", path=Path("a.md"))
        rendered = render_agent_document(
            name=agent.name,
            description=agent.description,
            prompt=agent.prompt,
            tools=agent.tools,
            model="",
            base_metadata=agent.metadata,
        )
        self.assertNotIn("model", rendered)

    def test_render_drops_legacy_keys(self) -> None:
        """Our own retired compile keys are the one thing still dropped on write."""
        agent = parse_agent_document(LEGACY_AGENT_DOC, slug="legacy", path=Path("legacy.md"))
        rendered = render_agent_document(
            name=agent.name,
            description=agent.description,
            prompt=agent.prompt,
            tools=agent.tools,
            base_metadata=agent.metadata,
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
            render_format="markdown",
            docs_url="",
            installed=True,
        )
        self.store = AgentStore(self.store_root)
        self.adapter = AgentHarnessAdapter(self.target, self.store_root)
        self.adapters = {"claude": self.adapter}
        snapshot = lambda: ((self.target,), self.adapters)
        self.ledger = AgentBindingLedger(root / "data" / "bindings.json", home=root)
        self.inventory = AgentInventoryService(self.store, snapshot, self.ledger)
        self.mutations = AgentMutationService(self.store, snapshot, self.ledger)

    def entry(self, ref: str):
        return next(e for e in self.inventory.build().entries if e.ref == ref)


class CodexAgentTests(unittest.TestCase):
    """Codex reads TOML, not markdown, so it is rendered and marker-owned."""

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
        self.store = AgentStore(self.store_root)
        self.adapter = AgentHarnessAdapter(self.target, self.store_root)
        adapters = {"codex": self.adapter}
        snapshot = lambda: ((self.target,), adapters)
        self.ledger = AgentBindingLedger(root / "data" / "bindings.json", home=root)
        self.inventory = AgentInventoryService(self.store, snapshot, self.ledger)
        self.mutations = AgentMutationService(self.store, snapshot, self.ledger)

    def test_enable_renders_toml_with_underscored_name(self) -> None:
        self.store.create(name="PR Reviewer", description="reviews", prompt="Be strict.")
        self.mutations.enable("pr-reviewer", "codex")

        rendered = self.harness_dir / "pr-reviewer.toml"
        self.assertTrue(rendered.is_file())
        self.assertFalse(rendered.is_symlink())

        import tomllib

        data = tomllib.loads(rendered.read_text(encoding="utf-8"))
        # Codex resolves by `name`, not filename; their example pairs a hyphenated
        # file with an underscored name.
        self.assertEqual(data["name"], "pr_reviewer")
        self.assertEqual(data["description"], "reviews")
        self.assertEqual(data["developer_instructions"].strip(), "Be strict.")

    def test_rendered_file_is_owned_not_reported_unmanaged(self) -> None:
        self.store.create(name="PR Reviewer", description="d", prompt="p")
        self.mutations.enable("pr-reviewer", "codex")

        inventory = self.inventory.build()
        self.assertEqual([e.ref for e in inventory.entries], ["pr-reviewer"])

    def test_codex_adoption_preserves_unknown_toml_fields_without_markdown_leakage(self) -> None:
        unmanaged = self.harness_dir / "auditor.toml"
        unmanaged.write_text(
            'name = "auditor"\n'
            'description = "audits things"\n'
            'developer_instructions = "Check everything."\n'
            'sandbox_mode = "workspace-write"\n'
            '[model_settings]\n'
            'reasoning_effort = "high"\n'
            'enabled = false\n',
            encoding="utf-8",
        )

        self.mutations.adopt("codex/auditor")

        stored = self.store.get("auditor")
        assert stored is not None
        self.assertEqual(
            stored.codex_extras,
            {
                "sandbox_mode": "workspace-write",
                "model_settings": {"reasoning_effort": "high", "enabled": False},
            },
        )
        self.assertNotIn("sandbox_mode", stored.path.read_text(encoding="utf-8"))

        import tomllib

        rendered = tomllib.loads((self.harness_dir / "auditor.toml").read_text(encoding="utf-8"))
        self.assertEqual(rendered["sandbox_mode"], "workspace-write")
        self.assertEqual(rendered["model_settings"]["enabled"], False)

    def test_codex_unknown_fields_survive_a_store_edit(self) -> None:
        unmanaged = self.harness_dir / "auditor.toml"
        unmanaged.write_text(
            'name = "auditor"\n'
            'description = "audits things"\n'
            'developer_instructions = "Check everything."\n'
            'sandbox_mode = "workspace-write"\n',
            encoding="utf-8",
        )
        self.mutations.adopt("codex/auditor")
        self.store.update("auditor", description="updated")
        self.mutations.enable("auditor", "codex")

        import tomllib

        rendered = tomllib.loads((self.harness_dir / "auditor.toml").read_text(encoding="utf-8"))
        self.assertEqual(rendered["description"], "updated")
        self.assertEqual(rendered["sandbox_mode"], "workspace-write")

    def test_disable_removes_only_generated_files(self) -> None:
        self.store.create(name="PR Reviewer", description="d", prompt="p")
        self.mutations.enable("pr-reviewer", "codex")
        self.mutations.disable("pr-reviewer", "codex")
        self.assertFalse((self.harness_dir / "pr-reviewer.toml").exists())

        hand_written = self.harness_dir / "pr-reviewer.toml"
        hand_written.write_text('name = "pr_reviewer"\n', encoding="utf-8")
        with self.assertRaises(MutationError):
            self.mutations.disable("pr-reviewer", "codex")
        self.assertTrue(hand_written.is_file())

    def test_update_unmanaged_refuses_rendered_adapter(self) -> None:
        unmanaged = self.harness_dir / "auditor.toml"
        content = 'name = "auditor"\ndescription = "d"\n'
        unmanaged.write_text(content, encoding="utf-8")

        with self.assertRaises(MutationError) as ctx:
            self.mutations.update_unmanaged("codex/auditor", name="Auditor", description="new d")
        self.assertIn("adopt it before editing", str(ctx.exception))
        self.assertEqual(unmanaged.read_text(encoding="utf-8"), content)

    def test_enable_refuses_to_overwrite_a_hand_written_file(self) -> None:
        self.store.create(name="PR Reviewer", description="d", prompt="p")
        (self.harness_dir / "pr-reviewer.toml").write_text(
            'name = "mine"\n', encoding="utf-8"
        )
        with self.assertRaises(MutationError):
            self.mutations.enable("pr-reviewer", "codex")

    def test_hand_written_toml_is_unmanaged_and_adopts_into_markdown(self) -> None:
        (self.harness_dir / "auditor.toml").write_text(
            'name = "auditor"\n'
            'description = "audits things"\n'
            'developer_instructions = """\nCheck everything.\n"""\n',
            encoding="utf-8",
        )

        entry = next(
            e for e in self.inventory.build().entries if e.ref == "codex/auditor"
        )
        self.assertEqual(entry.kind, "unmanaged")
        self.assertEqual(entry.name, "auditor")
        self.assertEqual(entry.description, "audits things")

        self.mutations.adopt("codex/auditor")

        # The store always holds markdown, whatever the harness format was.
        stored = (self.store_root / "auditor.md").read_text(encoding="utf-8")
        self.assertTrue(stored.startswith("---"))
        self.assertIn("name: auditor", stored)
        self.assertIn("Check everything.", stored)
        # And the harness gets a freshly rendered, owned TOML back.
        self.assertTrue((self.harness_dir / "auditor.toml").is_file())
        self.assertEqual(
            [e.ref for e in self.inventory.build().entries], ["auditor"]
        )

    def test_unparseable_toml_becomes_an_issue(self) -> None:
        (self.harness_dir / "broken.toml").write_text("not = = toml", encoding="utf-8")
        issues = self.inventory.build().issues
        self.assertEqual([i.name for i in issues], ["codex/broken"])


class HermesBestEffortHarnessTests(unittest.TestCase):
    """HAM can manage Hermes agent files for separate Hermes-side support."""

    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)
        self.store_root = root / "data" / "agents"
        self.store_root.mkdir(parents=True)

        self.target = AgentTarget(
            id="hermes",
            label="Hermes Agent",
            logo_key="hermes",
            root_path=root / "home" / ".hermes",
            output_dir=root / "home" / ".hermes" / "agents",
            file_glob="*.md",
            render_format="markdown",
            docs_url="",
            installed=True,
        )
        self.store = AgentStore(self.store_root)
        adapters = {"hermes": AgentHarnessAdapter(self.target, self.store_root)}
        snapshot = lambda: ((self.target,), adapters)
        self.ledger = AgentBindingLedger(root / "data" / "bindings.json", home=root)
        self.inventory = AgentInventoryService(self.store, snapshot, self.ledger)
        self.mutations = AgentMutationService(self.store, snapshot, self.ledger)

    def test_enabling_creates_a_symlink_into_the_store(self) -> None:
        self.store.create(name="Red Team", description="d", prompt="p")
        self.mutations.enable("red-team", "hermes")
        link = self.target.output_dir / "red-team.md"
        self.assertTrue(link.is_symlink())
        self.assertEqual(self.inventory.build().entries[0].bindings[0].state, "enabled")

    def test_adopting_an_unmanaged_file_works(self) -> None:
        _write(
            self.target.output_dir / "red-team.md",
            "---\nname: Red Team\ndescription: d\n---\np\n",
        )
        entry = self.inventory.build().entries[0]
        self.assertEqual(entry.kind, "unmanaged")
        self.assertTrue(entry.can_adopt)
        self.mutations.adopt("hermes/red-team")
        self.assertTrue((self.store_root / "red-team.md").is_file())
        self.assertTrue((self.target.output_dir / "red-team.md").is_symlink())


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


class AgentUnmanagedEditTests(AgentsFixture):
    def test_update_unmanaged_rewrites_file_in_place_with_custom_metadata(self) -> None:
        doc = (
            "---\n"
            "name: Stray\n"
            "description: found in claude\n"
            "model: claude-3-5-sonnet\n"
            "tools: Read, Grep\n"
            "customKey: customVal\n"
            "---\n"
            "harness prompt body\n"
        )
        _write(self.harness_dir / "stray.md", doc)

        self.mutations.update_unmanaged(
            "claude/stray",
            name="Stray Renamed",
            description="updated desc",
            prompt="new prompt body",
            tools=("Read", "Bash"),
            model="claude-3-7-sonnet",
            metadata=[
                ("permissionMode", "acceptEdits"),
                ("customKey", "newVal"),
                ("extraKey", "extraVal"),
            ],
        )

        harness_file = self.harness_dir / "stray.md"
        self.assertTrue(harness_file.is_file())
        self.assertFalse(harness_file.is_symlink())
        self.assertFalse((self.store_root / "stray.md").exists())

        parsed = parse_agent_document(
            harness_file.read_text(encoding="utf-8"), slug="stray", path=harness_file
        )
        self.assertEqual(parsed.name, "Stray Renamed")
        self.assertEqual(parsed.description, "updated desc")
        self.assertEqual(parsed.prompt, "new prompt body")
        self.assertEqual(parsed.tools, ("Read", "Bash"))
        self.assertEqual(parsed.metadata.get("model"), "claude-3-7-sonnet")
        self.assertEqual(parsed.metadata.get("permissionMode"), "acceptEdits")
        self.assertEqual(parsed.metadata.get("customKey"), "newVal")
        self.assertEqual(parsed.metadata.get("extraKey"), "extraVal")

    def test_update_unmanaged_omitted_metadata_prompt_and_tools_preserves_existing(self) -> None:
        doc = (
            "---\n"
            "name: Stray\n"
            "description: found in claude\n"
            "model: claude-3-5-sonnet\n"
            "tools: Read, Grep\n"
            "customKey: customVal\n"
            "---\n"
            "original prompt body\n"
        )
        _write(self.harness_dir / "stray.md", doc)

        self.mutations.update_unmanaged(
            "claude/stray",
            name="Stray Updated",
            description="updated desc",
        )

        harness_file = self.harness_dir / "stray.md"
        parsed = parse_agent_document(
            harness_file.read_text(encoding="utf-8"), slug="stray", path=harness_file
        )
        self.assertEqual(parsed.name, "Stray Updated")
        self.assertEqual(parsed.description, "updated desc")
        self.assertEqual(parsed.prompt, "original prompt body")
        self.assertEqual(parsed.tools, ("Read", "Grep"))
        self.assertEqual(parsed.metadata.get("model"), "claude-3-5-sonnet")
        self.assertEqual(parsed.metadata.get("customKey"), "customVal")

    def test_update_unmanaged_rejects_unsafe_ref_and_missing_file(self) -> None:
        with self.assertRaises(MutationError) as ctx:
            self.mutations.update_unmanaged("claude/missing", name="M", description="d")
        self.assertEqual(ctx.exception.status, 404)

        with self.assertRaises(MutationError) as ctx:
            self.mutations.update_unmanaged("claude/../escape", name="E", description="d")
        self.assertEqual(ctx.exception.status, 404)

        with self.assertRaises(MutationError) as ctx:
            self.mutations.update_unmanaged("claude/.", name="E", description="d")
        self.assertEqual(ctx.exception.status, 404)

        with self.assertRaises(MutationError):
            self.mutations.update_unmanaged("invalid-ref", name="I", description="d")

        with self.assertRaises(MutationError) as ctx:
            self.mutations.update_unmanaged("unknown/slug", name="U", description="d")
        self.assertEqual(ctx.exception.status, 404)

    def test_update_unmanaged_rejects_symlink(self) -> None:
        self.store.create(name="Stray", description="ours", prompt="ours")
        self.mutations.enable("stray", "claude")
        self.assertTrue((self.harness_dir / "stray.md").is_symlink())

        with self.assertRaises(MutationError) as ctx:
            self.mutations.update_unmanaged("claude/stray", name="S", description="d")
        self.assertEqual(ctx.exception.status, 404)


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
        self.store.create(name="Keep", description="original", prompt="body", skills=("code-review",))
        updated = self.store.update("keep", description="changed")
        self.assertEqual(updated.description, "changed")
        self.assertEqual(updated.prompt, "body")
        self.assertEqual(updated.name, "Keep")
        self.assertEqual(updated.skills, ("code-review",))

    def test_update_explicit_skills_overwrites(self) -> None:
        self.store.create(name="Keep", description="original", prompt="body", skills=("code-review",))
        updated = self.store.update("keep", skills=("test-debugging", "perf-audit"))
        self.assertEqual(updated.skills, ("test-debugging", "perf-audit"))

    def test_update_empty_skills_clears(self) -> None:
        self.store.create(name="Keep", description="original", prompt="body", skills=("code-review",))
        updated = self.store.update("keep", skills=())
        self.assertEqual(updated.skills, ())

    def test_path_for_rejects_traversal(self) -> None:
        with self.assertRaises(MutationError):
            self.store.path_for("../escape")

    def test_scan_ignores_sync_artifacts_and_temp_files(self) -> None:
        self.store.create(name="Valid Agent", description="d", prompt="p")
        # Add sync conflict files and temp artifacts
        (self.store_root / ".sync-conflict-20240101.md").write_text("junk", encoding="utf-8")
        (self.store_root / "valid-agent.sync-conflict-20240101.md").write_text("junk", encoding="utf-8")
        (self.store_root / ".syncthing.valid-agent.md.tmp").write_text("junk", encoding="utf-8")
        (self.store_root / "valid-agent.tmp").write_text("junk", encoding="utf-8")
        (self.store_root / "valid-agent.bak").write_text("junk", encoding="utf-8")
        (self.store_root / "valid-agent.orig").write_text("junk", encoding="utf-8")
        (self.store_root / "valid-agent.md~").write_text("junk", encoding="utf-8")
        (self.store_root / ".#valid-agent.md").write_text("junk", encoding="utf-8")
        (self.store_root / "not-markdown.txt").write_text("junk", encoding="utf-8")

        agents, issues = self.store.scan()
        self.assertEqual([a.slug for a in agents], ["valid-agent"])
        self.assertEqual(issues, ())


if __name__ == "__main__":
    unittest.main()


class ContractKeyParityTests(unittest.TestCase):
    """The agent contract is declared twice — once per language — so it must be pinned.

    ``CONTRACT_KEYS`` (Python) decides what the parser lifts out of frontmatter and the
    order the renderer writes it in; ``AGENT_CONTRACT_KEYS`` (TypeScript) decides which
    rows the detail view hides from the custom-configuration editor. If they drift, a
    contract field silently shows up as an editable custom row and gets written twice.

    The fixed vocabularies are mirrored the same way: Python rejects anything outside
    them, TypeScript builds the pickers from them, so drift means a picker offering a
    value the API refuses.
    """

    #: Every ``name = [...] as const;`` tuple types.ts mirrors, and its Python source.
    MIRRORED_VOCABULARIES = {
        "EFFORT_VALUES": EFFORT_VALUES,
        "COLOR_VALUES": COLOR_VALUES,
        "ISOLATION_VALUES": ISOLATION_VALUES,
        "ALLOWED_SUBAGENTS_VALUES": ALLOWED_SUBAGENTS_VALUES,
    }

    TYPES_TS = (
        Path(__file__).resolve().parents[2] / "frontend/src/features/agents/api/types.ts"
    )

    def test_typescript_contract_keys_match_python(self) -> None:
        source = self.TYPES_TS.read_text(encoding="utf-8")
        match = re.search(
            r"export const AGENT_CONTRACT_KEYS = \[(.*?)\] as const;", source, re.S
        )
        self.assertIsNotNone(match, "AGENT_CONTRACT_KEYS not found in types.ts")
        assert match is not None
        ts_keys = tuple(re.findall(r'"([^"]+)"', match.group(1)))
        self.assertEqual(
            ts_keys,
            CONTRACT_KEYS,
            "frontend AGENT_CONTRACT_KEYS drifted from backend CONTRACT_KEYS",
        )

    def test_typescript_vocabularies_match_python(self) -> None:
        source = self.TYPES_TS.read_text(encoding="utf-8")
        for name, expected in self.MIRRORED_VOCABULARIES.items():
            with self.subTest(vocabulary=name):
                match = re.search(
                    rf"export const {name} = \[(.*?)\] as const;", source, re.S
                )
                self.assertIsNotNone(match, f"{name} not found in types.ts")
                assert match is not None
                ts_values = tuple(re.findall(r'"([^"]+)"', match.group(1)))
                self.assertEqual(
                    ts_values, expected, f"frontend {name} drifted from backend {name}"
                )

    def test_typescript_max_turns_default_matches_python(self) -> None:
        source = self.TYPES_TS.read_text(encoding="utf-8")
        match = re.search(r"export const MAX_TURNS_DEFAULT = (\d+);", source)
        self.assertIsNotNone(match, "MAX_TURNS_DEFAULT not found in types.ts")
        assert match is not None
        self.assertEqual(int(match.group(1)), MAX_TURNS_DEFAULT)

    def test_contract_keys_are_the_fields_the_parser_lifts_out(self) -> None:
        """Every contract key must leave metadata as a real parsed field, not a custom row."""
        document = "\n".join(
            ["---", *(f"{key}: v-{key}" for key in CONTRACT_KEYS), "---", "", "body"]
        )
        agent = parse_agent_document(document, slug="a", path=Path("a.md"))
        self.assertEqual(agent.extra_metadata, ())


class EffortValidationTests(unittest.TestCase):
    """`effort` is a fixed vocabulary, enforced where values enter an agent file."""

    def test_every_declared_value_is_accepted(self) -> None:
        for value in EFFORT_VALUES:
            self.assertEqual(validate_effort(value), value)

    def test_omitted_stays_omitted_and_empty_clears(self) -> None:
        self.assertIsNone(validate_effort(None))
        self.assertEqual(validate_effort(""), "")
        self.assertEqual(validate_effort("   "), "")

    def test_unknown_value_is_rejected_with_the_standard_envelope(self) -> None:
        with self.assertRaises(MutationError) as caught:
            validate_effort("maximum")
        self.assertEqual(caught.exception.status, 400)
        self.assertEqual(caught.exception.code, "invalid_effort")

    def test_matching_is_exact_so_no_case_variant_is_invented(self) -> None:
        """Accepting HIGH would silently rewrite the file into a value the picker
        cannot produce, inventing a case-insensitive contract nothing declares."""
        with self.assertRaises(MutationError):
            validate_effort("HIGH")


class ContractFieldValidationTests(unittest.TestCase):
    """The fixed vocabularies added alongside `effort`, enforced on the same terms."""

    VOCABULARIES = (
        (validate_color, COLOR_VALUES, "invalid_color", "chartreuse"),
        (validate_isolation, ISOLATION_VALUES, "invalid_isolation", "sandbox"),
        (
            validate_allowed_subagents,
            ALLOWED_SUBAGENTS_VALUES,
            "invalid_allowed_subagents",
            "yes",
        ),
    )

    def test_every_declared_value_is_accepted(self) -> None:
        for validate, values, _code, _rejected in self.VOCABULARIES:
            for value in values:
                with self.subTest(validator=validate.__name__, value=value):
                    self.assertEqual(validate(value), value)

    def test_omitted_stays_omitted_and_empty_clears(self) -> None:
        for validate, _values, _code, _rejected in self.VOCABULARIES:
            with self.subTest(validator=validate.__name__):
                self.assertIsNone(validate(None))
                self.assertEqual(validate(""), "")
                self.assertEqual(validate("   "), "")

    def test_unknown_value_is_rejected_with_the_standard_envelope(self) -> None:
        for validate, _values, code, rejected in self.VOCABULARIES:
            with self.subTest(validator=validate.__name__):
                with self.assertRaises(MutationError) as caught:
                    validate(rejected)
                self.assertEqual(caught.exception.status, 400)
                self.assertEqual(caught.exception.code, code)

    def test_max_turns_accepts_a_positive_whole_number(self) -> None:
        self.assertEqual(validate_max_turns("30"), "30")
        self.assertEqual(validate_max_turns("  7 "), "7")
        self.assertIsNone(validate_max_turns(None))
        self.assertEqual(validate_max_turns(""), "")

    def test_max_turns_rejects_non_numbers_and_non_positives(self) -> None:
        for rejected in ("many", "3.5", "0", "-1"):
            with self.subTest(value=rejected):
                with self.assertRaises(MutationError) as caught:
                    validate_max_turns(rejected)
                self.assertEqual(caught.exception.status, 400)
                self.assertEqual(caught.exception.code, "invalid_max_turns")


class ContractFieldRoundTripTests(unittest.TestCase):
    """The new scalars must survive a parse/render cycle as the YAML types they are."""

    def _round_trip(self, document: str):
        agent = parse_agent_document(document, slug="a", path=Path("a.md"))
        rendered = render_agent_document(
            name=agent.name,
            description=agent.description,
            prompt=agent.prompt,
            tools=agent.tools,
            skills=agent.skills,
            color=agent.color,
            model=agent.model,
            effort=agent.effort,
            allowed_subagents=agent.allowed_subagents,
            max_turns=agent.max_turns,
            isolation=agent.isolation,
            base_metadata=agent.metadata,
        )
        return agent, rendered

    def test_bool_and_int_scalars_keep_their_yaml_spelling(self) -> None:
        """``str(True)`` is ``"True"`` — a value neither the file nor the picker uses."""
        agent, rendered = self._round_trip(
            "---\n"
            "name: A\n"
            "description: d\n"
            "allowed_subagents: true\n"
            "max_turns: 30\n"
            "---\n\nbody\n"
        )
        self.assertEqual(agent.allowed_subagents, "true")
        self.assertEqual(agent.max_turns, "30")
        self.assertIn("allowed_subagents: true", rendered)
        self.assertIn("max_turns: 30", rendered)
        reparsed = parse_agent_document(rendered, slug="a", path=Path("a.md"))
        self.assertEqual(reparsed.allowed_subagents, "true")
        self.assertEqual(reparsed.max_turns, "30")
        self.assertEqual(reparsed.extra_metadata, ())

    def test_isolation_none_is_the_literal_string_not_a_null(self) -> None:
        agent, rendered = self._round_trip(
            "---\nname: A\ndescription: d\nisolation: none\n---\n\nbody\n"
        )
        self.assertEqual(agent.isolation, "none")
        self.assertIn("isolation: none", rendered)

    def test_contract_fields_render_in_declared_order(self) -> None:
        rendered = render_agent_document(
            name="A",
            description="d",
            prompt="body",
            tools=("Read",),
            skills=("code-review",),
            color="cyan",
            model="opus",
            effort="high",
            allowed_subagents="false",
            max_turns="12",
            isolation="worktree",
            extra_metadata=[{"key": "permissionMode", "value": "ask"}],
        )
        keys = [
            line.split(":", 1)[0]
            for line in rendered.splitlines()
            if line and not line.startswith((" ", "-", "---"))
        ]
        self.assertEqual(keys[: len(CONTRACT_KEYS)], list(CONTRACT_KEYS))
        self.assertEqual(keys[len(CONTRACT_KEYS)], "permissionMode")

    def test_an_explicit_empty_string_clears_the_key(self) -> None:
        rendered = render_agent_document(
            name="A",
            description="d",
            prompt="body",
            color="",
            allowed_subagents="",
            max_turns="",
            isolation="",
            base_metadata={
                "name": "A",
                "description": "d",
                "color": "cyan",
                "allowed_subagents": True,
                "max_turns": 30,
                "isolation": "worktree",
            },
        )
        for cleared in ("color", "allowed_subagents", "max_turns", "isolation"):
            self.assertNotIn(f"{cleared}:", rendered)


class _CountingSkillsQueries:
    """Stands in for SkillsQueryService, counting how often skill names are resolved.

    Resolving rescans the skills store and every installed harness directory, which
    is why the number of calls per request matters. ``inventory()`` raises on
    purpose: it runs the skills reconcile, which can auto-adopt, so a read of the
    agents matrix must never reach for it.
    """

    def __init__(self, names: dict[str, str]) -> None:
        self._names = names
        self.calls = 0

    def managed_skill_names(self) -> dict[str, str]:
        self.calls += 1
        return dict(self._names)

    def inventory(self):
        raise AssertionError(
            "a read of the agents matrix must not run the skills reconcile"
        )


class AgentSkillResolutionTests(unittest.TestCase):
    """Skill names are resolved once per build, not once per agent."""

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
        self.store = AgentStore(self.store_root)
        adapters = {"claude": AgentHarnessAdapter(self.target, self.store_root)}
        self.snapshot = lambda: ((self.target,), adapters)
        self.ledger = AgentBindingLedger(root / "data" / "bindings.json", home=root)

    def _write_agent(self, slug: str, skills: list[str]) -> None:
        (self.store_root / f"{slug}.md").write_text(
            render_agent_document(
                name=slug,
                description="d",
                prompt="body",
                skills=tuple(skills),
                extra_metadata=(),
            ),
            encoding="utf-8",
        )

    def _service(self, queries) -> AgentInventoryService:
        return AgentInventoryService(
            self.store, self.snapshot, self.ledger, skills_queries=queries
        )

    def test_build_scans_the_skills_inventory_once_for_many_agents(self) -> None:
        for index in range(5):
            self._write_agent(f"agent-{index}", ["alpha"])
        queries = _CountingSkillsQueries({"alpha": "Alpha Skill"})

        inventory = self._service(queries).build()

        self.assertEqual(
            queries.calls,
            1,
            "the skills inventory must be scanned once per build, not once per agent",
        )
        names = {
            skill.name for entry in inventory.entries for skill in entry.skills
        }
        self.assertEqual(names, {"Alpha Skill"})

    def test_build_without_skill_references_never_scans(self) -> None:
        self._write_agent("plain", [])
        queries = _CountingSkillsQueries({"alpha": "Alpha Skill"})

        self._service(queries).build()

        self.assertEqual(queries.calls, 0, "an inventory with no skills must not scan")

    def test_unresolvable_slug_falls_back_to_the_slug_itself(self) -> None:
        self._write_agent("agent", ["ghost"])
        queries = _CountingSkillsQueries({})

        entry = next(e for e in self._service(queries).build().entries if e.ref == "agent")

        self.assertEqual([(s.slug, s.name) for s in entry.skills], [("ghost", "ghost")])

    def test_a_failing_skills_service_does_not_break_the_matrix(self) -> None:
        # Several agents: a single one cannot distinguish "scanned once" from
        # "rescanned per row", which is half of what this pins.
        for index in range(3):
            self._write_agent(f"agent-{index}", ["alpha"])

        class Broken:
            calls = 0

            def managed_skill_names(self):
                Broken.calls += 1
                raise RuntimeError("skills store unavailable")

        broken = Broken()
        entries = self._service(broken).build().entries

        self.assertEqual(
            [[(s.slug, s.name) for s in e.skills] for e in entries],
            [[("alpha", "alpha")]] * 3,
        )
        self.assertEqual(broken.calls, 1, "a failing scan must not be retried per agent")


class AgentCreateHarnessBindingTests(unittest.TestCase):
    """Pin create-time harness binding, empty preselection, and partial failure handling."""

    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.spec = create_fake_home_spec(Path(self._tmp.name))
        self.container = build_backend_container(self.spec.env())

    def test_create_with_supported_harnesses_binds_them_and_returns_ok(self) -> None:
        req = CreateAgentRequest(
            name="Reviewer",
            description="Reviews PRs",
            prompt="Be thorough.",
            harnesses=["claude", "cursor"],
        )
        detail = create_agent(req, container=self.container)
        self.assertTrue(detail.ok)
        self.assertEqual(detail.harnessFailures, [])
        enabled = [h.harness for h in detail.harnesses if h.state == "enabled"]
        self.assertEqual(sorted(enabled), ["claude", "cursor"])
        self.assertTrue((self.spec.home / ".claude" / "agents" / "reviewer.md").exists())
        self.assertTrue((self.spec.home / ".cursor" / "agents" / "reviewer.md").exists())

    def test_create_with_empty_harness_list_succeeds_bound_to_nothing(self) -> None:
        req = CreateAgentRequest(
            name="Bare Agent",
            description="No harnesses yet",
            prompt="Wait for bindings.",
            harnesses=[],
        )
        detail = create_agent(req, container=self.container)
        self.assertTrue(detail.ok)
        self.assertEqual(detail.harnessFailures, [])
        enabled = [h.harness for h in detail.harnesses if h.state == "enabled"]
        self.assertEqual(enabled, [])
        self.assertTrue((self.spec.agents_root / "bare-agent.md").exists())
        self.assertFalse((self.spec.home / ".claude" / "agents" / "bare-agent.md").exists())

    def test_create_with_unsupported_harness_creates_agent_and_reports_failure(self) -> None:
        with AppTestHarness() as harness:
            resp = harness.post_json(
                "/api/agents",
                {
                    "name": "Partial Agent",
                    "description": "Partially bound",
                    "prompt": "Do your best.",
                    "harnesses": ["claude", "unsupported-harness"],
                },
                expected_status=200,
            )
            self.assertFalse(resp["ok"])
            self.assertEqual(len(resp["harnessFailures"]), 1)
            self.assertEqual(resp["harnessFailures"][0]["harness"], "unsupported-harness")
            self.assertIn("unsupported-harness", resp["harnessFailures"][0]["error"])
            self.assertEqual(resp["ref"], "partial-agent")
            claude_binding = next(h for h in resp["harnesses"] if h["harness"] == "claude")
            self.assertEqual(claude_binding["state"], "enabled")
            self.assertTrue((harness.spec.agents_root / "partial-agent.md").exists())
            self.assertTrue((harness.spec.home / ".claude" / "agents" / "partial-agent.md").exists())
