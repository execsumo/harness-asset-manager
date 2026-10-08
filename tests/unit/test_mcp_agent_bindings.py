from __future__ import annotations

import json
import unittest

from harness_asset_manager.application.agents.model import McpAgentBinding
from harness_asset_manager.application.agents.parser import split_frontmatter
from harness_asset_manager.application.mcp import ClaudeCodeMapper, CodexMapper
from harness_asset_manager.application.mcp.store import McpServerSpec, McpSource
from harness_asset_manager.errors import MutationError
from harness_asset_manager.harness.catalog import mcp_agent_binding_capability
from tests.support.app_harness import AppTestHarness


def _spec(name: str = "exa", **overrides: object) -> McpServerSpec:
    base: dict[str, object] = dict(
        name=name,
        display_name=name.title(),
        source=McpSource.marketplace(f"@user/{name}"),
        transport="stdio",
        command="npx",
        args=("-y", f"{name}-mcp-server"),
        env=(("EXA_API_KEY", "secret"),),
    )
    base.update(overrides)
    return McpServerSpec(**base)


class McpAgentBindingCapabilityTests(unittest.TestCase):
    def test_claude_and_codex_support_inline_binding(self) -> None:
        self.assertEqual(mcp_agent_binding_capability("claude"), "inline")
        self.assertEqual(mcp_agent_binding_capability("codex"), "inline")

    def test_every_other_catalogued_harness_defaults_to_unsupported(self) -> None:
        for harness in ("cursor", "pi", "agy", "opencode", "droid", "hermes"):
            self.assertEqual(
                mcp_agent_binding_capability(harness),
                "unsupported",
                msg=f"{harness} must not claim per-agent MCP isolation it has not been verified to have",
            )

    def test_unknown_harness_id_defaults_to_unsupported(self) -> None:
        self.assertEqual(mcp_agent_binding_capability("does-not-exist"), "unsupported")


class InlineBindingRenderTests(unittest.TestCase):
    def test_inline_binding_renders_mapper_resolved_dict_for_claude_agent(self) -> None:
        with AppTestHarness() as harness:
            spec = _spec("exa")
            harness.container.mcp_store.upsert_from_spec(spec)

            agent = harness.container.agents_store.create(
                name="Researcher",
                description="Looks things up.",
                prompt="Search the web.",
                harness="claude",
            )

            bindings = harness.container.agents_mutations.set_mcp_bindings(agent.slug, ("exa",))
            self.assertEqual(bindings, (McpAgentBinding(name="exa", mode="inline"),))

            # The sidecar bookkeeping round-trips the same way.
            reloaded = harness.container.agents_store.get(agent.slug)
            assert reloaded is not None
            self.assertEqual(reloaded.mcp_servers, (McpAgentBinding(name="exa", mode="inline"),))

            # The agent's own file carries the resolved per-entry dict a harness
            # actually connects to -- exactly what ClaudeCodeMapper would produce --
            # not a bare name reference only HAM understands.
            document = reloaded.path.read_text(encoding="utf-8")
            metadata, _ = split_frontmatter(document)
            self.assertEqual(metadata["mcpServers"], {"exa": ClaudeCodeMapper().spec_to_dict(spec)})

    def test_editing_the_canonical_spec_fans_out_to_every_inline_agent(self) -> None:
        """Highest-risk gap: an inline copy must never drift from the canonical spec."""
        with AppTestHarness() as harness:
            spec = _spec("exa", command="npx", args=("-y", "exa-mcp-server"))
            harness.container.mcp_store.upsert_from_spec(spec)

            agent_a = harness.container.agents_store.create(
                name="Researcher A", description="", prompt="x", harness="claude"
            )
            agent_b = harness.container.agents_store.create(
                name="Researcher B", description="", prompt="x", harness="claude"
            )
            harness.container.agents_mutations.set_mcp_bindings(agent_a.slug, ("exa",))
            harness.container.agents_mutations.set_mcp_bindings(agent_b.slug, ("exa",))

            # The canonical spec changes (new command/args)...
            edited = _spec("exa", command="uvx", args=("exa-mcp-server", "--flag"))
            harness.container.mcp_store.upsert_from_spec(edited)

            # ...and re-binding (what a "refresh"/edit flow does) picks up the new
            # resolved dict for every agent with an inline binding to that server,
            # not a stale copy of the old command.
            harness.container.agents_mutations.set_mcp_bindings(agent_a.slug, ("exa",))
            harness.container.agents_mutations.set_mcp_bindings(agent_b.slug, ("exa",))

            expected = ClaudeCodeMapper().spec_to_dict(edited)
            for agent in (agent_a, agent_b):
                reloaded = harness.container.agents_store.get(agent.slug)
                assert reloaded is not None
                document = reloaded.path.read_text(encoding="utf-8")
                metadata, _ = split_frontmatter(document)
                self.assertEqual(metadata["mcpServers"]["exa"], expected)


