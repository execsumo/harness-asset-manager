from __future__ import annotations

from pathlib import Path

from harness_asset_manager.env_names import (
    AGY_ROOT_ENV,
    CLAUDE_ROOT_ENV,
    CODEX_ROOT_ENV,
    CURSOR_ROOT_ENV,
    HERMES_HOME_ENV,
    HERMES_ROOT_ENV,
    OPENCODE_ROOT_ENV,
    env_get,
)

from .contracts import (
    AgentFileBindingProfile,
    CommandFileBindingProfile,
    ConfigSubtreeBindingProfile,
    FamilyKey,
    FileTreeBindingProfile,
    FileTreeDiscoveryRoot,
    HarnessDefinition,
)


def _hermes_home(context) -> Path:
    # Three-way, in order: our own var (with its legacy spelling), then Hermes' own
    # HERMES_HOME, which we do not own and therefore never rename.
    override = env_get(context.env, HERMES_HOME_ENV) or context.env.get("HERMES_HOME")
    return Path(override) if override else context.home / ".hermes"


def _hermes_skills_root(context) -> Path:
    return _hermes_home(context) / "skills"


def _hermes_config_path(context) -> Path:
    return _hermes_home(context) / "config.yaml"


def supported_harness_definitions() -> tuple[HarnessDefinition, ...]:
    return SUPPORTED_HARNESS_DEFINITIONS


def supported_harness_ids() -> tuple[str, ...]:
    return tuple(definition.harness for definition in SUPPORTED_HARNESS_DEFINITIONS)


def core_harness_ids() -> tuple[str, ...]:
    """The harnesses this tool is built for — see ``SupportTier``.

    Derived from the catalog rather than listed anywhere else, so promoting or
    demoting a harness is a one-line change in ``SUPPORTED_HARNESS_DEFINITIONS`` and
    the release gates, the coverage ratchet, and the docs follow.
    """
    return tuple(
        definition.harness for definition in SUPPORTED_HARNESS_DEFINITIONS if definition.is_core
    )


def harness_definitions_for_family(family: FamilyKey) -> tuple[HarnessDefinition, ...]:
    return tuple(
        definition for definition in SUPPORTED_HARNESS_DEFINITIONS if definition.supports_family(family)
    )


