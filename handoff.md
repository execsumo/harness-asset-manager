# Handoff

Running status for in-flight work. Read this before resuming. Newest session on top.

---

## 2026-07-24 — One canonical harness order; disabled harnesses leave the matrices

**Landed on `main` and running.** Reported symptom: the Slash commands matrix led with
OpenCode, and OpenCode still had a column there despite being switched off in Settings.

### The ordering rule, now stated once

Harness order is **Claude, Codex, Antigravity, Cursor, OpenCode, Hermes, OpenClaw**, and
it lives in exactly one place: the declaration order of `SUPPORTED_HARNESS_DEFINITIONS`
in `skill_manager/harness/catalog.py`. Every family reaches it through
`bindings_for_family`, and `support_store.enabled_harnesses` preserves that order rather
than the settings file's — so reordering the catalog reorders Settings, Skills, MCP,
Hooks, Permissions, Agents, and Slash commands together.

**If you are adding a harness or changing order, edit the catalog tuple and nothing
else.** Slash commands used to keep its own curated `TARGET_ORDER`; that is what put
OpenCode first, and it is gone. Do not reintroduce a per-family order list.

### Disabled harnesses

`resolve_slash_targets` now filters out harnesses disabled in Settings, matching
`resolve_agent_targets`. Targets are also **re-resolved per call** (a plain callable
threaded into `SlashCommandReadModelService` / `SlashCommandMutationService`, mirroring
`resolve_agents_snapshot` at `container.py:295`), so a Settings toggle applies with no
restart. `migrate_legacy_slash_commands` deliberately keeps its one-shot build-time
resolve — it is a migration, not a read path.

Consequence, verified not assumed: a disabled harness also loses its review rows, but its
command files and sync records survive untouched and come back intact on re-enable.

### Two things the reorder exposed

1. **`_manage_entry` validated harnesses mid-loop.** Whether it rejected a missing install
   *before* creating any binding depended on which harness came first — Codex, by luck of
   the old catalog order. With Claude first it adopted Claude's copy and *then* raised on
   Codex, leaving a half-applied mutation. Fixed with a pre-flight validation pass.
   Knock-on: the managed package dir is ingested from `harness_sightings[0]`, so a skill
   found under different names in different harnesses is now named after Claude's copy.
   Existing managed skills unaffected; new manage operations only.
2. **The slash review matrix had a fallback** that synthesized columns from row order with
   `enabled: true` hardcoded — both bugs, in the reported view. It was unreachable
   (rows are empty whenever targets are) and is now deleted.

### Validation at completion, run independently of the delegate

typecheck clean · backend 347 + 146 · frontend 62 files / 263 tests · build clean ·
`codegen:check` clean. Three pressure tests run directly: all harnesses disabled yields a
well-formed empty payload; sync→disable→re-enable round-trips a file and its sync record;
a mutation against a disabled harness returns a clean 400.

**Delegation note:** agy did the per-call refactor competently, but `git commit --amend`ed
the orchestrator's HEAD commit instead of adding its own. Give it a separate worktree, or
tell it explicitly never to amend.

---

## 2026-07-24 — Agents rebuilt as a normal resource family

**Landed on `main` and running.** The compile/"hire" model shipped on 2026-07-13 (below)
is **retired**.
**`plan-agents-simplify.md` is the design of record** — read it first when resuming; it
supersedes `plan-agents-packages.md` decisions 2, 4, 6 and its Stages 2–4. The entries
below this one are left as the historical record of what actually shipped that day.

Why: agents had grown a bespoke capability-mapping + compiler model unlike every other
family. They are now a plain inventory with **In Use / Needs Review** views.

### Status — all merged to `main`

Suite at completion, run independently: typecheck clean, backend 347 + 144, frontend
263 across 62 files, build green. Run the app off `main`; rebuild `frontend/dist` and
restart after pulling, since the backend gained the agents router and the old
single-page `/agents` route is gone.


