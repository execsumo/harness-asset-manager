# Harness Asset Manager — Architecture

This document describes the high-level architecture, domain model, harness catalog, storage layout, and security design of **Harness Asset Manager (HAM)**.

Contributor checklists for extending the product:

- [Adding an asset family](docs/adding-a-family.md)
- [Adding a harness](docs/adding-a-harness.md)

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
+---------------------------------------------------------------------------------+       +--------------------------------+
|                             FastAPI / Uvicorn Server                            |       |     Headless CLI (argparse)    |
|             Loopback Bind (127.0.0.1) + Loopback Host/Origin Guards            |       | harnessam skills|agents|mcp|…  |
+---------------------------------------------------------------------------------+       +--------------------------------+
                                       |                                                                  |
                                       +--------------------------+---------------------------------------+
                                                                  |
                                                          Domain Services
  (SkillsService, McpService, SlashCommandsService, HooksService, AgentsService, PermissionsService)
                                       |
                 +---------------------+---------------------+
                 |                                           |
        Store & Manifest Storage                 Harness Adapters & Mappers
     (~/.harnessam/)                          (Claude, Codex, AGY, Cursor, etc.)
                 |                                           |
    Atomic File Writes & Locks                    Harness Native Config Files
```

Both entry points build the **same** `BackendContainer` and call the same domain
services; the CLI does not proxy through HTTP, so it needs no running server. Stores
serialize concurrent writes with `flock`, which is what makes it safe to run the CLI
while the server is up.

---

## 2. Domain Model & Resource Families

Harness Asset Manager manages six core extension families:

### 1. Skills
- **Storage**: Portable Markdown skill folders (`SKILL.md` + scripts/resources) under `skills/<package>/`, with source and revision tracked in `skills-manifest.json`.
- **Harness Integration**: Installed via local filesystem links (`symlink`) into each harness's skills directory (`~/.claude/skills`, `~/.agents/skills`, `~/.gemini/antigravity-cli/skills`, etc.).
- **Hermes Support**: Categorized under `~/.hermes/skills/harnessam/`. Hub provenance is retained when available; bundled/official skills remain excluded, while other valid local or self-learned skills are discoverable and adoptable. The legacy `harness-asset-manager` category remains readable for migration.
- **Package contents**: The parser enumerates every file in a package to fingerprint it, so the relative-path list rides on the inventory entry and reaches the detail payload as `packageFiles` — no second walk. Adoption is `copytree` over the package directory and harness bindings are *directory* symlinks, so supporting material (`scripts/`, `references/`, `assets/`) round-trips intact.
- **Reads must not write**: `SkillsQueryService.inventory()` runs the reconcile pass, which can auto-adopt. Callers that only need to read go through `_inventory_snapshot()` — or `managed_skill_names()`, which the agents matrix uses to resolve skill display names. Resolving a name through `inventory()` made `GET /api/agents` able to mutate the skills store as a side effect of being read.
- **Frontmatter round-trip**: One parser, `document_utils.parse_skill_document`, reads every `SKILL.md` — `package.py` delegates to it rather than keeping a second flat copy, which used to hoist a nested block's keys to the top level. A parsed value containing a newline is a **verbatim block**: everything after the colon including its indentation, re-emitted unchanged, which is what lets nested maps, lists, lists of maps, and literal `|` scalars survive an edit. Scalars are re-quoted on write when plain emission would be invalid YAML; a value that merely looks like a flow collection is left alone, since quoting it would turn a list into a string. Folded scalars (`>`, `>-`) deliberately fold to one line — equivalent YAML, and it keeps long descriptions editable as a single field.
- **Spec conformance is advisory**: `skills/conformance.py` checks a Skill against the Agent Skills specification (`name` charset/length, `name` vs package directory, `description` presence/length) and returns issues phrased as corrections. It never gates a mutation: HAM keys Skills on the package directory and uses `name` for display, so enforcement would invalidate working Skills. `name_declared` is carried out of the parser so "no `name` field" is distinguishable from an unconventional one — `declared_name` falls back to the document's first heading, and reporting that as a charset error would name the wrong fix. Issues ride the list payload as well as the detail one, so the Overview builds its notices without a request per Skill.
- **Inventory Read Model**: Store and harness observations share a bounded, thread-safe package cache keyed by resolved package identity. Each snapshot uses one validation cycle, scans the store and adapters concurrently, and single-flights concurrent cache misses. Unchanged regular files are validated from topology and stat metadata without content reads; content-read file symlinks remain volatile across cycles, directory symlinks are never traversed, and invalidation during a build forces a fresh snapshot before publication.

### 2. MCP Servers
- **Storage**: Normalized JSON records in `mcp/manifest.json`.
- **Harness Translation**: Mapped by harness-specific codecs:
  - **Claude Code / Cursor**: JSON under `mcpServers` in `.claude.json` / `mcp.json`.
  - **Antigravity (AGY)**: JSON under `mcpServers` in `mcp_config.json` (`serverUrl` or `command`/`args`/`env`).
  - **Codex**: TOML tables under `[mcp_servers]`.
  - **Hermes**: YAML under `mcp_servers` in `~/.hermes/config.yaml`.
  - **Factory Droid**: JSON under `mcpServers` in `~/.factory/mcp.json`.
    HAM manages the personal/global file only; project `.factory/mcp.json` and
    plugin-provided MCP configurations are outside its boundary.
  - **OpenCode**: Typed local/remote MCP definitions in `opencode.jsonc`.

### 3. Slash Commands
- **Storage**: Prompt records under `slash-commands/commands/` with sync tracking in `slash-commands/sync-state.json`.
- **Harness Rendering**:
  - **Claude Code / OpenCode / Hermes**: Frontmatter Markdown files in `commands/`.
  - **Codex**: Custom prompt files in `prompts/` (`/prompts:` invocation prefix).
  - **Cursor**: Plaintext prompt files in `commands/`.
  - **Factory Droid**: Frontmatter Markdown files in `~/.factory/commands/`.
    Project `.factory/commands/` and plugin commands are not managed.

### 4. Hooks
- **Storage**: Event-driven hook records (`hooks/manifest.json`).
- **Canonical Events**: `pre_tool_use`, `post_tool_use`, `user_prompt_submit`, `session_start`, `stop`, `pre_compact`.
- **Canonical Tool Categories**: `shell`, `file_read`, `file_write`, `mcp`, `web`, `any`.
- **Harness Sync**: Translated to native event structures in `settings.json` (Claude), `config.toml` (Codex), `hooks.json` (Cursor/AGY), or `opencode.jsonc` (OpenCode).

### 5. Subagents
- **Storage**: Markdown files with YAML frontmatter under `agents/`. The standard contract fields are `name`, `description`, `model`, `effort`, `tools`, and `skills`; the system prompt remains the document body. Contract fields are parsed and rendered separately, never treated as custom metadata.
- **Fixed-vocabulary fields**: `effort` accepts only `EFFORT_VALUES` (`low`, `medium`, `high`) or an empty string that clears the key. The value set is declared once in `application/agents/model.py` beside `CONTRACT_KEYS`, mirrored by `EFFORT_VALUES` in `features/agents/api/types.ts`, and pinned against drift by `ContractKeyParityTests`. `validate_effort` guards every write path (create, managed update, unmanaged in-place update) and matches exactly — case variants are rejected rather than normalized, so no contract is invented that the picker cannot produce. `model` stays free text: its value set is genuinely open.
- **Attached Skills**: `skills` is an ordered list of adopted Skill slugs. Agent detail editing validates entries against the managed Skills inventory and offers the adopted Skills as suggestions. Saving an agent auto-enables each newly attached Skill on installed harnesses where that agent is enabled. Removing a Skill from the list does not disable its harness bindings.
- **Custom frontmatter**: Other keys are preserved verbatim and surfaced as configuration. They cannot overwrite standard contract fields through the custom metadata channel.
- **Harness Integration**:
  - **Claude, Cursor, AGY, OpenCode**: Installed via direct symlinks. Standard and custom frontmatter are preserved on write.
  - **Factory Droid**: Installed via direct symlinks into `~/.factory/droids/`; Droid frontmatter keys are preserved.
  - **Codex**: Rendered into TOML agent files (`.codex/agents/*.toml`) carrying a `# harness-asset-manager:generated` header.

### 6. Permissions (Denylist-ONLY Model)
- **Storage**: Deny rules in `permissions/manifest.json`.
- **Supported Scope Types**: `shell` (command prefix), `file_read` / `file_write` (path globs), `web` (domain names), `mcp` (`server/tool` or `server`).
- **Denylist-ONLY Policy**: HAM operates exclusively as a **Denylist Manager**. `allow` and `ask` decisions are unsupported.
- **Unlisted actions**: Adopting a denylist also switches each harness to its native no-prompt/auto-execute default, so only HAM-recorded deny rules stop execution. Claude uses `bypassPermissions`, Antigravity uses `always-proceed`, Codex activates an `approval_policy = "never"` workspace profile, and Cursor sets `approvalMode = "unrestricted"`.
- **Harness Sync**:
  - **Claude Code**: Written into `permissions.deny` in `~/.claude/settings.json`.
  - **Antigravity (AGY)**: Written into `permissions.deny` in `~/.gemini/antigravity-cli/settings.json`.
  - **Codex**: Written into `[permissions.harness-asset-manager.filesystem]` and `[permissions.harness-asset-manager.network.domains]` as `"deny"` in `~/.codex/config.toml`.
  - **Cursor**: Written into `permissions.deny` in `~/.cursor/cli-config.json` (global only, never the project-level `.cursor/cli.json`) as `Shell()` / `Read()` / `Write()` / `WebFetch()` / `Mcp()` tokens.
- **Codex limitation**: Codex's native permission profiles currently expose filesystem and network rules, not command-prefix deny rules; HAM continues to report Codex `shell` and `mcp` scopes as unsupported.
- **Cursor limitation and status**: `CursorPermissionsMapper` (`cursor-permissions` codec) is implemented and denylist-only (`Yes (Denylist)` in the Capability Matrix). Enabling a Cursor permission writes `approvalMode = "unrestricted"` into `~/.cursor/cli-config.json` and disabling the final rule cleans it up. Cursor's `Shell()` token only matches a single-word command (`commandBase` is documented as "the first token in the command line"), so multi-token shell patterns like `"git push"` are reported unsupported; `Mcp()` similarly only supports the full `server:tool` form, so a bare-server MCP pattern is unsupported too. Only Cursor's CLI (`cursor-agent`) is targetable — its IDE Agent reads a separate `permissions.json` (allowlist-only, `autoRun` documented as "best-effort convenience," no deny/enforcement surface) and stays permanently out of scope for this model.

---

## 3. Harness Catalog & Capability Bindings

Harness definitions are declared centrally in `harness_asset_manager/harness/catalog.py` in `SUPPORTED_HARNESS_DEFINITIONS`:

| # | Harness | Id | Support tier |
|---|---|---|---|
| 1 | Claude Code | `claude` | core |
| 2 | Codex CLI | `codex` | core |
| 3 | Antigravity | `agy` | core |
| 4 | Cursor | `cursor` | core |
| 5 | OpenCode | `opencode` | best effort |
| 6 | Hermes Agent | `hermes` | best effort |
| 7 | Factory Droid | `droid` | best effort |

Every resource family resolves enabled harnesses dynamically from `catalog.py` and `settings.json`. Disabling a harness in Settings drops its column across all family matrices without requiring an app restart.

### Support tiers

`HarnessDefinition.support_tier` (`harness/contracts.py`) declares how much support a harness is committed to. It is a statement about investment, not a property of the harness.

- **`core`** — every family the harness can support is implemented or verifiably impossible; behaviour is verified against a live CLI with the evidence recorded in `handoff.md`; a gap blocks a release.
- **`best_effort`** — kept working, not invested in; may ship on documented assumptions carrying a `support_note`; never blocks a release.

The tier is declared once and derived everywhere else, the same way column ordering is. `core_harness_ids()` is the single accessor. `tests/unit/test_harness_support_tiers.py` pins the core set and each core harness's family coverage, so a gap must be declared in `KNOWN_CORE_GAPS` with a justification rather than passing unnoticed; the CI job `core-harness-gate` runs it on its own for a fast, separately-named signal.

**OpenClaw (`openclaw`) was retired on 2026-08-09.** It declared only Skills and MCP, and its MCP writes were never implemented, so it was a skills-only integration carrying a column in every matrix. Its mapper, capability probe, binding profile, and logo are removed. Harness Asset Manager no longer touches `~/.openclaw`; pre-existing files there are left alone, consistent with only ever removing files it owns.

Factory Droid hooks and permissions remain intentionally unbound. Droid's
multi-scope hook configuration does not match HAM's canonical hook model, and its
allowlist/denylist/blocklist command settings do not match HAM's denylist-only
permission model.

---

## 4. Storage Layout

HAM uses a local-first flat store. Each family owns a top-level directory; there is no
package layer (the `packages/<name>/` model was retired with the 2026-07-24 agents
rebuild, and `container.py` migrates any surviving `shared/` or `packages/local/`
directory into this shape on startup).

```
~/.harnessam/ (macOS and Linux; explicit XDG overrides remain supported)
├── settings.json                       # Global settings, harness toggles, autoAdopt
├── configs/
│   └── manifest.json                   # Portable harness preferences (synced)
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
├── audit.log                           # Append-only journal for every mutation entry point
└── marketplace/                        # HTTP response cache (disposable)
```

Everything above is resolved from `data_dir` in `paths.py` — nothing hardcodes the
directory name. Only `marketplace/` is safe to delete; it is a cache and rebuilds.

### Configs family
`ConfigsService` extracts portable *preferences* from each harness's user-level config into
a single `configs/manifest.json`, which is synced rather than machine-local.

- **The row is the harness, not the preference key.** Unlike the other families, a config
  key is not an asset that exists independently and gets enabled in several places: of 81
  distinct keys observed across six harnesses, exactly one (`model`) appears in more than
  one. So the matrix is six harness rows and the keys live in the detail drawer.
- **The toggle means managed vs. not managed.** Enabling captures a harness's preferences;
  disabling drops the record from the manifest and **never writes to the harness's own
  config file**.
- **An absent config file is not proof of a stale record.** A harness managed on another
  machine looks identical to a leftover on this one, so a record whose file is missing
  reports `managed: false, hasRecord: true` and is surfaced for the user to remove
  deliberately. Deleting it automatically would destroy the other machine's state on the
  next sync.
- **Portability is a filter, not a list.** `configs/extraction.py` drops any key that is
  owned by another family (declared per harness as `exclusion_keys` on its
  `ConfigSubtreeBindingProfile` — one declaration, beside the binding it governs), looks
  like a secret, or carries an absolute path. The secret and path checks **recurse into
  nested values and mapping keys**, and a key failing on any branch is dropped whole: a
  partially-copied structure restored over a working one is worse than not managing it.
- **Restore merges; it never rewrites.** Only managed keys are written back, so unowned
  content survives, and a restore of an unchanged capture is byte-identical. This is why
  the manifest preserves the *insertion order* of preference values while sorting only its
  own top-level structure — alphabetizing them would rewrite the user's file on every
  restore.
- **Round-tripping is delegated, not reimplemented.** Reads and writes go through
  `config_document`, which re-emits untouched regions byte-for-byte in every supported
  format, so a restore rewrites only the managed keys.
- **Automatic capture yields on divergence.** The manifest crosses machines and the family
  keeps no local ledger, so `drift.classify_drift` has no baseline to arbitrate with. A
  local file that differs from the manifest is left alone for explicit resolution instead
  of being captured over another machine's edit.

All file mutations use atomic writes (`atomic_write_text`) with flock file locks to ensure zero data corruption during concurrent operations.

### Harness Config Documents

Every family that binds into a harness-owned config file (MCP, Hooks, Permissions) performs
the same whole-document read-modify-write: load the file, mutate one subtree, write the file
back. That makes the load/dump pair — not the per-family mapper — the place where a user's
configuration is preserved or destroyed, so it lives in exactly one module,
`harness_asset_manager/config_document.py`, which all three families import.

The invariant is the one the mappers already hold for unmodeled *fields* (see
`tests/unit/test_writer_round_trip.py`), extended to unmodeled *file content* — comments,
key order, and formatting:

| Format | Files | Round-trip mechanism |
|---|---|---|
| `toml` | `~/.codex/config.toml` | `TomlDocument` — a `tomlkit` parse kept beside a plain view; only changed keys are replayed onto it |
| `jsonc` | `~/.opencode/opencode.jsonc` | `JsoncDocument` — original text plus a span tree; untouched regions are re-emitted byte-for-byte |
| `yaml` | `~/.hermes/config.yaml` | `ruamel.yaml` round-trip mode |
| `json` | `settings.json`, `hooks.json`, `.claude.json`, … | `json.dumps` (no comments to lose) |

Two properties are load-bearing and pinned by
`tests/unit/test_config_document_round_trip.py`:

- **Comment stripping is string-aware.** JSONC comments are blanked by a scanning pass that
  tracks string and escape state, replacing comment bytes with spaces so *offsets are
  preserved* — the span tree can index the original text, comments included. The regex this
  replaced was string-unaware: a value containing `//` truncated the document into a hard
  parse failure, and a value containing `/*…*/` or `, }` was silently rewritten.
- **Callers never see library wrapper types.** `tomlkit` converts values on insertion, so a
  mapper that appends a `dict` and then mutates its own reference writes nothing. Documents
  therefore hand out plain `dict`/`list` values — the semantics the mappers were written
  against — and reconcile at dump time. Every returned document is a `dict` subclass, so
  `isinstance(value, dict)` branches in mappers keep working.

Comment preservation is verbatim *outside* any subtree HAM rewrites, and best-effort within
one. `tomli-w` is still used for files HAM itself generates (Codex agent TOML, store
metadata), where there is no user formatting to protect.

### Store Portability

The store is designed to be carried between a user's own machines with dotfile/folder
synchronization tools. Three properties make that safe, all enforced in
`harness_asset_manager/portable_paths.py` and the persistence layer:

1. **No device-local absolute paths in load-bearing records.** `bindings.json` targets and
   slash-command sync-state paths persist home-relative (`~/...`) and re-resolve against the
   current `$HOME` on load. Legacy absolute paths still parse when they resolve under this
   machine's local roots (HOME, process XDG base dirs, resolved store base dirs); an absolute
   path from a *foreign* machine degrades to no-record rather than misclassifying local
   files.
2. **Total reads.** Every persisted-state reader survives absent, truncated, or malformed
   JSON — what folder sync produces when it replicates mid-write — by degrading to the
   default value plus a surfaced issue where the store has an issue channel. Losing state
   degrades to "no baseline", never to a crash and never to a destructive default.
3. **Sync-artifact tolerance.** `is_sync_artifact()` keeps conflict copies (`name (conflict
   copy)`, `*.sync-conflict-*`), editor backups, temp files, and dotfiles out of skills/
   agents directory scans and out of auto-adopt eligibility: they may surface as unmanaged,
   but are never adopted and never break scanning.

On startup HAM seeds a default `.gitignore` into the store root (only if absent) suggesting
the standard exclusions (`marketplace/`, journals, locks, runtime state, and `configs/*`
except the portable `configs/manifest.json`). Intent
travels with the synced store; placement (symlinks, rendered harness files) is recomputed
locally per machine when assets are enabled. Secrets in MCP `env`/`headers` values and hook
commands live in the manifests and therefore travel too — documented as a trust boundary,
not enforced.

### Mutation Audit Journal

The HTTP API and headless CLI share the same audited domain-service wrappers. Each
mutation appends one JSON Lines event to `audit.log` with a UTC timestamp, family,
operation, safe identifiers, outcome, and the paths whose filesystem state changed.
Failed and partially applied operations are recorded as distinct outcomes. The journal
never serializes prompt bodies, config objects, environment values, or exception
messages; failures carry only the exception type. Automatic agent reconciliation uses
the same wrapper when it actually changes a path, while its richer repair detail remains
in `agents-audit.json`.

The journal is append-serialized with `flock`. An audit-write failure does not turn an
already-completed config mutation into an apparent failure, which avoids unsafe retries.
`audit.log` is the authoritative activity record and is backend-only: there is no HTTP
endpoint or UI surface for it. The former `GET /api/activity` endpoint and the read-only
Activity page were removed; the journal remains in place for traceability and support
diagnostics.

---

## 6. Frontend Architecture

The SPA (`frontend/src`) is feature-sliced: every family lives under `features/<family>/`
(`components/`, `screens/`, `model/` selectors, `api/`, `i18n.ts`, `routes.tsx`), with
cross-family primitives in `components/matrix/`. State is TanStack React Query over the
generated API client; the client is regenerated from OpenAPI and kept drift-free by a
`codegen:check` gate.

### Overview hierarchy

The Active-harnesses table is the object of the Overview page and keeps the solid panel
treatment. Everything below it is explicitly secondary: **Needs correcting** renders one
notice per conformance issue — asset, correction, and a link to that asset's detail
drawer, because a count leaves the reader to go find the thing themselves — and **Review
to Adopt** is recessed (transparent ground, muted heading, small count chips, brightening
on hover) because a standing backlog is not an alert. Deep links from these panels use
canonical routes, never the legacy `/<family>/use` redirects, which drop the query string.

### One unified page per family

Each family has exactly one canonical "In use" route listing managed **and** unadopted items,
with URL-backed status filter pills (`?status=needs-review`, `?status=untracked`). Legacy
per-view routes (`/mcp/review`, `/mcp/unmanaged`, …) are redirects onto the canonical route's
filters. Single-link sidebar groups render their heading itself as a direct link carrying the
family count; only multi-page groups (Marketplace) keep a collapsible sub-tree.

Every family page also honours a URL-backed `?harness=<id>` filter that restricts the list to
items actually present on that harness — skills with an `enabled`/`found` matrix cell (a
plainly `disabled` cell means merely adoptable), agents with an `enabled` binding, slash
commands with a `synced` sync entry, and MCP/hooks/permissions with any observed sighting.
The Overview page's Active-harnesses table is the primary producer of these deep links: each
coverage cell links to the harness-filtered capability surface, and its `+N` review detail
links to the harness-filtered needs-review view. A leading All-harnesses totals row shows
catalog-level counts per capability and links to the unfiltered surfaces. An active
`?harness=` filter renders a dismissible chip in the page's FilterBar and participates in
"Clear filters".

### Shared matrix component system

All five family matrices are built from `components/matrix/` (`MatrixTable`,
`MatrixSortableHeader`) and follow one set of conventions:

- The identity header is the family name (Skill / Agent / Slash Command / MCP Server / Hook /
  Rule), styled like the Active coverage header — not "Name".
- Every column is sortable: name asc/desc, per-harness cell state, and coverage/Active, via a
  per-family `sort*Rows` selector in that family's `model/selectors.ts`.
- Column widths are uniform: harness 52px / compact 140px / coverage 96px; compact responsive
  logo stacks stand in for wide columns on narrow viewports.
- Rows carry a leading select checkbox. Managed rows selected → bulk action bar (apply /
  remove everywhere / delete, with confirm dialog); untracked rows → a bulk-dock Adopt bar.
  Families with the full managed-row bar (Skills, MCP, Permissions) also get a **Tag** action
  (`BulkTagPopover`): staged multi-tag input with existing-tag autocomplete, merged into each
  selected asset's tags via the family's per-asset replace-set endpoint. Unmanaged rows render
  inline with no special tint, identically across families.

### Enabled-and-detected column filtering

Harness toggle columns include only harnesses that are enabled in Settings **and detected**
(installed, or config file present). The filter is applied at the inventory presentation
boundary only — `_active_scans` for MCP/hooks/permissions, detection filters for skills,
agents, and slash commands — so reconcile paths, mutation gating, and planner endpoints see
the full scan list. Disabling a harness in Settings drops its column everywhere without a
restart.

---

## 5. Security & Request Guarding

Harness Asset Manager enforces a multi-layered security model tailored for local-first execution with secure remote access:

### Trust Boundary

1. **Same-User Local Access (Loopback Peer)**:
   - Requests whose client address originates from loopback (`127.0.0.1`, `::1`) are trusted automatically without requiring tokens or credentials.
   - *Rationale*: A local process running under the same user UID already possesses read/write access to the user's filesystem, environment variables, and process memory. Defending against same-user local access would introduce friction without genuine security boundaries.
2. **Remote Access Boundary**:
   - Non-loopback requests to `/api/*` (exempting unauthenticated `/api/health`) must satisfy **at least one** of:
     - **Tailscale Identity Header**: A non-empty `Tailscale-User-Login` header injected by Tailscale Serve (which strips client-provided headers to prevent spoofing).
     - **API Bearer Token**: An `Authorization: Bearer <token>` header matching the persistent secret stored at `~/.harnessam/api-token` (written with strict `0600` permissions) or overridden by `HARNESSAM_API_TOKEN`.
   - Any remote request failing all rules is rejected with `401 Unauthorized` and `WWW-Authenticate: Bearer`.

### Request Guards (`LoopbackOnlyMiddleware`)

To protect browsers from cross-origin exploits when accessing the daemon:
- **DNS Rebinding Guard**: Rejects HTTP requests whose `Host` header is neither loopback nor explicitly registered via `--trusted-host <host>`.
- **CSRF Guard**: Rejects mutating HTTP requests (`POST`, `PUT`, `DELETE`, `PATCH`) from web browsers whose `Origin` header is neither loopback nor registered in `--trusted-host`.
- **Reverse Proxies & Tailscale Serve**: Pass `--trusted-host <tailnet-or-proxy-hostname>` to permit the proxy's `Host` and `Origin` headers while keeping DNS rebinding and CSRF guards fully active. `--allow-remote` is retained for backwards compatibility when binding non-loopback interfaces without request guards.
