# Harness Asset Manager — Architecture

This document describes the high-level architecture, domain model, harness catalog, storage layout, and security design of **Harness Asset Manager (HAM)**.

---

## 1. Overview & System Design

Harness Asset Manager is a local-first control center for AI developer extensions. It unifies Skills, MCP Servers, Slash Commands, Hooks, Subagents, and Denylist Permissions across heterogeneous AI agent harnesses into one single interface.

```
+---------------------------------------------------------------------------------+
|                               React / Vite SPA                                  |
|         (Tailwind / Vanilla CSS, Lucide icons, TanStack React Query)            |
+---------------------------------------------------------------------------------+
                                       |
                              HTTP / REST API
                                       |
+---------------------------------------------------------------------------------+
|                             FastAPI / Uvicorn Server                            |
|             Loopback Bind (127.0.0.1) + Loopback Host/Origin Guards            |
+---------------------------------------------------------------------------------+
                                       |
                               Domain Services
  (SkillsService, McpService, SlashCommandsService, HooksService, AgentsService, PermissionsService)
                                       |
                 +---------------------+---------------------+
                 |                                           |
        Store & Manifest Storage                 Harness Adapters & Mappers
     (~/.harness-asset-manager/)              (Claude, Codex, AGY, Cursor, etc.)
                 |                                           |
    Atomic File Writes & Locks                    Harness Native Config Files
```

---

## 2. Domain Model & Resource Families

Harness Asset Manager manages six core extension families:

### 1. Skills
- **Storage**: Portable Markdown skill folders (`SKILL.md` + scripts/resources) under `skills/<package>/`, with source and revision tracked in `skills-manifest.json`.
- **Harness Integration**: Installed via local filesystem links (`symlink`) into each harness's skills directory (`~/.claude/skills`, `~/.agents/skills`, `~/.gemini/antigravity-cli/skills`, etc.).
- **Hermes Support**: Categorized under `~/.hermes/skills/harness-asset-manager/`. Hub-installed skills are tracked while local/learned skills remain untouched.

### 2. MCP Servers
- **Storage**: Normalized JSON records in `mcp/manifest.json`.
- **Harness Translation**: Mapped by harness-specific codecs:
  - **Claude Code / Cursor**: JSON under `mcpServers` in `.claude.json` / `mcp.json`.
  - **Antigravity (AGY)**: JSON under `mcpServers` in `mcp_config.json` (`serverUrl` or `command`/`args`/`env`).
  - **Codex**: TOML tables under `[mcp_servers]`.
  - **Hermes**: YAML under `mcp_servers` in `~/.hermes/config.yaml`.
  - **OpenCode**: Typed local/remote MCP definitions in `opencode.jsonc`.

### 3. Slash Commands
- **Storage**: Prompt records under `slash-commands/commands/` with sync tracking in `slash-commands/sync-state.json`.
- **Harness Rendering**:
  - **Claude Code / OpenCode / Hermes**: Frontmatter Markdown files in `commands/`.
  - **Codex**: Custom prompt files in `prompts/` (`/prompts:` invocation prefix).
  - **Cursor**: Plaintext prompt files in `commands/`.

### 4. Hooks
- **Storage**: Event-driven hook records (`hooks/manifest.json`).
- **Canonical Events**: `pre_tool_use`, `post_tool_use`, `user_prompt_submit`, `session_start`, `stop`, `pre_compact`.
- **Canonical Tool Categories**: `shell`, `file_read`, `file_write`, `mcp`, `web`, `any`.
- **Harness Sync**: Translated to native event structures in `settings.json` (Claude), `config.toml` (Codex), `hooks.json` (Cursor/AGY), or `opencode.jsonc` (OpenCode).

### 5. Subagents
- **Storage**: Markdown files with YAML frontmatter (`name`, `description`, system prompt body) under `agents/`. Unrecognized frontmatter keys are preserved byte-for-byte on edit.
- **Harness Integration**:
  - **Claude, Cursor, AGY, OpenCode**: Installed via direct symlinks. Unrecognized frontmatter keys (`model`, `permissionMode`, `hooks`) are preserved on write.
  - **Codex**: Rendered into TOML agent files (`.codex/agents/*.toml`) carrying a `# harness-asset-manager:generated` header.