- **Pre-existing break fixed first (`b44b54a`).** `e1c9c41` had left `main` red:
  `McpNeedsReviewPage` referenced `copy.review.adoptSelected` / `.adoptingSelected`,
  which were never added to MCP i18n, and `McpServerMatrixView.test.tsx` still expected
  the old "Enabled" column label after the rename to "Active". Both fixed.
- **Backend rebuild — DONE (`8febf40`).** `"agents"` is a `FamilyKey` with a new
  `AgentFileBindingProfile`. Store/adapters/inventory/mutations replace `AgentsService`;
  `service.py` deleted along with all compile machinery.
- **Harness coverage corrected — branch `feat/agents-harness-coverage`.** The first cut
  shipped only claude+opencode from a curated `TARGET_ORDER`, which was wrong: Cursor,
  Codex, and Antigravity all have real subagent formats, and a hand-curated list would
  drift from Skills anyway. Columns now derive from
  `enabled_harness_ids_for_family("agents")` — same call the skills read model makes —
  and are resolved **per request**, so toggling a harness in Settings takes effect
  without a restart. Evidence per harness is tabulated in the amendment at the foot of
  `plan-agents-simplify.md`; claude and agy are probe-verified, the rest documented.
  Two accepted consequences: a generated marker returns **for Codex only** (it reads
  TOML, so its files are rendered, not symlinked, and get no drift detection), and
  Hermes keeps a column whose cells all read `unsupported` with a reason.
- **Ownership is a symlink**, mirroring skills. **Verified empirically**: a symlinked
  `~/.claude/agents/*.md` was picked up by a live headless `claude` session. No content
  hashes, no sync-state, no provenance marker, and no third "drifted" cell state.
- **Adopt conflicts are resolved by the user, never guessed.** A bare adopt on a
  store-name collision raises `AgentAdoptConflict` → **HTTP 409** carrying both paths;
  the client re-issues with `onConflict: keep_store | replace_store`. Bulk adopt skips
  conflicts and returns them in `skipped[]`.
- **Orphaned links surface as issues.** If a store file is deleted out from under a
  link, the agent has no inventory row left to hang a binding off, so the dead link is
  reported as an issue rather than silently disappearing.
- **Template/scaffold/docs — DONE** (agy delegate `agy-agents-scaffold`, independently
  verified). Agent frontmatter is now just `name` / `description` / optional `tools`;
  the parser ignores legacy `capabilities:` / `harnesses:` keys on read and drops them
  on write, so **no migration script is needed** and existing files keep working.
  `_rewrite_agent_local_prefix` deleted from `container.py` (the file move stays).
- **Frontend rebuild — IN FLIGHT** (agy delegate `agy-agents-fe`, worktree
  `../skill-manager-worktrees/agy-agents-fe`): flat `/agents/use` + `/agents/review`
  routes, sidebar NavGroup, overview card, `features/agents/public.ts`, and the
  `AdoptConflictDialog`. Structure copies Hooks; look and language copy Skills.

- **Detail view — DONE.** Clicking an agent opened `EditAgentDialog`, which populated
  from a placeholder (`setName(agentRef)`, everything else `""`) and wrote that back on
  save — renaming the agent to its slug and wiping description/prompt/tools. Replaced
  with a Skills-style detail modal (About → System prompt → Configuration → Harnesses →
  Locations, Edit/Delete footer) built on the shared `components/detail/` primitives.
  `GET /api/agents/{ref}` grew the fields it needs: raw document, store path, and a
  per-harness row with `state` / `path` / `installMethod`. Ported by an agy delegate
  against a contract I implemented and curl-verified **first** — that ordering is what
  stopped a third round of invented endpoints.
