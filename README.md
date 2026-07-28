# harness-asset-manager

<p align="center">
  <img src="assets/harness_asset_manager_logo.svg" alt="Harness Asset Manager" width="520" />
</p>

<p align="center">
  <strong>A local-first control center for AI extensions.</strong><br />
  Use, review, and discover Skills, Agents, MCP servers, slash commands, hooks, and CLI tools across agent harnesses.
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-111827?style=flat-square" /></a>
  <a href="https://github.com/execsumo/harness-asset-manager/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/execsumo/harness-asset-manager?style=flat-square&color=EA580C" /></a>
  <a href="#install"><img alt="Install with Homebrew" src="https://img.shields.io/badge/install-homebrew-FBBF24?style=flat-square&logo=homebrew&logoColor=111827" /></a>
  <a href="#install"><img alt="macOS ARM64/x64" src="https://img.shields.io/badge/platform-macOS%20ARM64%2Fx64-111827?style=flat-square&logo=apple&logoColor=white" /></a>
  <a href="#local-first-safety"><img alt="Local-first" src="https://img.shields.io/badge/data-local--first-0F766E?style=flat-square" /></a>
</p>

![skill-market-overview](./assets/harness-asset-manager-skill-unification.svg)

## Why it exists

AI extensions are scattered across harness-specific folders, MCP config files, slash command locations, and marketplace sources. Harness Asset Manager gives those pieces one local control surface:

| Product idea | What it means |
|---|---|
| **In use** | Harness Asset Manager controls the item and can enable or disable it across harnesses. |
| **Needs review** | Harness Asset Manager found local state, config differences, or inventory issues that need a decision. |
| **Discover** | Browse marketplaces and preview external tools. |

## What you can do

- See what is in use, what needs review, and where extensions are active.
- Adopt local Skills into one shared inventory, then enable or disable them per harness.
- Install or adopt MCP server configs, resolve differences, and enable them where supported.
- Manage reusable slash commands once, then sync them to supported harnesses.
- Manage hooks as normalized records, then sync them into supported harness settings with drift detection and review for unmanaged entries.
- Manage Agents — markdown files in the store, symlinked into each harness's agents directory, with In Use and Needs Review views like every other family. If a harness overwrites a link with its own copy, provably-safe edits are folded back in automatically and conflicting ones are left for you.
- Enforce strict **Denylists** across supported harnesses (Claude Code, Antigravity, and Codex) to restrict shell commands, file paths, web domains, and MCP tools in a single unified view.
- Capture and back up **Native Config Snapshots** across all 7 supported harnesses (`~/.harness-asset-manager/configs/`) with automatic drift detection, SHA-256 deduplication, secret redaction, Web UI controls, and `ham snapshot` CLI support.
- Discover Skills, MCP servers, and preview-only CLI tools from marketplace sources.

## Product tour

### Overview

Start with the whole extension portfolio: what is in use, what needs review, what can be discovered, and where extensions are active.

![skill-market-overview](./assets/harness-asset-manager-overview.png)

### Skills

Use Skills as shared local packages instead of maintaining separate copies per harness.

Typical flow:

1. Review a Skill found in a harness or install one from the marketplace.
2. Adopt it into the Harness Asset Manager inventory.
3. Enable it only where it should be available.
4. Update, remove, or delete it from one place.

![skill-market-skill-matrxi](./assets/harness-asset-manager-skill-matrix.png)

### MCP servers

Use MCP servers as one normalized config that can be written into each harness shape.

Typical flow:

1. Review an MCP server found in a harness or install one from the marketplace.
2. Adopt it into the Harness Asset Manager inventory.
3. Enable it where the server should be available.
4. Resolve config differences, disable harness bindings, or uninstall it from one place.

![skill-market-skill-matrxi](./assets/harness-asset-manager-mcp-matrix.png)

### Slash commands

Use slash commands as one shared prompt library instead of rewriting the same command in each harness-specific format.

Typical flow:

1. Create a slash command with a name, description, and prompt.
2. Use `$ARGUMENTS` where runtime input should be inserted.
3. Sync it to supported harnesses.
4. Review existing harness command files and adopt them into the shared library when needed.