### 6. Permissions (Denylist-ONLY Model)
- **Storage**: Deny rules in `permissions/manifest.json`.
- **Supported Scope Types**: `shell` (command prefix), `file_read` / `file_write` (path globs), `web` (domain names), `mcp` (`server/tool` or `server`).
- **Denylist-ONLY Policy**: HAM operates exclusively as a **Denylist Manager**. `allow` and `ask` decisions are unsupported.
- **Harness Sync**:
  - **Claude Code**: Written into `permissions.deny` in `~/.claude/settings.json`.
  - **Antigravity (AGY)**: Written into `permissions.deny` in `~/.gemini/antigravity-cli/settings.json`.
  - **Codex**: Written into `[permissions.harness-asset-manager.filesystem]` and `[permissions.harness-asset-manager.network.domains]` as `"deny"` in `~/.codex/config.toml`.

---

## 3. Harness Catalog & Capability Bindings

Harness definitions are declared centrally in `harness_asset_manager/harness/catalog.py` in `SUPPORTED_HARNESS_DEFINITIONS`:

1. **Claude Code** (`claude`)
2. **Codex CLI** (`codex`)
3. **Antigravity** (`agy`)
4. **Cursor** (`cursor`)
5. **OpenCode** (`opencode`)
6. **Hermes Agent** (`hermes`)
7. **OpenClaw** (`openclaw`)

Every resource family resolves enabled harnesses dynamically from `catalog.py` and `settings.json`. Disabling a harness in Settings drops its column across all family matrices without requiring an app restart.

---

## 4. Storage Layout

HAM uses a local-first flat store. Each family owns a top-level directory; there is no
package layer (the `packages/<name>/` model was retired with the 2026-07-24 agents
rebuild, and `container.py` migrates any surviving `shared/` or `packages/local/`
directory into this shape on startup).

```
~/.harness-asset-manager/ (macOS) or $XDG_DATA_HOME/harness-asset-manager/ (Linux)
├── settings.json                       # Global settings, harness toggles, autoAdopt
├── configs/                            # Canonical native harness config baselines & snapshots
│   ├── claude/                         # .claude.json, settings.json
│   ├── codex/                          # config.toml
│   ├── agy/                            # mcp_config.json, settings.json, hooks.json
│   ├── cursor/                         # mcp.json, hooks.json
│   ├── opencode/                       # opencode.jsonc
│   ├── hermes/                         # config.yaml
│   └── openclaw/                       # openclaw.json
├── permissions/
│   └── manifest.json                   # Denylist permissions manifest
├── mcp/
│   └── manifest.json                   # Normalized MCP server records
├── hooks/
│   └── manifest.json                   # Canonical hook records
├── slash-commands/
│   ├── commands/                       # Slash command prompt files
│   └── sync-state.json                 # Target hash sync tracking
├── skills/                             # Skill packages, one directory each
├── skills-manifest.json                # Source & revision per skill package
├── agents/                             # Agent markdown definitions
│   └── conflicts/                      # Preserved copies when two harnesses diverge
├── bindings.json                       # Agent binding ledger (store/harness hashes)
├── agents-audit.json                   # Every automatic binding repair, for review
└── marketplace/                        # HTTP response cache (disposable)
```

Everything above is resolved from `data_dir` in `paths.py` — nothing hardcodes the
directory name. Only `marketplace/` is safe to delete; it is a cache and rebuilds.

### Native Config Snapshot Service
HAM captures canonical baselines and timestamped snapshots of user-level native harness config files under `configs/<harness_id>/`.
- **Triggers**: Pre-write (prior to HAM edits), External drift (detected via SHA-256 hash checks on startup), and Manual (`ham snapshot` CLI / Web UI).
- **Safety**: SHA-256 deduplication avoids storage bloat; automatic secret redaction masks API keys and tokens prior to export.
- **Atomic-Save Immunity**: Real files in native harness homes are preserved to prevent atomic `rename()` operations from severing file symlinks.

All file mutations use atomic writes (`atomic_write_text`) with flock file locks to ensure zero data corruption during concurrent operations.

---

## 5. Security & Request Guarding

HAM runs as a unauthenticated local daemon listening on loopback (`127.0.0.1`). Security is enforced via ASGI request middleware (`harness_asset_manager/api/guards.py`):

1. **DNS Rebinding Guard**: Rejects HTTP requests whose `Host` header does not resolve to a loopback address (`127.0.0.1`, `localhost`).
2. **CSRF Guard**: Rejects mutating HTTP requests (`POST`, `PUT`, `DELETE`, `PATCH`) from web browsers with non-loopback `Origin` headers.
3. **Remote Bind Protection**: Running serve with `--host 0.0.0.0` requires explicit `--allow-remote` flag.
