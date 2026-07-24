# Handoff

Running status for in-flight work. Read this before resuming. Newest session on top.

---

## 2026-07-13 (evening) — Packages & Agents: plan locked, Stage 1 delegated

The "Agents & Packages" RFC was reviewed and revised; **`plan-agents-packages.md` is the
design of record** — read it first when resuming. Key amendments over the raw RFC:
packages *migrate* the legacy store (no parallel resolution paths), stable `SkillRef`
ids stay primary, no hardcoded model ids, and cross-harness delegation runtime is cut from v1.

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
- **Stage 2 (agents family) — DONE, merged as `5f8f808`.** Agents
  live in `packages/<slug>/agents/*.md`; `AgentsService` in
  `skill_manager/application/agents/`; `GET /api/agents`; OpenAPI regenerated. 11 new unit tests.
- **Stage 3 (cursor/codex targets) — DONE, merged as `dec09ae`.**
  Suite at merge: backend 330+133, frontend 269, typecheck, build — all green,
  independently run.
- **Stage 4 (agents UI) — DONE, merged as `076641a`** (agy delegate, independently
  verified: typecheck, frontend 272, backend 330+133, build). `/agents` route,
  sidebar entry, agent cards. Note: agy's original commit regressed
  `handoff.md` from stale worktree state — stripped via amend before merge.
- **All four stages complete.** `frontend/dist` rebuilt on `main`. **Restart the
  running instance** — backend gained the agents router, and the packages migration
  runs on first container build (moves `data_dir/shared` → `packages/local/`;
  one-way, locked, idempotent).
- **Not torn down** (left intentionally): agy pane `wP:p4`, worktrees
  `../skill-manager-worktrees/{agy-package-store,agents-family}`, merged branches
  `delegate/agy-package-store`, `delegate/agy-agents-ui`, `feat/agents-family`.
- **Deferred (v1 cuts + follow-ups):** cross-harness delegation runtime; package
  deps; packages inventory UI view; non-local vs
  non-local duplicate-ref policy (both retained today, issue emitted).

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