- **Frontmatter is preserved, not shrunk — DONE.** Second data-loss bug, same shape as
  the first: the writer re-rendered agent files from only name/description/tools, so
  every other key was deleted on save. Real Claude agents carry `model`, `effort`,
  `permissionMode`, `disallowedTools`, `skills`, `mcpServers`, `maxTurns`, `hooks`.
  Edits now merge into the original frontmatter; unrecognized keys survive byte-for-byte
  and are listed verbatim under **Configuration** in the detail view. Only
  `capabilities:`/`harnesses:` are still dropped. See the amendment at the foot of
  `plan-agents-simplify.md` — including the generalizable lesson, since this class of
  bug shipped twice.

### Frontend contract failures worth remembering

Two rounds of agy work passed their own DoD while being wrong on the wire, because the
frontend tests mock `fetch`:

1. Invented `/api/v1/agents` and `/bindings/{harness}` endpoints, and read `err.detail`
   when this API returns `{"error": ...}`.
2. After I corrected it to `/api/agents`, that doubled the base — `apiPath()` already
   prepends `/api` — producing `/api/api/agents` and 404ing on every call. The page
   tests missed it because they assert with `.includes("/enable")`, which passes for the
   doubled path too.

Fixed by `features/agents/api/client.test.ts`, which asserts the **fully composed** URL
(`toBe("/api/agents")`, not `includes`). Verified it fails against the broken client.

### Behavior change worth flagging

Compiled agents used to **inline full `SKILL.md` bodies** into the rendered artifact.
Deployed agents no longer carry skill text — both target harnesses resolve skills
natively.

---

## 2026-07-13 (evening) — Packages & Agents: plan locked, Stage 1 delegated

The "Agents & Packages" RFC was reviewed and revised; **`plan-agents-packages.md` is the
design of record** — read it first when resuming. Key amendments over the raw RFC:
packages *migrate* the legacy store (no parallel resolution paths), stable `SkillRef`
ids stay primary with `pkg/slug` as compile-time-pinned aliases, compiled artifacts get
provenance headers + drift detection, per-harness capability-degradation reports, no
hardcoded model ids, and cross-harness delegation runtime is cut from v1.

### Status

- **Stage 0 (scaffolding) — DONE**, committed on `main` (`64d08b2`, `898af8b`).
  Templates + `POST /api/scaffold`, writing into legacy store paths.
- **Stage 1 (package store + migration) — DONE, merged to `main` as `343fb9d`** (agy
  delegate, independently verified: typecheck, backend 316+133, frontend 269, build).
  Migration runs in `build_backend_container` (`_migrate_to_packages`); multi-package
  scan honors `active`; immutability guard in `SkillStore`. Known v1 nit: duplicate
  refs between two *non-local* packages are both retained (issue emitted; local-wins
  works). agy pane `wP:p4` + worktree `../skill-manager-worktrees/agy-package-store`
  kept alive for Stage 4.
- **Also on `main`:** upstream mode-io merge `0b54469` (came in mid-session from
  another agent) + `9224d79` fixing its artifacts (duplicate hermes mapper key,
  duplicate README Hermes cell, upstream png). Fork features verified intact.
- **Stage 2 (agents family + Claude compile) — DONE, merged as `5f8f808`.** Agents
  live in `packages/<slug>/agents/*.md`; `AgentsService` (scan/resolve/compile) in
  `skill_manager/application/agents/`; `GET /api/agents` +
  `POST /api/agents/{ref}/compile` (`dryRun`, `projectDir`); provenance marker +
  refuse-to-overwrite-foreign-files; OpenAPI regenerated. 11 new unit tests.
- **Stage 3 (cursor/codex targets + degradation reports) — DONE, merged as `dec09ae`.**
  Cursor → `<project>/.cursor/rules/skill-manager.<slug>.mdc` (projectDir required);
  Codex → `~/.codex/prompts/<slug>.md` (custom prompt; reported as degradation).
  Suite at merge: backend 330+133, frontend 269, typecheck, build — all green,
  independently run.
- **Stage 4 (agents UI) — DONE, merged as `076641a`** (agy delegate, independently
  verified: typecheck, frontend 272, backend 330+133, build). `/agents` route,
  sidebar entry, agent cards, Hire dialog with dry-run preview + degradation
  warnings + cursor projectDir gating. Note: agy's original commit regressed
  `handoff.md` from stale worktree state — stripped via amend before merge.