![skill-market-slash-commands-matrix](./assets/harness-asset-manager-slash_commands-matrix.png)

### Agents

Subagents you keep in one place instead of copy-pasting between harnesses.

Typical flow:

1. Write an agent — a name, a description, and a system prompt — or adopt one Harness Asset Manager found in a harness.
2. Turn it on for the harnesses that should have it.
3. Review agents discovered in harness directories and adopt the ones worth keeping.

If a harness later edits an agent out from under Harness Asset Manager — some editors replace the link with their own copy — that edit is folded back in automatically, but only when it is provably the only edit. Conflicting edits are always left for you to resolve. See [Agents](#agents-1) below.

### Marketplace

Marketplace is the discovery surface:

- **Skills Marketplace**: browse and install Skills.
- **MCP Marketplace**: browse and install MCP servers.
- **CLI Marketplace**: preview external CLI tools from CLIs.dev. This is display-only; Harness Asset Manager does not install or manage CLIs.

![skill-market-skill-matrxi](./assets/harness-asset-manager-marketplace.png)

## Install

### Homebrew (macOS recommended)

```bash
brew tap execsumo/tap
brew install harness-asset-manager
harness-asset-manager start
```

`harnessAM` is a short alias for the same formula (`brew install harnessAM`).

## Supported harnesses

<table align="center">
  <tr>
    <td align="center" valign="middle">
      <img src="assets/harness-logos/claude-code-logo.svg" alt="Claude Code" height="56" /><br />
      <strong>Claude Code</strong><br />
      <a href="https://code.claude.com/docs/en/overview">Docs</a>
    </td>
    <td align="center" valign="middle">
      <img src="assets/harness-logos/codex-logo.svg" alt="Codex CLI" height="56" /><br />
      <strong>Codex CLI</strong><br />
      <a href="https://developers.openai.com/codex/cli">Docs</a>
    </td>
    <td align="center" valign="middle">
      <img src="assets/harness-logos/agy-logo.svg" alt="Antigravity CLI" height="56" /><br />
      <strong>Antigravity (agy)</strong><br />
      <a href="https://antigravity.google">Docs</a>
    </td>
    <td align="center" valign="middle">
      <img src="assets/harness-logos/cursor-logo.svg" alt="Cursor" height="56" /><br />
      <strong>Cursor</strong><br />
      <a href="https://cursor.com/docs">Docs</a>
    </td>
    <td align="center" valign="middle">
      <img src="assets/harness-logos/opencode-logo.svg" alt="OpenCode" height="56" /><br />
      <strong>OpenCode</strong><br />
      <a href="https://opencode.ai/docs">Docs</a>
    </td>
    <td align="center" valign="middle">
      <img src="assets/harness-logos/hermes-logo.svg" alt="Hermes Agent" height="56" /><br />
      <strong>Hermes Agent</strong><br />
      <a href="https://hermes-agent.nousresearch.com/docs">Docs</a>
    </td>
    <td align="center" valign="middle">
      <img src="assets/harness-logos/openclaw-logo.svg" alt="OpenClaw" height="56" /><br />
      <strong>OpenClaw</strong><br />
      <a href="https://docs.openclaw.ai/start/getting-started">Docs</a>
    </td>
  </tr>
</table>

Harnesses appear in this order everywhere in the app — Settings, and every resource
matrix. The order is declared once, in `SUPPORTED_HARNESS_DEFINITIONS`
(`harness_asset_manager/harness/catalog.py`); every family derives its columns from it, so there
is no per-page ordering to keep in sync. A harness switched off in Settings is dropped
from every matrix rather than shown as an inert column.

| Harness | Skills | MCP servers | Slash commands | Hooks | Permissions |
|---|---:|---:|---:|---:|---:|
| Codex CLI | Yes | Yes | Yes | Yes | Yes (Denylist) |
| Claude Code | Yes | Yes | Yes | Yes | Yes (Denylist) |
| Cursor | Yes | Yes | Yes | Yes | No |
| OpenCode | Yes | Yes | Yes | Partial | No |
| Hermes Agent | Yes | Yes | Yes* | Not Yet | No |
| OpenClaw | Yes | Not Yet | Not Yet | Not Yet | No |
| Antigravity (agy) | Yes | Yes | Not Yet | Partial | Yes (Denylist) |

<sub>\* Hermes Agent slash-command support is provisional. Its slash-command directory (`~/.hermes/commands`, frontmatter Markdown) follows common conventions but is **not yet verified against a shipping Hermes build**; hooks are not yet mapped. See `handoff.md`.</sub>

## Local-first safety

Harness Asset Manager is a local configuration-management tool. It runs on your machine and reads or writes local harness extension state.

Actions that can change local state include:

- adopting a local skill folder
- enabling or disabling a skill for a harness
- updating a source-backed skill
- removing or deleting a skill
- installing an MCP server into a selected harness config
- adopting an existing MCP config
- enabling, disabling, resolving, or uninstalling an MCP server
- creating, updating, syncing, importing, or deleting a slash command
- creating, enabling, disabling, resolving, or deleting a hook binding
- changing harness support settings
- repairing a drifted agent binding, which can move an edit out of a harness file and into the store

That last one is the only action Harness Asset Manager takes without being asked. It is limited to cases where no content can be lost — either the two copies are identical, or the harness copy is provably the only edit that exists — and it is recorded in an audit log surfaced in the app. Turn it off in Settings under **Repair drifted agent bindings automatically**.

App-owned files live under `~/.harness-asset-manager` on macOS (with a legacy fallback to `~/Library/Application Support/harness-asset-manager` if it already exists) and XDG base directories on Linux.

## How it works

### Store layout

Harness Asset Manager keeps a flat store under its data directory: `skills/` holds one directory per skill, `agents/` holds one `<slug>.md` per agent, and each family's manifests sit alongside. Every binding into a harness points back here, so a resource is edited once and every harness that has it enabled follows.

Two earlier layouts are migrated one-time on first start — the pre-package `shared/` directory and the later `packages/local/` structure both fold into `skills/` and `agents/`. The migration is locked, idempotent, and skipped once the flat layout exists.

### Skills

Before adoption, each harness points at its own local skill folder. After adoption, Harness Asset Manager keeps one canonical package in its shared local store and exposes it to selected harnesses with local links. Disabling a harness removes that harness binding without deleting the package.

Harness Asset Manager treats managed Skills as portable by default: once a Skill is adopted into the shared store, it can be enabled for any supported harness. `originHarness` is retained only as provenance.

Hermes Agent Skills use the categorized Hermes layout under `~/.hermes/skills/<category>/<skill>/SKILL.md`. Shared Skills enabled for Hermes are linked under the `harness-asset-manager` category by default. Harness Asset Manager only imports Hermes Skills that Hermes itself installed from external hub provenance (`.hub/lock.json` entries that are not official/builtin/optional). Hermes self-learned/local Skills, bundled Skills tracked by `.bundled_manifest`, and official optional Skills recorded in Hermes hub provenance are excluded from Harness Asset Manager inventory and bulk actions; Harness Asset Manager leaves those folders untouched so `hermes update` and Hermes-owned Skill sync keep their normal ownership.

![skill-market-overview](./assets/harness-asset-manager-skill-unification.svg)

### MCP servers

MCP servers are stored as normalized Harness Asset Manager records, then translated into the config shape each harness expects:

- Codex uses TOML under `mcp_servers`.
- Claude Code and Cursor use `mcpServers` JSON entries.
- OpenCode uses typed local/remote MCP entries.
- Antigravity (agy) uses `mcpServers` JSON entries with `serverUrl` for HTTP transports and `command`/`args`/`env` for stdio.
- Hermes Agent uses YAML under `mcp_servers` in `~/.hermes/config.yaml` (or `$HERMES_HOME/config.yaml`).
- OpenClaw MCP writes are not yet supported.

When Harness Asset Manager finds different configs for the same MCP server, it asks you to resolve the source of truth first.

![skill-market-overview](./assets/harness-asset-manager-mcp-translation.svg)

### Slash commands

Slash commands are stored as TOML records under Harness Asset Manager app storage, then rendered into each supported harness format:

- Claude Code writes Markdown command files under `~/.claude/commands` and invokes them with `/`.
- Codex writes prompt files under `~/.codex/prompts` and invokes them with `/prompts:`.
- Cursor writes plain text command files under `~/.cursor/commands` and invokes them with `/`.
- OpenCode writes Markdown command files under `~/.config/opencode/commands` and invokes them with `/`.
- Hermes Agent writes Markdown command files under `~/.hermes/commands` and invokes them with `/` (provisional).
- OpenClaw and Antigravity (agy) slash command writes are not yet supported.

Disabling a harness in Settings removes its column here immediately, without a restart.
Command files already written to that harness and their sync records are left alone —
re-enabling it restores the column and its sync state unchanged.

Harness Asset Manager tracks target ownership with sync state and content hashes. It will not overwrite an untracked command file automatically, and it reports managed files as changed or missing when the target no longer matches the last synced hash. Review actions let you adopt unmanaged commands, restore managed content, adopt a changed harness command as the new source, or remove a broken binding while leaving the harness file untouched.

### Hooks

Hooks are stored as normalized Harness Asset Manager records using **canonical events** (`pre_tool_use`, `post_tool_use`, `user_prompt_submit`, `session_start`, `stop`, `pre_compact`) and **canonical tool categories** (`shell`, `file_read`, `file_write`, `mcp`, `web`, `any`). Each harness codec translates a canonical record into that harness's native event names and config shape, and merges it into the harness's hook config:

- Claude Code writes hook entries into `~/.claude/settings.json` under the `hooks` key.
- Codex writes inline `[hooks]` tables into `~/.codex/config.toml` (same event schema as Claude).
- Cursor writes `~/.cursor/hooks.json`, expressing each tool category as its dedicated event (`beforeShellExecution`, `afterFileEdit`, `beforeMCPExecution`, and so on).
- OpenCode writes `experimental.hook` entries in `opencode.json` — limited to `file_edited` (post-edit on write) and `session_completed` (stop), so coverage is partial.
- Antigravity (agy) writes a name-keyed `~/.gemini/config/hooks.json`, matching against its own tool names (`run_command`, `view_file`, …); it covers tool, stop, and (via `PreInvocation`) prompt-submit hooks, so coverage is partial.

Because harnesses differ, not every canonical event maps to every harness. Harness Asset Manager exposes a **representability matrix** showing where each hook can sync and where it cannot, including caveats — for example, an Antigravity `user_prompt_submit` hook maps to `PreInvocation`, which fires before every model invocation rather than only on prompt submit.

Harness Asset Manager owns only the specific hook entries it writes. It merges into each harness's config without disturbing hooks or other keys it does not manage, and it tracks ownership with content hashes. When a managed hook is edited outside Harness Asset Manager it is reported as drifted, and hooks found in a harness that Harness Asset Manager does not manage are reported as unmanaged for review.

### Agents

Agents are Markdown files with YAML frontmatter and the system prompt as the body. They live in Harness Asset Manager's store; enabling one for a harness symlinks it into that harness's agents directory, so editing the agent once updates it everywhere it is enabled.

Harness Asset Manager reads `name`, `description`, and `tools`, and **leaves every other frontmatter key alone**. Harness agents routinely carry settings we have no business interpreting — Claude's `model`, `permissionMode`, `maxTurns`, `hooks`; Cursor's `readonly` and `is_background`; Codex's `sandbox_mode` — so an edit merges into the original frontmatter rather than re-rendering it, and unrecognized keys survive untouched. The detail view lists them verbatim under **Configuration**, which means a new harness field shows up without any code change here. The only keys dropped on write are `capabilities:` and `harnesses:` from the retired compile model, which nothing reads.

The agents matrix shows the same harnesses as every other family — whichever you have enabled in Settings:

| Harness | Location | How it is installed |
|---|---|---|
| Claude Code | `~/.claude/agents/` | symlink |
| Cursor | `~/.cursor/agents/` | symlink |
| Antigravity | `~/.gemini/antigravity-cli/agents/` | symlink |
| OpenCode | `$XDG_CONFIG_HOME/opencode/agents/` | symlink |
| Codex | `~/.codex/agents/` | rendered TOML |
| Hermes | — | not installable |

Most harnesses read the same Markdown format the store holds, so enabling one symlinks the store file into place — edit the agent once and every harness it is enabled for follows. **Codex** is the exception: it reads TOML with different keys (`name`, `description`, `developer_instructions`), so Harness Asset Manager renders a real file marked `# harness-asset-manager:generated`. Local edits to a rendered file are reported but never adopted — re-enabling overwrites them. **Hermes** keeps a column for consistency but spawns subagents dynamically and has no agent-definition file to install into, so its cells say so rather than offering a toggle that cannot work.

Harness Asset Manager only ever removes files it owns — a symlink into its store, or a file carrying its generated marker. Anything else in a harness's agents directory is reported as **unmanaged** for review, never overwritten. Adopting one moves it into the store (converting Codex TOML to Markdown) and installs it back. If the name is already taken in the store, Harness Asset Manager refuses to guess and asks which version to keep.

#### When a harness breaks the link

Some editors save a file by writing a temporary file and renaming it over the target. Renaming over a symlink **replaces the symlink** with a regular file, so a harness that edits an agent through its own UI can silently turn a binding into an ordinary copy — and from then on the two versions drift apart. (Skills are immune to this: they bind as directory symlinks, and renaming a directory over one fails at the kernel.)

Harness Asset Manager records every binding it makes in `bindings.json`: which agent went to which harness, and what the store held at that moment. That record is what makes the difference between "a harness broke our link" and "an unrelated file happens to share this name" decidable — without it, the two are the same observation. The record is a cache, never a source of truth; if it disagrees with the filesystem, the filesystem wins. Deleting it costs you the automation, never your content.

On the next inventory load, each broken binding is classified and handled:

| What is found | What happens |
|---|---|
| The copy is identical to the store | The link is restored. There is no content decision to make. |
| The copy was edited, and the store has not changed since it was linked | That copy holds the only edit in existence, so it is adopted into the store and every binding for that agent is restored. |
| The copy was edited **and** the store changed too | Nothing. Both sides hold work; choosing either discards the other. Reported for you to resolve. |
| Several harnesses were edited differently | Nothing is adopted and nothing is deleted. Each version is preserved under `agents/conflicts/`, with one issue naming every side. |
| There is no record of a binding here | Nothing. This is an ordinary name collision, and you are asked, as before. |

Newest-file-wins is deliberately **not** a rule here — it silently discards the other harness's work, which is the exact failure this exists to prevent. Codex is excluded from automatic adoption entirely, because converting its TOML back to Markdown drops keys Harness Asset Manager does not model.

Every automatic action is appended to an audit log and shown as **Recent automatic repairs** on the agents review page: repair you cannot see is nearly as bad as breakage you cannot see. The whole behaviour is off with one switch in Settings, and turning it off takes effect on the next load, not the next restart.

### CLIs

CLI marketplace entries are preview-only.

## Configuration

On macOS, app-owned files live under `~/.harness-asset-manager` (with a legacy fallback to `~/Library/Application Support/harness-asset-manager` if it already exists). On Linux, app-owned files use XDG base directories.

Useful macOS paths:

- skills store: `~/.harness-asset-manager/skills` (migrated from the legacy `shared/` and `packages/local/skills` layouts on first start)
- agents store: `~/.harness-asset-manager/agents`
- agent binding ledger: `~/.harness-asset-manager/bindings.json`
- agent repair audit log: `~/.harness-asset-manager/agents-audit.json`
- preserved conflicting agent copies: `~/.harness-asset-manager/agents/conflicts`
- MCP manifest: `~/.harness-asset-manager/mcp/manifest.json`
- hooks manifest: `~/.harness-asset-manager/hooks/manifest.json`
- slash command library: `~/.harness-asset-manager/slash-commands/commands`
- slash command sync state: `~/.harness-asset-manager/slash-commands/sync-state.json`
- marketplace cache: `~/.harness-asset-manager/marketplace`
- app settings: `~/.harness-asset-manager/settings.json` (harness on/off, plus `autoAdopt`)

Useful Linux paths:

- skills store: `${XDG_DATA_HOME:-~/.local/share}/harness-asset-manager/skills`
- agents store: `${XDG_DATA_HOME:-~/.local/share}/harness-asset-manager/agents`
- agent binding ledger: `${XDG_DATA_HOME:-~/.local/share}/harness-asset-manager/bindings.json`
- agent repair audit log: `${XDG_DATA_HOME:-~/.local/share}/harness-asset-manager/agents-audit.json`
- MCP manifest: `${XDG_DATA_HOME:-~/.local/share}/harness-asset-manager/mcp/manifest.json`
- hooks manifest: `${XDG_DATA_HOME:-~/.local/share}/harness-asset-manager/hooks/manifest.json`
- slash command library: `${XDG_DATA_HOME:-~/.local/share}/harness-asset-manager/slash-commands/commands`
- slash command sync state: `${XDG_DATA_HOME:-~/.local/share}/harness-asset-manager/slash-commands/sync-state.json`
- marketplace cache: `${XDG_DATA_HOME:-~/.local/share}/harness-asset-manager/marketplace`
- app settings: `${XDG_CONFIG_HOME:-~/.config}/harness-asset-manager/settings.json`

Most users do not need to change these locations. If you manage skills in a custom environment, you can override individual skill roots with environment variables.

| Harness | Env var | Default Harness Asset Manager skill root |
|---|---|---|
| Codex | `SKILL_MANAGER_CODEX_ROOT` | `~/.agents/skills` |
| Claude | `SKILL_MANAGER_CLAUDE_ROOT` | `~/.claude/skills` |
| Cursor | `SKILL_MANAGER_CURSOR_ROOT` | `~/.cursor/skills` |
| OpenCode | `SKILL_MANAGER_OPENCODE_ROOT` | `~/.config/opencode/skills` |
| Hermes Agent | `SKILL_MANAGER_HERMES_ROOT` | `${HERMES_HOME:-~/.hermes}/skills` |
| OpenClaw | `n/a` | `~/.openclaw/skills` |
| Antigravity (agy) | `SKILL_MANAGER_AGY_ROOT` | `~/.gemini/antigravity-cli/skills` |

MCP config locations are harness-owned. Harness Asset Manager writes only to verified config paths and skips unsupported harness writes. Hermes Agent config discovery honors `SKILL_MANAGER_HERMES_HOME` first, then `HERMES_HOME`, then `~/.hermes`.

## From source

### Requirements

- Python 3.11+
- Node.js 18+
- npm

`harness-asset-manager` supports Python 3.11+. CI validates backend compatibility on Python 3.11 through 3.14, while packaging and release builds stay pinned to Python 3.11 for determinism.

### Contributor setup

```bash
scripts/install-dev.sh
```

### Run locally

```bash
scripts/start-dev.sh
```

Stop the managed local instance:

```bash
scripts/stop-dev.sh
```

The split dev flow is available when you want Vite hot reload:

```bash
npm run dev
npm run dev:backend
```

Default local URLs:

- Frontend: `http://127.0.0.1:5173`
- Backend: `http://127.0.0.1:8000`
- Health: `http://127.0.0.1:8000/api/health`

The server binds to loopback only, and it rejects requests with a non-loopback `Host` header
(DNS-rebinding protection) and mutations with a non-loopback `Origin` header (CSRF protection).
Binding a non-loopback address requires an explicit opt-in, and is discouraged because the API
has no authentication:

```bash
harness-asset-manager serve --host 0.0.0.0 --allow-remote
```

Validation:

```bash
scripts/install-dev.sh
npm run typecheck
bash scripts/test_backend.sh
npm test
npm run build
```

## Troubleshooting

- If Marketplace requests fail with `Marketplace is temporarily unavailable`, verify your network connection and try again.
- If an MCP harness is shown as unavailable, Harness Asset Manager has detected that the local client is missing or does not support the required config surface.

## More to come

### Extension families

- [x] Hook support
- [x] Slash command support
- [x] Agent personas
- [x] Package-based storage (portable resource bundles)
- [ ] Plugin support

### Harness expansion

- [ ] GitHub Copilot
- [ ] Gemini CLI
- [ ] Cline
- [ ] Windsurf
- [ ] Qwen Code
- [ ] Kimi Code
- [ ] Qoder

## Community

- See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.
- See [SECURITY.md](SECURITY.md) to report vulnerabilities privately.