class CodexInlineBindingTests(unittest.TestCase):
    def test_codex_inline_binding_writes_mcp_servers_into_codex_extras_and_renders_it(self) -> None:
        with AppTestHarness() as harness:
            spec = _spec("exa")
            harness.container.mcp_store.upsert_from_spec(spec)

            agent = harness.container.agents_store.create(
                name="Codex Researcher", description="", prompt="x", harness="codex"
            )
            harness.container.agents_mutations.enable(agent.slug, "codex")

            bindings = harness.container.agents_mutations.set_mcp_bindings(agent.slug, ("exa",))
            self.assertEqual(bindings, (McpAgentBinding(name="exa", mode="inline"),))

            reloaded = harness.container.agents_store.get(agent.slug)
            assert reloaded is not None
            self.assertIn("mcp_servers", reloaded.codex_extras)
            self.assertEqual(reloaded.codex_extras["mcp_servers"]["exa"], CodexMapper().spec_to_dict(spec))

            # Codex renders its own separate TOML file (not the shared markdown);
            # it must have been refreshed with the same inline payload.
            rendered_path = harness.spec.home / ".codex" / "agents" / f"{agent.slug}.toml"
            self.assertTrue(rendered_path.is_file())
            self.assertIn("mcp_servers", rendered_path.read_text(encoding="utf-8"))


class HarnessFallbackBindingTests(unittest.TestCase):
    def test_unsupported_harness_falls_back_to_harness_level_enable(self) -> None:
        with AppTestHarness() as harness:
            # A manual (non-marketplace) source: ``enable_server`` for a marketplace
            # server re-resolves against the marketplace catalog, which is a detail
            # of installation this test is not exercising.
            spec = _spec("exa", source=McpSource.manual("exa"))
            harness.container.mcp_store.upsert_from_spec(spec)

            agent = harness.container.agents_store.create(
                name="Cursor Agent",
                description="",
                prompt="x",
                harness="cursor",
            )

            bindings = harness.container.agents_mutations.set_mcp_bindings(agent.slug, ("exa",))
            self.assertEqual(bindings, (McpAgentBinding(name="exa", mode="harness_fallback"),))

            # No inline content was ever written into the agent's own file: there is
            # nothing to isolate on a harness with no per-agent MCP isolation.
            reloaded = harness.container.agents_store.get(agent.slug)
            assert reloaded is not None
            document = reloaded.path.read_text(encoding="utf-8")
            metadata, _ = split_frontmatter(document)
            self.assertNotIn("mcpServers", metadata)

            # Instead the server was enabled at the harness level.
            cursor_cfg = harness.spec.home / ".cursor" / "mcp.json"
            self.assertTrue(cursor_cfg.is_file())
            payload = json.loads(cursor_cfg.read_text(encoding="utf-8"))
            self.assertIn("exa", payload.get("mcpServers", {}))


class ValidateMcpServersTests(unittest.TestCase):
    def test_rejects_unknown_server_name(self) -> None:
        with AppTestHarness() as harness:
            with self.assertRaises(MutationError) as ctx:
                harness.container.agents_mutations.validate_mcp_servers(["does-not-exist"])
            self.assertEqual(ctx.exception.status, 400)
            self.assertEqual(ctx.exception.code, "invalid_mcp_server")

    def test_accepts_and_dedupes_known_names(self) -> None:
        with AppTestHarness() as harness:
            harness.container.mcp_store.upsert_from_spec(_spec("exa"))
            result = harness.container.agents_mutations.validate_mcp_servers(["exa", "exa"])
            self.assertEqual(result, ("exa",))


class DeleteGuardTests(unittest.TestCase):
    def test_cannot_remove_a_server_still_bound_to_an_agent(self) -> None:
        with AppTestHarness() as harness:
            harness.container.mcp_store.upsert_from_spec(_spec("exa"))
            agent = harness.container.agents_store.create(
                name="Researcher", description="", prompt="x", harness="claude"
            )
            harness.container.agents_mutations.set_mcp_bindings(agent.slug, ("exa",))

            with self.assertRaises(MutationError) as ctx:
                harness.container.mcp_mutations.uninstall_server("exa")
            self.assertEqual(ctx.exception.status, 409)
            self.assertEqual(ctx.exception.code, "mcp_server_in_use")

            # The manifest entry survives the refused removal.
            self.assertIsNotNone(harness.container.mcp_store.get_managed("exa"))

    def test_removal_succeeds_once_the_agent_is_unbound(self) -> None:
        with AppTestHarness() as harness:
            harness.container.mcp_store.upsert_from_spec(_spec("exa"))
            agent = harness.container.agents_store.create(
                name="Researcher", description="", prompt="x", harness="claude"
            )
            harness.container.agents_mutations.set_mcp_bindings(agent.slug, ("exa",))
            harness.container.agents_mutations.set_mcp_bindings(agent.slug, ())

            harness.container.mcp_mutations.uninstall_server("exa")
            self.assertIsNone(harness.container.mcp_store.get_managed("exa"))


if __name__ == "__main__":
    unittest.main()