- **All four stages complete.** `frontend/dist` rebuilt on `main`. **Restart the
  running instance** — backend gained the agents router, and the packages migration
  runs on first container build (moves `data_dir/shared` → `packages/local/`;
  one-way, locked, idempotent).
- **Not torn down** (left intentionally): agy pane `wP:p4`, worktrees
  `../skill-manager-worktrees/{agy-package-store,agents-family}`, merged branches
  `delegate/agy-package-store`, `delegate/agy-agents-ui`, `feat/agents-family`.
- **Deferred (v1 cuts + follow-ups):** cross-harness delegation runtime; package
  deps; packages inventory UI view; agent-scoped MCP compilation; non-local vs
  non-local duplicate-ref policy (both retained today, issue emitted); drift
  detection surfacing for compiled artifacts (marker exists, no UI/API check yet).

### To resume mid-flight

1. Check `git branch -a` / agy's pane for `feat/package-store` progress; read the brief.
2. Independently run the validation gate before any merge:
   `npm run typecheck && bash scripts/test_backend.sh && npm test && npm run build`.
3. Continue at the first unfinished stage in `plan-agents-packages.md`.

---

## 2026-07-13 — Migrated Hermes to upstream's product-accurate impl (PR #51)

Replaced our speculative Hermes harness with upstream mode-io PR #51 (commit `4f085f8`),
landed on `main` as `3c9beb2` via a verified cherry-pick reconciled with fork-only work.

- **MCP now correct**: `~/.hermes/config.yaml` (YAML) under `mcp_servers`, no `type` field
  (standalone `HermesMapper`). Adds `ruamel.yaml`; `FileBackedMcpAdapter` mutates in place
  (`_ensure_subtree`) so YAML comments survive — **write path changed for all config-subtree
  MCP harnesses** (claude/cursor/codex/opencode), all re-tested green.
- **Skills**: categorized `~/.hermes/skills/<category>/<skill>/`, shared under `skill-manager`.
- **Hub-awareness**: reads `.hub/lock.json` + `.bundled_manifest`; excludes
  official/builtin/optional + self-learned; adopts only external-hub; `origin_harness` provenance
  threaded through the store manifest.
- **Home override**: `SKILL_MANAGER_HERMES_HOME` → `HERMES_HOME` → `~/.hermes`.
- **Kept fork-only**: our Hermes slash-command binding (still **provisional** — upstream omits it),
  `agy` harness, `hermes-logo.svg` (dropped upstream png).
- Resolves handoff item #2 for the **MCP shape** (now matches upstream's real formats). Still
  unverified against a live Hermes install; **slash commands remain provisional**. Hooks/permissions
  still unbound (items #1/#3 below).
- Verified independently: backend 309+133, typecheck, npm 269, build, openapi (no drift) — all green.

---

## 2026-07-12 — Hermes Agent harness + `~/` path display

### What shipped (done, validated, verified live)

- **Settings "Harness roots" no longer show `/skills`.** The label showed the managed
  *skills* root (e.g. `~/.claude/skills`); it now shows the harness root the app writes into.
  Done in the backend presenter (`skill_manager/application/settings/presenters.py`,
  `_harness_root_display` → `managed_location.parent`). The kernel's real `managed_location`
  is unchanged (the skills adapter and tests depend on it).
  - Note: Codex's skills root is `~/.agents/skills`, so it displays as `~/.agents` (a shared
    cross-harness dir), not `~/.codex`. That's the honest result of dropping `/skills`.