SUPPORTED_HARNESS_DEFINITIONS: tuple[HarnessDefinition, ...] = (
    HarnessDefinition(
        harness="claude",
        label="Claude",
        logo_key="claude",
        install_probe="claude",
        support_tier="core",
        bindings={
            "skills": FileTreeBindingProfile(
                managed_env=CLAUDE_ROOT_ENV,
                managed_default=lambda context: context.home / ".claude" / "skills",
            ),
            "mcp": ConfigSubtreeBindingProfile(
                config_path_resolver=lambda context: context.home / ".claude.json",
                file_format="json",
                subtree_path=("mcpServers",),
                discovery_subtree_path_resolvers=(
                    lambda context: ("projects", str(context.home), "mcpServers"),
                    lambda context: ("projects", str(context.home.resolve()), "mcpServers"),
                ),
                codec="claude-code",
            ),
            "hooks": ConfigSubtreeBindingProfile(
                config_path_resolver=lambda context: context.home / ".claude" / "settings.json",
                file_format="json",
                subtree_path=("hooks",),
                codec="claude-code-hooks",
            ),
            "permissions": ConfigSubtreeBindingProfile(
                config_path_resolver=lambda context: context.home / ".claude" / "settings.json",
                file_format="json",
                subtree_path=("permissions",),
                codec="claude-code-permissions",
            ),
            "agents": AgentFileBindingProfile(
                root_path_resolver=lambda context: context.home / ".claude",
                output_dir_resolver=lambda context: context.home / ".claude" / "agents",
                docs_url="https://code.claude.com/docs/en/sub-agents",
            ),
            "slash_commands": CommandFileBindingProfile(
                root_path_resolver=lambda context: context.home / ".claude",
                output_dir_resolver=lambda context: context.home / ".claude" / "commands",
                invocation_prefix="/",
                render_format="frontmatter_markdown",
                scope="global",
                docs_url="https://code.claude.com/docs/en/slash-commands",
                file_glob="*.md",
                supports_frontmatter=True,
                support_note="Claude Code has merged custom commands into skills, while existing .claude/commands files remain supported.",
            ),
        },
    ),
    HarnessDefinition(
        harness="codex",
        label="Codex",
        logo_key="codex",
        install_probe="codex",
        support_tier="core",
        bindings={
            "skills": FileTreeBindingProfile(
                managed_env=CODEX_ROOT_ENV,
                managed_default=lambda context: context.home / ".agents" / "skills",
                discovery_roots=(
                    FileTreeDiscoveryRoot(
                        kind="admin-root",
                        scope="admin",
                        label="Admin skills root",
                        path_resolver=lambda _context: Path("/etc/codex/skills"),
                    ),
                    FileTreeDiscoveryRoot(
                        kind="legacy-root",
                        scope="legacy",
                        label="Legacy import root",
                        path_resolver=lambda context: context.home / ".codex" / "skills",
                    ),
                ),
            ),
            "mcp": ConfigSubtreeBindingProfile(
                config_path_resolver=lambda context: context.home / ".codex" / "config.toml",
                file_format="toml",
                subtree_path=("mcp_servers",),
                codec="codex",
            ),
            "hooks": ConfigSubtreeBindingProfile(
                config_path_resolver=lambda context: context.home / ".codex" / "config.toml",
                file_format="toml",
                subtree_path=("hooks",),
                codec="codex-hooks",
            ),
            "permissions": ConfigSubtreeBindingProfile(
                config_path_resolver=lambda context: context.home / ".codex" / "config.toml",
                file_format="toml",
                subtree_path=("permissions",),
                codec="codex-permissions",
            ),
            "agents": AgentFileBindingProfile(
                root_path_resolver=lambda context: context.home / ".codex",
                output_dir_resolver=lambda context: context.home / ".codex" / "agents",
                file_glob="*.toml",
                render_format="codex_toml",
                docs_url="https://developers.openai.com/codex/subagents",
            ),
            "slash_commands": CommandFileBindingProfile(
                root_path_resolver=lambda context: context.home / ".codex",
                output_dir_resolver=lambda context: context.home / ".codex" / "prompts",
                invocation_prefix="/prompts:",
                render_format="frontmatter_markdown",
                scope="global",
                docs_url="https://developers.openai.com/codex/custom-prompts",
                file_glob="*.md",
                supports_frontmatter=True,
                support_note="Codex custom prompts are deprecated in favor of skills, but this prompt directory remains verified for slash-command compatibility.",
            ),
        },
    ),
    HarnessDefinition(
        harness="agy",
        label="Antigravity",
        logo_key="agy",
        install_probe="agy",
        support_tier="core",
        bindings={
            "skills": FileTreeBindingProfile(
                managed_env=AGY_ROOT_ENV,
                managed_default=lambda context: context.home / ".gemini" / "antigravity-cli" / "skills",
                discovery_roots=(
                    FileTreeDiscoveryRoot(
                        kind="compat-root",
                        scope="agents-compat",
                        label="Agents compatibility root",
                        path_resolver=lambda context: context.home / ".agents" / "skills",
                    ),
                    FileTreeDiscoveryRoot(
                        kind="legacy-root",
                        scope="legacy",
                        label="Legacy import root",
                        path_resolver=lambda context: context.home / ".gemini" / "skills",
                    ),
                ),
            ),
            # Verified by probe: `agy agents` lists definitions dropped in
            # ~/.gemini/antigravity-cli/agents (and ~/.gemini/agents), and follows symlinks.
            "agents": AgentFileBindingProfile(
                root_path_resolver=lambda context: context.home / ".gemini" / "antigravity-cli",
                output_dir_resolver=lambda context: context.home
                / ".gemini"
                / "antigravity-cli"
                / "agents",
            ),
            "mcp": ConfigSubtreeBindingProfile(
                config_path_resolver=lambda context: context.home / ".gemini" / "config" / "mcp_config.json",
                discovery_config_path_resolvers=(
                    lambda context: context.home / ".gemini" / "antigravity-cli" / "mcp_config.json",
                    lambda context: context.home / ".gemini" / "antigravity" / "mcp_config.json",
                    lambda context: context.home / ".gemini" / "antigravity-ide" / "mcp_config.json",
                ),
                file_format="json",
                subtree_path=("mcpServers",),
                codec="antigravity-cli",
            ),
            "hooks": ConfigSubtreeBindingProfile(
                config_path_resolver=lambda context: context.home / ".gemini" / "config" / "hooks.json",
                discovery_config_path_resolvers=(
                    lambda context: context.home / ".gemini" / "antigravity-cli" / "hooks.json",
                    lambda context: context.home / ".gemini" / "antigravity" / "hooks.json",
                    lambda context: context.home / ".gemini" / "antigravity-ide" / "hooks.json",
                    lambda context: context.home / ".agents" / "hooks.json",
                ),
                file_format="json",
                subtree_path=(),
                codec="antigravity-hooks",
            ),
            "permissions": ConfigSubtreeBindingProfile(
                config_path_resolver=lambda context: context.home / ".gemini" / "antigravity-cli" / "settings.json",
                file_format="json",
                subtree_path=("permissions",),
                codec="antigravity-permissions",
            ),
            "slash_commands": CommandFileBindingProfile(
                root_path_resolver=lambda context: context.home / ".gemini" / "antigravity-cli",
                output_dir_resolver=lambda context: context.home
                / ".gemini"
                / "antigravity-cli"
                / "commands",
                invocation_prefix="/",
                render_format="frontmatter_markdown",
                scope="global",
                docs_url="https://antigravity.google/docs/cli/reference",
                file_glob="*.md",
                supports_frontmatter=True,
            ),
        },
    ),
    HarnessDefinition(
        harness="cursor",
        label="Cursor",
        logo_key="cursor",
        install_probe="cursor-agent",
        support_tier="core",
        bindings={
            "skills": FileTreeBindingProfile(
                managed_env=CURSOR_ROOT_ENV,
                managed_default=lambda context: context.home / ".cursor" / "skills",
                availability="cli_or_app",
                app_probe_paths=(
                    lambda _context: Path("/Applications/Cursor.app"),
                    lambda context: context.home / "Applications" / "Cursor.app",
                ),
            ),
            "mcp": ConfigSubtreeBindingProfile(
                config_path_resolver=lambda context: context.home / ".cursor" / "mcp.json",
                file_format="json",
                subtree_path=("mcpServers",),
                codec="cursor",
            ),
            "hooks": ConfigSubtreeBindingProfile(
                config_path_resolver=lambda context: context.home / ".cursor" / "hooks.json",
                file_format="json",
                subtree_path=("hooks",),
                codec="cursor-hooks",
            ),
            "permissions": ConfigSubtreeBindingProfile(
                config_path_resolver=lambda context: context.home / ".cursor" / "cli-config.json",
                file_format="json",
                subtree_path=("permissions",),
                codec="cursor-permissions",
            ),
            "agents": AgentFileBindingProfile(
                root_path_resolver=lambda context: context.home / ".cursor",
                output_dir_resolver=lambda context: context.home / ".cursor" / "agents",
                docs_url="https://cursor.com/docs/subagents",
                availability="cli_or_app",
            ),
            "slash_commands": CommandFileBindingProfile(
                root_path_resolver=lambda context: context.home / ".cursor",
                output_dir_resolver=lambda context: context.home / ".cursor" / "commands",
                invocation_prefix="/",
                render_format="cursor_plaintext",
                scope="global",
                docs_url="https://cursor.com/changelog/1-6",
                file_glob="*.md",
                supports_frontmatter=False,
                support_note="Cursor slash command support is verified locally; current public docs emphasize skills while older command files remain supported in practice.",
            ),
        },
    ),
    HarnessDefinition(
        harness="opencode",
        label="OpenCode",
        logo_key="opencode",
        install_probe="opencode",
        support_tier="best_effort",
        bindings={
            "skills": FileTreeBindingProfile(
                managed_env=OPENCODE_ROOT_ENV,
                managed_default=lambda context: context.xdg_config_home / "opencode" / "skills",
                availability="cli",
                discovery_roots=(
                    FileTreeDiscoveryRoot(
                        kind="compat-root",
                        scope="claude-compat",
                        label="Claude compatibility root",
                        path_resolver=lambda context: context.home / ".claude" / "skills",
                    ),
                    FileTreeDiscoveryRoot(
                        kind="compat-root",
                        scope="agents-compat",
                        label="Agents compatibility root",
                        path_resolver=lambda context: context.home / ".agents" / "skills",
                    ),
                ),
            ),
            "mcp": ConfigSubtreeBindingProfile(
                config_path_resolver=lambda context: context.home / ".opencode" / "opencode.jsonc",
                discovery_config_path_resolvers=(
                    lambda context: context.xdg_config_home / "opencode" / "opencode.json",
                ),
                source_install_config_path_resolvers=(
                    lambda context: context.home / ".opencode" / "opencode.jsonc",
                ),
                file_format="jsonc",
                subtree_path=("mcp",),
                codec="opencode",
            ),
            "hooks": ConfigSubtreeBindingProfile(
                config_path_resolver=lambda context: context.home / ".opencode" / "opencode.jsonc",
                discovery_config_path_resolvers=(
                    lambda context: context.xdg_config_home / "opencode" / "opencode.json",
                ),
                file_format="jsonc",
                subtree_path=("experimental", "hook"),
                codec="opencode-hooks",
            ),
            "agents": AgentFileBindingProfile(
                root_path_resolver=lambda context: context.xdg_config_home / "opencode",
                output_dir_resolver=lambda context: context.xdg_config_home / "opencode" / "agents",
                docs_url="https://opencode.ai/docs/agents/",
            ),
            "slash_commands": CommandFileBindingProfile(
                root_path_resolver=lambda context: context.xdg_config_home / "opencode",
                output_dir_resolver=lambda context: context.xdg_config_home / "opencode" / "commands",
                invocation_prefix="/",
                render_format="frontmatter_markdown",
                scope="global",
                docs_url="https://opencode.ai/docs/commands/",
                file_glob="*.md",
                supports_frontmatter=True,
            ),
        },
    ),
    HarnessDefinition(
        harness="hermes",
        label="Hermes Agent",
        logo_key="hermes",
        install_probe="hermes",
        support_tier="best_effort",
        bindings={
            "skills": FileTreeBindingProfile(
                managed_env=HERMES_ROOT_ENV,
                managed_default=_hermes_skills_root,
                layout="categorized",
                default_category="harness-asset-manager",
            ),
            "mcp": ConfigSubtreeBindingProfile(
                config_path_resolver=_hermes_config_path,
                file_format="yaml",
                subtree_path=("mcp_servers",),
                codec="hermes",
            ),
            # Hermes delegates to dynamically spawned subagents (config.yaml
            # `orchestrator`/`subagent_*` keys) and has no agent-definition file format
            # to bind to. It keeps a column for parity; every cell reports why.
            "agents": AgentFileBindingProfile(
                root_path_resolver=_hermes_home,
                output_dir_resolver=lambda context: _hermes_home(context) / "agents",
                unavailable_reason=(
                    "Hermes spawns subagents dynamically and has no agent-definition "
                    "file format to install into"
                ),
            ),
            "slash_commands": CommandFileBindingProfile(
                root_path_resolver=_hermes_home,
                output_dir_resolver=lambda context: _hermes_home(context) / "commands",
                invocation_prefix="/",
                render_format="frontmatter_markdown",
                scope="global",
                docs_url="",
                file_glob="*.md",
                supports_frontmatter=True,
                # Provisional (RECOMMENDATIONS.md §1.3): the ~/.hermes/commands
                # convention is an unverified assumption and the adapters have never
                # run against a real Hermes install. Surface that so users do not
                # trust unverified writes.
                support_note=(
                    "Provisional: Hermes slash-command conventions are unverified "
                    "against a real Hermes install; writes may not take effect."
                ),
            ),
        },
    ),
)


__all__ = [
    "SUPPORTED_HARNESS_DEFINITIONS",
    "core_harness_ids",
    "harness_definitions_for_family",
    "supported_harness_definitions",
    "supported_harness_ids",
]