- **`~/` home abbreviation across all path displays.** Absolute home paths render as `~/…`
  everywhere: Settings storage + harness roots, MCP config paths, slash written/review paths,
  skill-detail locations. Implemented as a **frontend display-only** concern so API values stay
  absolute (keys, matching, and the MCP config-choice round-trip are unaffected):
  - `frontend/src/lib/paths/` — `formatHomePath()` util (+ test), `useFormatPath()`/`useHomeDir()`,
    `HomeDirContext` + `HomeDirProvider` (mounted in `App.tsx`, inside QueryClientProvider).
  - Home source: `homeDir` added to `GET /api/health` (`skill_manager/api/routers/health.py`).
  - `useHomeDir` reads context (default `null`), so path-displaying components still render in
    tests without a QueryClient — paths just pass through unabbreviated.

- **Hermes Agent added as a harness** (`skill_manager/harness/catalog.py`), CLI probe `hermes`,
  root `~/.hermes`. It is **catalog-driven, so it flows app-wide**, not settings-only. Verified
  live: appears in Settings, Skills inventory/detail, MCP inventory columns, and slash targets.
  - Skills: `~/.hermes/skills` (env override `SKILL_MANAGER_HERMES_ROOT`).
  - MCP: `~/.hermes/mcp.json`, subtree `mcpServers`, codec `hermes`
    (`HermesMapper(_TypedMcpServersMapper)` in `skill_manager/application/mcp/mappers.py`).
  - Slash: `~/.hermes/commands`, frontmatter Markdown. **Required extending the closed slash
    allowlist** — `SlashTargetId` Literal (backend `models.py` + `api/schemas/slash_commands.py`,
    frontend `api/types.ts`) and `TARGET_ORDER` in `slash_commands/targets.py`. This gap silently
    dropped Hermes from slash targets until fixed; regenerated `openapi.json`/`generated.ts`.
  - Logo: `assets/harness-logos/hermes-logo.svg` (+ `frontend/src/assets/...`), from lobehub,
    re-filled `#7d8590` (theme-neutral; logos render as `<img>` so `currentColor` won't inherit).

- Validation: `npm run typecheck`, `bash scripts/test_backend.sh` (300 + 127), `npm test` (269),
  `npm run build`, `npm run codegen:openapi` — all green.

### ⚠️ Incomplete — resume here

1. **Hermes hooks — NOT implemented (the main open item).** Hermes has no `hooks` binding, so it
   is correctly absent from the Hooks views. Deferred because hook config formats are
   harness-specific (each harness has its own event taxonomy + file shape) and Hermes' real
   schema is unknown. Reusing another harness's hook codec would write structurally-wrong config.
   **To finish:** obtain Hermes' actual hooks schema (event names, config file path, JSON/TOML
   shape), then add a `HookMapper` in `skill_manager/application/hooks/mappers.py` + register it,
   and add a `hooks` `ConfigSubtreeBindingProfile` to the Hermes entry in `catalog.py`.

2. **Hermes MCP + slash conventions are UNVERIFIED assumptions.** `~/.hermes/mcp.json`
   (`mcpServers` shape) and `~/.hermes/commands` (frontmatter Markdown) follow common
   cross-vendor conventions but have **not** been checked against a shipping Hermes build. If
   Hermes differs, correct the resolvers/codec in `catalog.py` (and `HermesMapper` if the MCP
   shape differs).

3. **Hermes permissions — no binding** (not requested). Add a `permissions`
   `ConfigSubtreeBindingProfile` + a `PermissionMapper` if/when wanted.

4. **Hermes not installed locally** → its skills/MCP/slash adapters have never run against a real
   Hermes install. Behavior is exercised only via the catalog wiring and unit/integration tests
   with a fake home. Validate against a real `hermes` CLI before trusting writes.

### Housekeeping

- **Nothing is committed.** Changes are in the working tree on `main`. Per `CLAUDE.md`, land via a
  short-lived branch off `main` → merge back → delete. Run the full validation suite before commit.
- **Restart the running instance** to pick up backend changes; `frontend/dist` is already rebuilt.
- `README.md` updated (Hermes row + provisional footnote). `README.zh-CN.md` was **removed** from
  this fork (not needed); its link was dropped from `README.md`.
