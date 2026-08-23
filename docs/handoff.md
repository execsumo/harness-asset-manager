# Handoff

Running status for in-flight work. Read this before resuming. Newest session on top.

## 2026-08-23 — Hooks rows simplified (event / command); ⚠ agy is working IN this checkout

**⚠ Checkout state warning:** the delegated `feat/asset-tags` work (agy, pane wA:p17) is being
implemented **in this shared checkout**, which is currently switched to `feat/asset-tags` with
large uncommitted changes — NOT on `main`. Do not reset/switch branches here until agy's work
lands; do not trust "run app off main" assumptions for this tree until then. The running
server's `frontend/dist` was rebuilt from `main` (`1cf3a98`) and copied in manually.
Incident note: a same-checkout ff-merge briefly moved the `feat/asset-tags` ref; it was restored
via `git update-ref` without touching files. **Future delegation must give agy its own worktree**
(`git worktree add ../ham-<task> origin/main`) so this never recurs.

**Hooks row simplification** (`main` @ `1cf3a98`, pushed): per owner dog-fooding feedback,
hooks matrix rows now render line 1 = event only (e.g. `pre_compact`) and line 2 = command;
the old identity cell showed the dense server-side composite `event · match: command`
(`_display_name` in hooks/inventory.py). Frontend-only change in `HooksMatrixView.tsx` with
test updates + a new regression test pinning event-as-heading; falls back to `displayName`
when no spec parses. Note `match` no longer shows on the row (it was almost always `any`) —
it remains in the detail view; flag if that hurts. Validation: typecheck clean, Vitest 323/323
across 66 files, build OK, backend 598 unit + 205 integration OK (run on agy's tree).

## 2026-08-23 — Next feature decided: asset tags with a pinned `starred` system tag

Plan of record: [`docs/plan-asset-tags.md`](plan-asset-tags.md). Decision: one tagging
mechanism (sidecar `data/asset-tags.json`, family-generic keys, portable-store invariants
apply), with `starred` surfaced as a pre-listed system tag / one-click star toggle. Phase 1 =
Skills only; later phases generalize to the other families. Not started yet — next substantial
implementation work, delegated per §7 of the plan.

## 2026-08-23 — Unmanaged agents are now editable in place (harness file rewritten directly)

Follow-on to the read-only unmanaged detail fix (entry below). Clicking into an unmanaged
agent and editing it now works: `PUT /api/agents/<harness>/<slug>` dispatches slashed refs to
`AgentMutationService.update_unmanaged`, which parses the harness Markdown file, re-renders it
with the managed path's frontmatter contract, and writes atomically in place. Omitted fields
carry forward (`prompt`/`tools`/custom frontmatter are never wiped by a partial update — that
data-loss risk existed in the first WIP cut and was fixed before landing). Rendered adapters
(Codex TOML) stay refuse-to-edit (`can_edit=false`); adopt-first is required there. Guards:
unsafe slug → 404, missing file → 404, symlink target → 404 (already-managed binding).

Bonus fix found during review: unmanaged Codex TOML detail inspection had been 404-ing because
`_unmanaged_detail` ran Markdown frontmatter parsing on rendered adapters; it now branches on
`adapter.renders` and parses TOML, keeping `can_edit=false`.

Frontend unchanged beyond the WIP commit (DocumentSection already supported preview-only mode;
the Locations note keys off `storePath`). Delegated to agy via herdr (branch
`feat/unmanaged-agent-edit`: WIP `b3eab9a` by owner, fixes `4175087` + tests `fa3574a` by agy),
independently verified — full suite re-run by owner — then fast-forward merged to `main` and
pushed; branch deleted. Validation: typecheck clean; backend 588 unit + 203 integration OK at
81% branch coverage; Vitest 322/322 across 66 files; build passes. New coverage: unit tests for
in-place rewrite with custom metadata, omitted-field preservation, unsafe/missing/symlink/rendered
refusals; integration tests incl. an end-to-end lifecycle (unmanaged edit → adopt → managed edit).

## 2026-08-23 — Launch pattern: real store vs `--state-dir`; tailnet relaunch; inline document editing shipped; unmanaged agent details fixed

### Relaunching the app — READ THIS FIRST

**The running instance must use the REAL store (`~/.harnessam`), which means NO `--state-dir`.**
`--state-dir` is a full isolation override: it relocates config, data, AND runtime state
to the given directory (`paths.py::_base_dirs`). Launching with
`--state-dir .artifacts/runtime` (as `scripts/start-dev.sh` does — it exists for sandboxed
dev/CI runs) silently points the app at an empty scratch store: the Overview showed zero
assets and all 73 skills "disappeared". Nothing was lost; the store was just invisible.

The correct production/local launch (also what serves over tailnet):

```bash
./.venv/bin/python -m harness_asset_manager start \
  --host 0.0.0.0 --port 8000 --allow-remote --no-open-browser
```

- `--allow-remote` is required for any non-loopback `--host` and also relaxes the loopback
  Host/Origin guards so tailnet peers can reach it. The API is UNAUTHENTICATED — tailnet-only,
  never funnel/public.
- Tailnet URL: `http://vibebox.goose-marlin.ts.net:8000/` (Tailscale IP `100.119.233.79`).
- One process serves API + built SPA; rebuild `frontend/dist` (`npm run build`) after any
  frontend change, then restart.
- Stop with `bash scripts/stop-dev.sh`. Note: `start` refuses to double-start via runtime
  state in the (omitted) state dir — if stop says "not running" but the port answers, kill
  the pid from the previous launch directly.
- Verify after launch: `/api/health` must report `"homeDir": "/home/dev"` (i.e. `~/.harnessam`),
  NOT `.artifacts/runtime`, and `/api/skills` summary should show ~73 managed.

### Inline document editing in detail views (delegated to agy, merged)

Skills, Agents, and Slash Commands detail views now have a universal Document section
(Preview|Edit) with a structured frontmatter editor — known fields as labeled inputs per
family (agents: name/description/tools; skills: name/description; slash: name locked +
description), all custom/user-added frontmatter keys as order-preserving editable rows,
optional raw-YAML mode, dirty-state Save/Cancel with an unsaved-changes discard guard.
The agents modal Edit dialog was removed in favor of inline editing. Branch
`detail-editing` (7 commits), independently verified then merged to `main` and pushed.

Backend: new `PUT /api/skills/{ref}/document` (atomic write, inventory invalidation);
agent update requests carry ordered extra-frontmatter `metadata`; slash-command codec passes
custom frontmatter lines through verbatim. OpenAPI regenerated. Owner review caught one real
data-loss bug before merge: the skills endpoint silently dropped ALL frontmatter when a
request omitted `metadata` — fixed to carry current frontmatter forward (mirroring the agents
contract), regression-tested at the integration level (`78445a5`).

### Unmanaged agent details fixed (owner, this session)

Clicking details on an unmanaged agent (ref `<harness>/<slug>`) always failed with
`unsafe agent ref` — pre-existing: the route handed the namespaced ref to `AgentStore.path_for()`,
which correctly rejects path separators. Managed agents were unaffected; the owner's agents are
all unadopted droid entries, which is why every click failed. Fix:

- `AgentsInventory.detail()` now dispatches slashed refs to `_unmanaged_detail()`: parses the
  harness file read-only, returns detail with `storePath=null`, `canEdit=false`,
  `canDelete=false`, plus a note pointing at Adopt. Per-harness row logic extracted into
  `_harness_rows()` shared by both paths. `AgentDetail.store_path` is now `Path | None`;
  response schema gained nullable `storePath` and `canEdit` (OpenAPI regenerated).
- Frontend: `DocumentSection` gained `editable=false` mode (preview-only, no toggle/save bar);
  agent locations section hides the store card when there is no store copy and lists the owning
  harness's file path instead.
- Regression tests in `tests/integration/test_agents_routes.py` (read-only inspection shape;
  unsafe/missing refs → 404).

Validation on the final tree: typecheck clean; backend 583 unit + 197 integration OK; Vitest
322/322 across 66 files; build passes; codegen check clean once the regenerated files are
committed. Server relaunched from merged tree against the real store; unmanaged agent detail
verified live over HTTP.

## 2026-08-22 — Overview redesigned around the Active-harnesses table; coverage cells deep-link

Two commits on `main` (`7c77bed`, `ae3d9e2`). The Overview page is now action-first:

- **Statistics band removed** — the "in use" mega-sum (skills + commands + MCP + hooks +
  permissions + agents) was a vanity metric; its detail line duplicated the Extensions
  section, and "N observed" duplicated the harness table's row count.
- **Extensions portfolio + Discover panel collapsed** into a compact Shortcuts strip
  (`QuickLinks.tsx`, manage/discover chip groups) beside the promoted Review queue.
- **Active harnesses is the full-width centerpiece**: per-harness coverage for all six
  capabilities from every inventory — skills matrix cells, slash-command `syncTargets` /
  `reviewCommands`, MCP/hooks/permissions sightings, agent bindings — plus a cross-capability
  review column and writability warnings for MCP, hooks, and permission writes
  (`OverviewHarnessRow.cells` / `.availabilityIssues` in `capability-registry/overview.ts`).
- **Coverage cells deep-link**: active count → `/skills?harness=<id>`-style capability view;
  `+N` review detail → the `?status=untracked&harness=<id>` review view. Route map lives in
  `coverageCellLinks()` (canonical routes only — legacy `/skills/use` etc. redirects drop
  query params). Review-column total is intentionally not a link.
- **All six family pages honour URL-backed `?harness=`** via their selectors; active filter
  renders a shared `HarnessFilterChip` in each FilterBar and participates in Clear filters.
  Documented as a convention in ARCHITECTURE §6; README Product Tour updated.

Validation (both commits): typecheck, backend suite, Vitest (314/314 across 64 files),
eslint clean on touched files, production build with `frontend/dist` rebuilt — all green.

## 2026-08-22 — Deep-link filter semantics fixed; All-harnesses totals row

Follow-up to the Overview redesign after live use:

- **Bug: `?harness=` filters matched too much on three pages.** The predicates counted
  assets that merely *could* be on a harness: skills cells are `"disabled"` on every
  detected harness unless enabled (`cell_state` in `application/skills/policy.py`), agent
  bindings default to `"disabled"` on all installed targets, and slash-command
  `syncTargets` carries a `"not_selected"` entry for every target. Predicates now require a
  real tie: skills cell state `enabled`/`found`, agent binding `enabled`, sync entry status
  `synced`. MCP/hooks/permissions sightings only exist where observed, so they were already
  correct. Selector tests updated to pin the stricter semantics.
- **All-harnesses totals row** added as the first row of the Active-harnesses table:
  catalog totals per capability (managed counts + unadopted/drift review), independent of
  any single harness's adoption. Its cells link to the unfiltered capability surfaces
  (`coverageCellLinks(cellKey)` with no harness). Rendered by `TotalsRow` in
  `HarnessCoverageMap`; modelled as `OverviewModel.totalsRow`.

Validation: typecheck, Vitest (full suite), production build with `frontend/dist` rebuilt —
all green.

## 2026-08-22 — Activity page/view removed; backend audit journal retained

The user-facing Activity surface is gone; the backend activity log stays.

- Deleted `frontend/src/features/activity/` (page, queries, API client, styles, i18n,
  tests), the `/activity` route in `App.tsx`, the sidebar link + `activity` icon key,
  and the `nav.activity` / `loading.activity` copy keys.
- Removed the `GET /api/activity` endpoint (`routers/activity.py`,
  `schemas/activity.py`) and `tests/integration/test_activity_api.py`; regenerated
  `openapi.json` / `generated.ts` via `npm run codegen:openapi`.
- **`MutationAuditJournal` is untouched** — every mutation still appends to
  `data/audit.log`. The journal is now backend-only (no HTTP endpoint, no UI) and
  remains the traceability/support-diagnostics record. ARCHITECTURE §5 updated
  accordingly; `plan-auto-adoption.md` wording fixed ("shared Activity journal" →
  "mutation audit journal"); shipped-batches list in RECOMMENDATIONS notes the removal.
- App test now asserts the Activity sidebar link is *absent*.

Validation: typecheck, backend suite (579 unit + 191 integration OK), frontend vitest
(310/310), production build — all green. Commit `60b1a02` pushed to `main`.

## 2026-08-22 — Backlog sweep: root pointers deleted, sync plan retired, stale items closed

All remaining open items resolved by owner decision; nothing left in the backlog.

1. **Root plan pointers deleted** (`RECOMMENDATIONS.md`, `plan-agents-packages.md`,
   `plan-agents-simplify.md`, `plan-auto-adoption.md`, `plan-cross-device-sync.md`). The
   `stash@{0}` decision is finally committed: the docs/ copies remain canonical; the root
   pointers are gone for good.
2. **`docs/plan-cross-device-sync.md` deleted entirely.** No in-app sync transport will be
   built — carrying the store between a user's own machines via dotfile/folder replication
   is *the* supported workflow, documented in README ("Carrying the store between your own
   devices" + "Store Portability" in ARCHITECTURE §4) and in the portable-store entry below.
   The README's "Cross-device sync — planned" roadmap section was replaced with a short
   note pointing at that workflow.
3. **Vitest worker I/O stall item dropped** without root-causing: it has not reproduced in
   many sessions. Reopen only if it returns.
4. **Per-family single-flight reconcile locks dropped**: agreed unnecessary — the 2026-08-21
   audit found no correctness gap (409 races skipped benignly, file-locked writes), and the
   mutation-path pressure test showed no latency concern. Agents' `lock_path` remains the
   template if reconcile cost ever matters.

## 2026-08-22 — Mutation-path pressure test passed; perf follow-ups closed

Closed handoff items 1–3 from the 2026-08-21/18 entries (pressure-test, conditional
optimization, justification for further work). Restarted the server from `main`
(dist already matched) on :8000 with `--allow-remote`; tailnet URL live as before.
Owner exercised the real mutation path from the UI: adopting a skill and toggling its
harness bindings were **snappy** — no observable post-mutation lag, no waterfall worth
tracing further.

Consequences:
- **No optimization work** on audit snapshots or frontend refetches — the trace did not
  justify it (item 2's condition failed in the good direction).
- The **end-to-end latency regression check** (old item 3) is downgraded to optional:
  there is no observed latency problem to guard against anymore. Only revisit if a
  future change makes mutations slow again.
- Note recorded for posterity: concurrent GETs during auto-adopt serialize behind the
  adoption lock (longer tail latency vs the pre-fix early-return), confirmed expected.

Still open, unchanged priority: `stash@{0}` root-pointer decision; Vitest worker I/O
stall root cause (still unreproduced); `plan-cross-device-sync.md` §4 "never travels"
column is stale post-portable-store; per-family single-flight reconcile locks remain
deferred hardening (no correctness gap).

## 2026-08-22 — `~/.harnessam` made portable for dotfile-sync between devices

Decision: **no in-app sync feature will be built.** The owner will carry the store between
their own machines with a dotfile/folder-replication tool. That inverts
`plan-cross-device-sync.md` §4's assumption (some files "never travel") — with folder sync
everything travels, so the store itself had to be hardened: nothing load-bearing may be
device-local, and readers must tolerate partial/foreign state fail-safe. Implemented by agy
(delegated via herdr, branch `feat/portable-store`, 6 commits), independently verified:
diff spot-check caught a real bug in agy's work (fixed in `970a5d3`, see below); full suite
re-run on merged `main`. Merged as `344d42e`; branch deleted.

### What shipped

- **Portable path persistence** (`ecfcdfb`): new `harness_asset_manager/portable_paths.py`.
  `bindings.json` targets and slash-command sync-state paths now persist home-relative
  (`~/...`) and re-resolve against the current HOME on load. Backward compatible: legacy
  absolute paths under the current machine's roots still parse; absolute paths from a
  **foreign** machine degrade to no-record instead of poisoning broken-binding
  classification.
- **Total reads everywhere** (`9a3c004`): `SlashCommandSyncStateStore.load()` and MCP's
  `_load_manifest_result()` previously called `json.loads` uncaught — a truncated file (what
  folder sync produces when it replicates mid-write) crashed every read of that family.
  Both now degrade to default + surfaced issue, matching the agents-ledger/hooks/permissions
  pattern. Skills manifest loader verified/made total.
- **Sync-artifact tolerance** (`443745f`): `is_sync_artifact()` filters conflict copies,
  editor backups, temp files, dotfiles out of skills-store/agents-dir scans and auto-adopt
  eligibility — a Syncthing `name (conflict copy)` file can surface as unmanaged but is
  never auto-adopted and never breaks scanning.
- **Arrival pinned by tests** (`b9eb633`): `tests/unit/test_cross_device_arrival.py` moves a
  populated store between two synthetic homes with different layouts and asserts inventory
  survives, missing bindings report cleanly, foreign ledger entries don't misclassify, and
  no false drift appears.
- **Docs + store `.gitignore`** (`67e8a80`, aligned in the follow-up docs pass): README
  section under Local-first Safety ("carrying the store between your own devices": what
  travels, what to exclude — `marketplace/`, `audit.log*`, locks, runtime files, `configs/`;
  secrets note). HAM writes a default `.gitignore` into the store root on startup (only if
  absent); the follow-up pass added the missing `audit.log`/`marketplace/`/`configs/`
  entries so the seeded file matches the documented exclusions. ARCHITECTURE.md §4 gained a
  "Store Portability" subsection pinning the three invariants (no device-local paths, total
  reads, artifact tolerance).
- **Post-review fix** (`970a5d3`, owner): agy's foreign-path guard used a name heuristic
  (`base_home.name == "home"`) that fires on *every standard Linux machine*, admitting a
  foreign `/home/alice/...` as local. Replaced with an explicit `extra_local_roots`
  parameter plumbed from the container (resolved XDG **base** dirs + HOME). The first cut
  passed HAM's own store subdirs, which broke slash-command auto-adopt in integration
  (harness files live in *sibling* dirs of `$XDG_CONFIG_HOME/harnessam`) — caught by
  re-running the full suite, root-caused, fixed, regression-tested.

### Validation

Backend 579 unit + 193 integration pass; typecheck clean; Vitest 314/314 across 64 files;
build passes; dist rebuilt from merged `main`; server restarted and healthy on :8000.
Pushed to `origin/main`.

### Notes for future sync-adjacent work

- `plan-cross-device-sync.md` remains the design of record for a future in-app transport,
  but its §4 "never travels" column is now stale in practice: everything travels safely.
- Secrets (MCP `env`/`headers` values, hook commands) live in the manifests and therefore
  travel with a dotfile repo — documented as trust-boundary advice rather than enforced.

## 2026-08-22 — Permissions page converged; matrix dead code removed; docs caught up

The last family still on its own design was converged. Commits `5befc6b`..`09b2d7b` (frontend +
docs only — no backend/API changes), all on `main`, pushed to `origin/main`. This entry also
closes the doc pass: README and ARCHITECTURE.md were audited against current behavior and
updated where stale.

- **Permissions matrix standardized** (`5befc6b`): page title/subtitle, search copy, status
  filter pills, and Adopt button now come from feature i18n (title drops the "in use" suffix);
  `MatrixSortableHeader` throughout with a new `sortPermissionsRows` selector mirroring
  hooks/MCP ordering (name / coverage / per-harness state); coverage aria-labels and column
  widths aligned to the shared convention.
- **Per-row checkboxes with bulk actions** (`689d740`): managed rows selected → BulkActionBar
  (Apply everywhere / Remove everywhere / Delete with confirm dialog) driven by the existing
  set-harnesses and uninstall mutations; untracked rows → bulk-dock Adopt bar like Hooks/MCP.
  Selection is per row id and cleared when filters or inventory change.
- **Untracked-row tint dropped** (`e1e71ac`): permissions was the only family styling unmanaged
  rows with a warm accent/tint; removed so all five families render unmanaged rows identically.
- **Dead code orphaned by standardization removed** (`a49c292`): `MatrixHarnessHeader` deleted
  (no view uses it since every matrix moved to `MatrixSortableHeader`; its `--header` class had
  no CSS rule), `MatrixTable`'s ignored `hasCheckboxColumn` prop dropped (views render their own
  checkbox columns), and permissions rows' unused `data-kind` attribute removed.
- **README** (`a5ea789`): Permissions section restructured into the standard family deep-dive —
  scope→pattern examples as a list, matrix interactions documented (sortable columns, select
  checkboxes, bulk apply/remove/delete/adopt), per-codec deny-surface notes split out.
- **Doc audit follow-ups (this session)**: removed the stale README claim that the capability
  matrix "keeps Cursor as Planned" — it has been `Yes (Denylist)` since 2026-08-14 and the
  sentence contradicted both the README matrix and ARCHITECTURE.md. Added a Frontend
  Architecture section to ARCHITECTURE.md pinning the now-stable UI conventions: one unified
  In-use page per family with URL-backed status filters, flattened single-link sidebar groups,
  the shared matrix component system (sortable headers, checkbox/bulk-action pattern, column
  width convention), and enabled+detected-only harness columns enforced at the inventory
  presentation boundary.
- `09b2d7b`: CLAUDE.md gained RTK token-optimized command instructions (tooling only).

Validation re-run on this tree before this entry: typecheck clean; Vitest 314/314 across 64
files; backend 553 unit + 193 integration tests pass at 81% branch coverage; production build
passes; `frontend/dist` rebuilt from merged `main`.

## 2026-08-22 — Family pages hide disabled and not-detected harnesses

Harness toggle columns on the five family pages now only include harnesses that are **enabled in
Settings AND detected** (installed, or config file present). Implemented by agy (delegated via
herdr, branch `fix/hide-unusable-harness-columns`, 4 commits `ba700e5`..`7e74531`), independently
verified: diff spot-checked and full suite re-run — backend 553 unit + 193 integration (6 new
integration regression tests), typecheck, Vitest 312/312, build all pass.

- The leak was real and per-family inconsistent: MCP/Hooks/Permissions built their inventory from
  the FULL harness scan list (so disabled harnesses rendered as columns); skills/agents/slash
  filtered disabled but kept enabled-but-not-installed ones.
- Fix is at the inventory presentation boundary only (`_active_scans` in mcp/hooks/permissions;
  detection filters in skills/agents/slash presentation). Reconcile paths, mutation gating
  (`require_enabled_adapter`, `enabled_writable_adapters`), and planner/unmanaged-review endpoints
  are untouched.
- Slash-command detection could NOT reuse its `available` flag (output-root existence — a fresh
  install may not have created the folder yet). New `_is_detected` in `slash_commands/targets.py`
  derives detection from install probe on PATH / app probe paths / discovery config files; targets
  gained an `installed` field (OpenAPI regenerated, codegen check clean).
- CLI JSON matrix output shares these query services, so headless output filters identically
  (intended).
- Server restarted from merged `main`; dist rebuilt. Pushed to `origin/main`.

## 2026-08-22 — Family matrix pages standardized on the Skills design

Skills is the design reference; Agents, Slash Commands, MCP, and Hooks were converged on it
(delegated to agy via herdr, branch `ui/standardize-family-matrices`, 6 commits `1673b7c`..`0f5c038`,
independently verified: diff spot-checked and typecheck / Vitest / build re-run — all pass).

- **Identity headers are now the family name**, styled identically to the "Active" header:
  Skill / Agent / Slash Command / MCP Server / Hook (was Name / Agent Name / Name / Server / Hook ID).
- **Sorting everywhere**: name asc/desc, per-harness column state, and coverage/Active — ported the
  Skills `sortRows` pattern into agents/hooks/mcp selectors (new sort tests mirror
  `MatrixView.test.tsx`); slash commands' existing sort was aligned rather than reimplemented.
- **Column widths uniform**: harness 52px / compact 140px / coverage 96px across all five; agents
  gained a compact responsive stack cell (`AgentsHarnessLogoStack`); hooks dropped a minWidth=800px
  override.
- **Titles**: "Skills in use" → "Skills", "MCP servers in use" → "MCP Servers", "Hooks in use" →
  "Hooks"; Agents and Slash Commands were already bare family names. Review-view titles unchanged.
- **Buttons**: standardized on the action-pill system; removed an inline `marginRight` style in
  HooksInUsePage.

Validation re-run post-merge: typecheck clean, Vitest 312/312 across 63 files (up from 307/61),
build passes, dist rebuilt from merged `main`. Pushed. Frontend only — no backend/API changes.

## 2026-08-22 — Sidebar flattened: family headings link straight to their page

Follow-on to the two entries below. Since every family now has exactly one unified page, the nested
"In use" child entry under each sidebar heading was pure indirection. Single-link groups (Agents,
Skills, Slash Commands, MCP Servers, Hooks) render their heading itself as a direct link carrying
the family count; Marketplace keeps its collapsible group for its three children (`92c4076`).
Implemented in `Sidebar.tsx` (render-level: single-link `SidebarGroupModel`s become
`SidebarTopLink`s; the model is unchanged), so a future multi-page family automatically regains the
collapsible treatment. App.test.tsx updated; note the accessible-name collision between the Skills
family heading and the Marketplace "Skills" sub-link — tests assert unambiguous names instead.

Validation: typecheck clean, Vitest 307/307 across 61 files, build passes, dist rebuilt from
merged `main`. Pushed.

## 2026-08-22 — MCP In-use page converged; all five families now uniform

MCP's In-use page now includes unadopted servers behind the URL-backed status filter
(`?status=untracked`), matching agents/skills/slash-commands/hooks. Implemented by agy (delegated
via herdr, branch `ui/mcp-converge-in-use`, commits `1f1326c` + `d04baa0`), independently verified:
diff spot-checked and typecheck / Vitest / build re-run on this checkout — all pass.

- `/mcp` is the canonical route (moved into a feature `routes.tsx`, hooks pattern); `/mcp/use`,
  `/mcp/review`, `/mcp/managed`, `/mcp/unmanaged` are redirects (`/mcp/review` →
  `/mcp?status=untracked`). `mcpRoutes.inUse = "/mcp"`, `needsReview = "/mcp?status=untracked"`.
- Selectors: `filterMcpServersInUse` no longer drops unmanaged entries; new `untracked` pill;
  "All" counts every entry. Matrix renders unmanaged rows inline with Adopt (identical) or
  config-choice dialog (differing configs); needs-review detail sheet composed for unmanaged
  servers; bulk adopt-selected and adopt-identical header action carried over from the old page.
- **Sidebar is now uniform across all five families: one "In use" link each.** The MCP exception
  comment from `420b97c` is gone with its second link.
- Deleted `McpNeedsReviewPage.tsx` + `McpNeedsReviewMatrixView.tsx`; their test cases were folded
  into `McpInUsePage.test.tsx` (307/307 tests, 61 files — count up from 300/62).
- `frontend/dist` rebuilt from merged `main`; hard-refresh to see it.

Validation re-run post-merge on this checkout: typecheck clean, Vitest 307/307, build passes.
Pushed to `origin/main`. Backend untouched. Follow-up docs pass: README "Extension Statuses"
now describes the single-page-per-family navigation with the inline Needs-review filter, the
agents auto-repair pointer was corrected to the Needs-review view, and `docs/adding-a-family.md`
now pins the one-unified-In-use-page convention as a checklist item for future families.

## 2026-08-21 — Sidebar: removed per-family Unmanaged links unified into In-use pages

Agents, Skills, Slash Commands, and Hooks each have one unified In-use page that already includes
unadopted assets behind a URL-backed status filter, so their second sidebar link ("Unmanaged")
duplicated a view reachable in place. Removed those four links (`420b97c`); group header counts still
show the whole family inventory. **MCP deliberately keeps its Unmanaged link** — `McpInUsePage`
lists managed servers only (comment recorded in `sidebar.ts`). Legacy `/review` routes remain as
redirects onto the unified pages' filters; Overview review cards that deep-link through them are
unchanged. Agents page attention-banner copy now points at the Needs-review filter instead of the
removed nav item.

Validation: typecheck clean; Vitest 300/300 across 62 files; production build passed (`frontend/dist`
rebuilt). Pushed to `origin/main`. If MCP's In-use page later gains unadopted entries behind a
filter, its sidebar link becomes removable the same way.

## 2026-08-21 — Reconcile-reentrancy audit across families (handoff item 5)

### What shipped

Audited every family that wires `set_reconcile` for the threading assumption skills fixed on
2026-08-21. Findings by family: **skills** guarded (`threading.local`); **agents** serialized by its
dedicated `lock_path`; **slash_commands** had a *worse* version of the bug — no guard, and the drift
repair path reads back through the query service (`_mutation_payload` → `queries.get_command`), so
one top-level `reconcile()` executed once per repaired command (reproduced empirically: 3 drifted
commands → 3 full passes; O(N²) scans, N-deep recursion, unbounded if drift persists across passes,
e.g. under a concurrent external writer); **mcp/hooks/permissions** have no guard but their
reconciles never read back through the query service, so they were latent-only.

Fixes:
- Added the same per-thread reentrancy guard (`threading.local`) to `SlashCommandQueryService`
  (proven bug) and, as structural hardening with comments, to `McpQueryService`, `HooksQueryService`,
  and `PermissionsQueryService`. The invariant is now uniform: every query service that wires
  `set_reconcile` is reentrancy-guarded.
- Audit-trail pollution fix: concurrent readers both run reconcile in these families (there is no
  single-flight lock), and the loser of an adoption race hits the mutation service's "already
  managed" 409 after the winner succeeded. `ObservedConfigAutoAdoptService` and
  `McpAutoAdoptService` now treat a 409 `MutationError` from promote/adopt as a benign race loss
  instead of recording a failed `auto_adopt` Activity event. Genuine failures still record.

Regression coverage: `test_repair_does_not_reenter_reconcile_per_repaired_command` in
`tests/unit/test_slash_commands.py` pins one reconcile execution for three drifted commands
(verified to fail without the guard); new `tests/unit/test_config_auto_adopt.py` pins the 409-skip
and that non-409 failures still record.

### Validation

553 unit + 187 integration tests pass at 81% branch coverage; Ruff clean; Pyright 0 errors;
`npm run typecheck` clean; `npm test` 300/300 across 62 files; `npm run build` passes. Committed as
`71b84fb` on a short-lived branch, fast-forwarded into `main`; branch deleted. **Not pushed** (see
the push decision below, still pending). Server restarted from this tree.

### Remaining notes from this audit

- These four families still have *no single-flight* reconcile: two concurrent readers duplicate the
  full scan work and can interleave adoptions. Consequences are now benign (409 races are skipped
  silently, store writes are file-locked), but if reconcile cost ever matters, a per-family lock
  like agents' `lock_path` is the template. Not done now — no correctness gap.
- `SlashCommandMutationService.create_command/update_command` build payloads via
  `queries.get_command`, which triggers a redundant reconcile pass per mutation call. Harmless today
  (the guard prevents nesting; the pass finds nothing new post-mutation), noted for whenever
  mutation latency is next profiled.

## 2026-08-21 — Interrupted `origin/main` merge landed; auto-adopt stale-read fixed

### Running state

- `main` is at the merge commit `fd7341d` plus a follow-up fix commit. **Nothing is
  pushed** — `main` is well ahead of `origin/main` and push is deliberately deferred.
- The app is **not** running (nothing listening on port 8000). `frontend/dist` has been
  rebuilt from the current tree.
- `stash@{0}` (root `plan-*.md` / `RECOMMENDATIONS.md` pointer deletions) is untouched
  and still pending the separate decision recorded below.
- `CLAUDE.md` has an uncommitted local edit (an appended RTK tooling section) that was
  made outside this work and deliberately left uncommitted.

### What was actually on disk when this session started

`.git/MERGE_HEAD` was present: a merge of `origin/main` (`97559e2`) into `main` had been
started around 2026-08-20, its three conflicts resolved into the index, and then
abandoned before committing. The previous handoff entry did not mention it. The
resolution survived only in the index, which is the most fragile place to hold it.

### What shipped

**Merge committed (`fd7341d`).** Committed exactly the nine already-staged files, with no
re-resolution: the four upstream commits are Dependabot bumps (#37 ruff, #38 coverage,
#44 npm) plus `9b86efc` (#43), which normalizes the OpenAPI 422 reason phrase so codegen
stays deterministic on Python 3.14+.

The conflict resolution keeps this fork's `SkillsMutationService.enable_managed_package`
and `_manage_entry -> Path` alongside upstream's reentrancy guards. That union is
required, not cosmetic: `auto_adopt` binds the package path returned by `manage_entry`.
Worth noting upstream, `origin/main`'s `_manage_entry` is annotated `-> None` while its
body still returns `ingested` and `manage_entry` still declares `-> Path`; the fork's
version is the internally coherent one.

**Auto-adopt stale-read fix.** Upstream #43 resolved its deadlock with plain instance
booleans (`_is_reconciling`) on `SkillsQueryService` and `SkillsAutoAdoptService`. Those
guards were written against a codebase without this fork's caching and bounded-parallel
scanning layer, and they are not thread-safe. Sync API endpoints run in a threadpool over
one shared container, so the bad interleaving is a live path:

1. Thread A calls `inventory()`, which sets the flag and begins auto-adoption.
2. Thread B calls `inventory()`, sees A's flag, and **skips reconciliation entirely**,
   returning a snapshot taken from the middle of A's adoption.

Before the merge, B would instead have blocked on `file_lock` and returned freshly
reconciled state. The merge therefore traded *blocking-correct* for
*non-blocking-possibly-stale* in the one subsystem whose recent commits (`b47bc41`,
`f7ed959`) were specifically about race correctness.

This was confirmed by reproduction, not by inspection: thread B returned the skill as
`unmanaged` while thread A concurrently returned it as `managed`.

The fix makes both guards `threading.local()`. Reentrancy protection is preserved per
thread (upstream's actual intent), while a genuinely concurrent caller falls through to
`file_lock`, is serialized, and reads fresh state.

**Regression test.** `test_concurrent_inventory_read_during_auto_adopt_is_not_stale` in
`tests/integration/test_skills_mutations.py` blocks adoption mid-flight, starts a second
reader, and asserts both that the reader does not return early and that it observes the
adopted skill. It was verified to fail against the merged-but-unfixed code
("concurrent reader returned mid-adoption") and pass after the fix, closing the coverage
gap noted below.

### Validation

Full suite on the final tree: 549 backend unit tests and 187 backend integration tests
pass at 81% branch coverage (the 2026-08-18 entry recorded 186 integration tests and this
session added exactly one, so the merge dropped no test despite resolving a conflict in
`test_agents_routes.py`); `npm run typecheck` clean; `npm test` passes 300/300 across 62 files (the
previously reported Vitest worker I/O stall did not reproduce); `npm run build` passes;
`npm run codegen:check` reports no OpenAPI drift; Ruff clean; Pyright project-wide
reports 0 errors against its existing warning baseline.

### Known environment gap

`./.venv/bin/python -m pytest ...` does not work in this repo — pytest is not a
dependency. `requirements-dev.txt` pins only ruff, pyright, and coverage, and the suite
runs on `unittest` via `scripts/test_backend.sh`. Use
`./.venv/bin/python -m unittest tests.integration.test_skills_mutations` for focused runs.

### Next steps, in priority order

1. **Decide whether to push.** `main` carries a large unpushed backlog plus this merge,
   and Dependabot keeps landing on `origin/main`, so the divergence regrows every week
   this waits. Push was intentionally not performed.
2. **Pressure-test the real mutation path** (carried over, still the substantive next
   item). Adopt and enable a skill from the UI, record the browser network waterfall for
   the mutation plus the following list/detail/source-status requests, and separate
   server time from render time. The app must be restarted first — nothing is listening
   on port 8000. Note the baseline moved: concurrent readers now serialize behind the
   adoption lock instead of returning early, so overlapping GETs will show longer tail
   latency during auto-adopt than the merged-but-unfixed code did. That is the
   correctness fix showing up in the trace, not a caching regression.
3. **Optimize remaining post-mutation work only if the trace justifies it.** Leading
   candidates stay the before/after audit snapshots and the frontend's overlapping
   post-mutation refetches. Preserve audit completeness and cache invalidation semantics.
4. **Add an end-to-end latency regression check** over adopt/enable plus the first
   refreshed read model, using isolated state rather than live-user mutations.
5. **Audit the other families for the same threading assumption.** Only skills carried
   the `_is_reconciling` guards, but `slash_commands`, `mcp`, `hooks`, and `permissions`
   all wire `set_reconcile` the same way and share the threadpool exposure.
6. **Resolve the frontend test-runner environment.** The Vitest worker I/O stall has not
   reproduced recently, but the cause was never identified.
7. **Repository hygiene.** Decide whether the five root pointers in `stash@{0}` stay
   deleted, and commit that decision on its own.

## 2026-08-18 — Skills inventory performance shipped; tailnet app live

### Running state

- `main` includes skills-performance merge `2e80fb3`. The production
  frontend was rebuilt from that checkout on 2026-08-18.
- The app is running with
  `./.venv/bin/python -m harness_asset_manager serve --host 127.0.0.1 --port 8000 --allow-remote --no-open-browser`.
- Tailnet URL: <https://vibebox.goose-marlin.ts.net/>. Tailscale Serve maps `/` to
  `http://127.0.0.1:8000`; the root, `/api/health`, and `/api/skills` all returned
  HTTP 200 through tailnet HTTPS after launch.
- This is tailnet-only, not a Funnel/public route. The API is unauthenticated, so
  every identity allowed to reach this node by tailnet policy can mutate local
  harness configuration.
- Five pre-existing root-file deletions (`RECOMMENDATIONS.md` and four
  `plan-*.md` pointers) remain deliberately untouched. **Correction (2026-08-21):**
  they are not loose in the working tree — they are parked in `stash@{0}`
  ("wip: remove obsolete root plan pointers before branch reconciliation"), and the
  root pointer files are present on disk. This entry also failed to record that an
  `origin/main` merge was started and left unfinished; see the 2026-08-21 entry.

### What shipped

**Stable settings path (`c375eec`).** The default settings file previously lived
under `config_dir`, so changing only `XDG_CONFIG_HOME` could silently select a
different `settings.json` and make disabled-harness or auto-adopt settings appear
lost. The default now follows `data_dir / "settings.json"`; explicit settings-path
overrides still win, and no live settings file was migrated, overwritten, or
deleted.

**Faster skills adoption and harness enable (`2e80fb3`).** The delay was dominated
by rebuilding the complete skills read model after each mutation: the store and
every harness repeatedly walked, read, hashed, and parsed the same package trees.
The fix adds a shared, bounded package cache, per-snapshot validation cycles,
bounded parallel scanning, and single-flight snapshot construction. Unchanged
packages are validated from filesystem metadata without rereading content, while
ordinary edits, nested topology changes, symlink repoints, broken links,
invalidation races, and waiter failures retain deterministic freshness behavior.

Controlled read-only comparison on the same live roots (70 store packages and 90
harness observations):

- baseline `c375eec`: 10.042 s cold; 10.257 s median expired refresh;
- candidate `f7ed959`: 2.240 s cold; 1.279 s median expired refresh;
- unchanged refresh speedup: **8.02x**;
- post-merge tailnet expired refreshes: approximately 1.24–1.30 s.

Validation: 549 backend unit tests and 186 integration tests passed at 81% branch
coverage; focused skills-mutation integration tests passed 46/46; typecheck, Ruff,
`git diff --check`, and production build passed. The independent correctness review
found no remaining blocker. The exact full Vitest command did not complete in this
environment because workers repeatedly entered the known uninterruptible I/O state;
frontend code was unchanged, and the isolated skills selector test passed 4/4.

### Next steps, in priority order

1. **Pressure-test the real mutation path.** Adopt and enable
   `frontend-test-environment-debugging` from the tailnet UI. Record the browser
   network waterfall for the mutation plus subsequent list/detail/source-status
   requests, and distinguish server time from rendering time.
2. **Optimize the remaining post-mutation work only if the trace justifies it.**
   The leading candidates are the before/after mutation audit snapshots and the
   frontend's overlapping post-mutation refetches. Preserve audit completeness and
   cache invalidation semantics; do not trade correctness for a cosmetic speedup.
3. **Add an end-to-end latency regression check.** Keep the existing read-only
   benchmark for package-inventory comparisons, and add a safe isolated-state test
   that times adopt/enable plus the first refreshed read model. Avoid live-user
   mutations in automated validation.
4. **Resolve the frontend test-runner environment.** Reproduce the Vitest worker
   I/O stall on an otherwise idle machine, separate jsdom/dependency startup from
   test execution, and restore a reliable full-suite acceptance signal before the
   next frontend-heavy change.
5. **Repository hygiene.** Decide separately whether the five historical root
   pointers should stay deleted, then commit that decision without mixing it into
   runtime or performance work. Nothing from this session has been pushed.

## 2026-08-14 — Cursor permissions approval mode set to unrestricted

Configured `CursorPermissionsMapper` to write `approvalMode = "unrestricted"` into `~/.cursor/cli-config.json` upon enabling a HAM denylist permission, aligning Cursor with Claude, Antigravity, and Codex.

- **What shipped**:
  - `CursorPermissionsMapper.enable_permission` sets `document["approvalMode"] = "unrestricted"`.
  - `CursorPermissionsMapper.disable_permission` pops `"approvalMode"` when no deny rules remain in `permissions.deny` and `approvalMode == "unrestricted"`.
  - Kept `version: 1` and `editor.vimMode: false` setdefault seeding for from-empty configs as planned.
  - Re-enabling an existing permission repairs and upgrades an older native approval mode (e.g. `auto-review` → `unrestricted`).
  - Added unit test `test_enable_sets_approval_mode_and_disable_cleans_it_up` in `test_permissions_mappers.py`, updated `test_cursor_round_trip_and_unsupported` in `test_permissions_adapters.py`, and updated `test_enable_and_disable_across_harnesses` in `test_permissions_routes.py`.
- **Capability Matrix**: Promoted Cursor Permissions to `Yes (Denylist)` in `README.md` and `ARCHITECTURE.md`.

Closed `RECOMMENDATIONS.md` §2.2. Added:

- `coverage.py` to `requirements-dev.txt` and `scripts/test_backend.sh`, measuring
  combined unit and integration coverage for `harness_asset_manager` with branch
  coverage and an 80% minimum.
- Vitest V8 coverage via `@vitest/coverage-v8`, with `npm run test:coverage`
  enforcing 60% statements/lines and 55% branches/functions.
- CI enforcement in the frontend validation job; generated coverage artifacts
  remain ignored local output.

The thresholds start just below the current baseline so the ratchet prevents
regressions without pretending coverage is a quality score. The reports show
per-file coverage so future threshold increases can be evidence-based.

## 2026-08-12 — Machine-readable API error codes shipped

Closed the API error-code recommendation. Unsuccessful API responses now use a
documented `{code, error}` envelope:

- Added the `ErrorResponse` OpenAPI schema and applied it to common 400, 404,
  409, 422, 500, and 503 responses.
- Centralized stable fallback codes (`not_found`, `conflict`,
  `validation_error`, `request_failed`, `internal_error`) in the API handlers.
- Added semantic codes for skill, slash-command, and marketplace-item lookups,
  plus `agent_conflict`.
- Added frontend `ApiError` with preserved `code` and HTTP `status`, while
  retaining compatibility with legacy `detail` and validation payloads.
- Corrected agent mutation UI catches that were reading a nonexistent
  `error.error` property.

Validation: 526 backend unit tests, 182 backend integration tests, 281 frontend
tests, frontend typecheck, production build, Ruff, and deterministic OpenAPI
regeneration all pass.

## 2026-08-12 — Family and harness extension checklists documented

Closed `RECOMMENDATIONS.md` §2.3. Added:

- `docs/adding-a-family.md`, covering canonical storage, binding shapes, mappers,
  adapters, preservation and ownership rules, application/API/CLI/frontend wiring,
  catalog updates, tests, and validation.
- `docs/adding-a-harness.md`, covering live product research, catalog registration,
  support tiers, per-family verification, fake-home detection tests, capability
  behavior, and evidence requirements.

`ARCHITECTURE.md` now links both guides, and `RECOMMENDATIONS.md` records the
checklists as shipped. No runtime behavior changed.

> **Priority scope (2026-08-10):** Focus active work on Claude Code, Codex, Antigravity (agy),
> and Cursor. Hermes, OpenCode, and OpenClaw are low/no priority and have no remaining roadmap
> work. Historical entries below may mention them for context, but do not resume those items.

## 2026-08-12 — `--state-dir` now isolates the complete run

Closed `RECOMMENDATIONS.md` §1.4. The existing state-dir override isolated HAM's config, data,
and runtime directories, but catalog-resolved native harness paths could still point at the real
`HOME`, XDG roots, or explicit harness-root environment overrides.

- `--state-dir` and `HARNESS_ASSET_MANAGER_STATE_DIR` now normalize `HOME`,
  `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, and `XDG_STATE_HOME` to the isolation root.
- Explicit HAM harness-root overrides, legacy root spellings, `HERMES_HOME`, and the settings
  path override are cleared for the isolated invocation so they cannot escape the root.
- Config snapshot discovery now uses the container's resolved harness context instead of reading
  the process-global environment, closing the last snapshot path escape.
- Added regression coverage for direct context resolution, CLI environment propagation, and
  config/data/state path resolution. README now documents the full isolation boundary.

Validation: 523 backend tests, 279 frontend tests, Ruff across application/tests/scripts,
frontend typecheck, production build, and `git diff --check` all pass. Pyright was unavailable
in the local virtualenv and was not run.

## 2026-08-14 (latest) — Short `harnessam` paths and Hermes best-effort agents

The central store uses the short `harnessam` name, while product/distribution names,
Python imports, persisted Codex keys, generated markers, and legacy migration paths
retain `harness-asset-manager` for compatibility:

- macOS: `~/.harnessam`
- Linux: `~/.harnessam` (unless explicit XDG overrides are set)

On first resolution, existing `harness-asset-manager` stores are moved into the new location
without deleting content, and a compatibility symlink remains at the old location so existing
absolute harness bindings keep working. macOS preserves the previous precedence of
`~/Library/Application Support/harness-asset-manager` over `~/.harness-asset-manager`.
Explicit XDG roots receive the same legacy-name migration.

The remaining low-priority housekeeping is also complete: long-form plans and handoff material
now live under `docs/` with root pointers, `atomic_files.py` gates its platform lock import,
server startup passes one bound socket through to the child process, frontend tests are green,
and `scripts/clean-local-caches.sh` handles reproducible local caches.

Hermes agent files are managed best-effort under `$HERMES_HOME/agents/` (normally
`~/.hermes/agents/`) so separate Hermes-side support can consume the shared Markdown
definitions. HAM does not claim that Hermes loads those files natively.

Validation: 528 backend unit tests, 182 backend integration tests, backend coverage at
81%, frontend typecheck, production build, Ruff, and `git diff --check` pass. The local
frontend test dependency set still fails before assertions because React 19.2.8 exports
no `act` function for the installed React Testing Library (`React.act is not a function`).

## 2026-08-10 — Cursor permissions mapper shipped, denylist-only, matrix stays `Planned`

Implements steps 1-3 of the "Next permissions milestone" checklist from the entry directly below
this one, on branch `feat/cursor-permissions-adapter`. Delegated via herdr: Codex built the mapper,
Agy (pinned to Gemini 3.1 Pro) wired the catalog binding and tests; both ran in isolated worktrees
and neither branch was ever committed to — I copied their verified worktree diffs into one
integration branch myself and re-ran the full DoD there, which is where two real bugs surfaced
(below). Research was done first against Cursor's live docs (`cursor.com/docs/cli/reference/
permissions`, `.../configuration`, `.../reference/permissions` (IDE), `.../changelog`) — the
handoff entry below explicitly warned not to guess this schema, and it was right to warn: the
CLI and IDE Agent turned out to be two unrelated permission surfaces.

- **What shipped**: `CursorPermissionsMapper` (`mappers.py`, codec `cursor-permissions`) and a
  `permissions` catalog binding for `cursor` pointing at `~/.cursor/cli-config.json` (global
  only — the project-level `.cursor/cli.json` is never touched, same rule every other family
  here already follows). Deny-only, matching every other harness in this family. Scopes map
  unusually cleanly onto Cursor's five tokens (`Shell()`, `Read()`, `Write()`, `WebFetch()`,
  `Mcp()`) — no dual-rule complexity like Claude's `file_write`, no missing-scope gap like
  Codex's shell/mcp. Two representability limits are real and were pinned by tests, not
  incidental: `Shell()` only matches a single-word command (docs: *"commandBase is the first
  token in the command line"*), so HAM's common multi-token shell patterns (`"git push"`) are
  correctly reported unsupported; `Mcp()` only documents the full `server:tool` form, so a
  bare-server MCP pattern is also unsupported. `enable_permission` seeds `version`/`editor.vimMode`
  via `setdefault` (never clobbering an existing value) because Cursor's docs list both as
  required top-level keys and a from-empty `cli-config.json` would otherwise be malformed.
- **Deliberately not shipped: no auto-run/approval-mode write.** Every other harness in this
  family flips a persistent no-prompt flag on enable (Claude `bypassPermissions`, Antigravity
  `always-proceed`, Codex `approval_policy = "never"`). Cursor's `cli-config.json` has a
  persistent `approvalMode` key (`allowlist` / `auto-review` / `unrestricted`), but nothing in
  Cursor's docs ties any of its values to guaranteed deny-rule enforcement the way `--force`/
  `--yolo` are explicitly documented to ("Force allow commands unless explicitly denied"), and
  the CLI's own changelog shows this exact area (auto-run naming, `auto-review` mode, team-level
  gating) actively changing release to release. This is precisely the case the entry below
  pre-decided: *"If the mode is UI-only, version-dependent, or does not guarantee deny-first
  evaluation, expose Cursor as unsupported... rather than writing an inferred setting."* The
  mapper only ever reads/writes `permissions.deny`.
- **IDE Agent confirmed permanently out of scope.** It reads an entirely separate
  `~/.cursor/permissions.json` (+ per-repo copy, concatenated) with `mcpAllowlist` /
  `terminalAllowlist` / `autoRun` — allowlist-only, and `autoRun` is explicitly documented as
  "best-effort convenience," not enforcement. There is no deny surface to bind to at all, so
  unlike the CLI this is not a "not yet verified" gap, it is structurally unsupported.
- **Capability matrix intentionally left at `Planned`, not flipped to `Yes (Denylist)`.** The
  entry below gates the flip on "both the CLI and IDE behavior are confirmed... add a handoff
  entry with the exact Cursor versions tested." IDE is now genuinely resolved (previous bullet).
  CLI is not: `cursor-agent` is not installed anywhere in this environment (`which cursor-agent`
  → not found), so every claim above is doc-verified, not tested against a running binary. The
  matrix flip is the next step, gated on that test existing.
- **Two real bugs caught only by integrating the two branches and re-running the DoD myself** —
  neither delegate's own local run could have caught them, and this is exactly why "a delegate's
  passing self-report is not the acceptance signal": (1) `FileBackedPermissionsAdapter.__init__`
  resolves its mapper eagerly via `get_mapper(profile.codec)`, so Agy's catalog binding alone
  broke the entire DI container (every test that builds it) until Codex's mapper landed —
  Agy diagnosed this correctly itself and escalated rather than stubbing the mapper, which is
  the right call and is why its worktree never had a green full suite. (2) Agy's own new
  adapter test called `adapter.disable_permission(spec_file)` (a whole `PermissionSpec`) where
  the method wants just an `id: str`, and separately asserted `"editor.vimMode" in doc` against
  a *nested* `{"editor": {"vimMode": False}}` structure — neither error crashed, both silently
  passed/failed the wrong thing. Fixed directly in the integration branch rather than bouncing
  back to a delegate for a two-line test fix; `disable_permission()`'s pattern lookup also turned
  out to re-resolve its own `PermissionStore` from `resolve_app_paths(env)` rather than trusting
  whatever store instance the caller holds, which the fix had to route around explicitly (see the
  comment left in `test_cursor_round_trip_and_unsupported`) — this quirk is pre-existing and
  shared by every other per-harness adapter test in that file, none of which previously exercised
  `disable_permission` directly.
- **Validation on the integration branch**: `ruff check harness_asset_manager tests` clean;
  targeted permissions suite (`test_permissions_mappers` + `test_permissions_adapters` +
  `test_permissions_routes`) 23/23 pass; full backend suite 699 tests, same 2 failures + 1 error
  as an unmodified `main` checkout (confirmed by running both) — a pre-existing environment flake
  where `tests.integration.test_launcher` spawns a subprocess that can't inherit
  `~/.local/lib/python3.12/site-packages` in this sandbox, unrelated to this change; `npm run
  typecheck` clean; `npm run build` clean. No frontend files were touched.
- **Not yet done**: merging `feat/cursor-permissions-adapter` into `main`, deleting the two
  delegate worktrees/branches (`codex-cursor-perms` / `agy-cursor-catalog`, neither ever
  committed to), and the actual CLI-version verification pass that would unlock the matrix flip.

## 2026-08-10 — Denylist adoption now changes native approval defaults; Cursor permissions planned

The Permissions family remains denylist-only, but adoption now configures each supported harness
so unlisted actions do not fall back to the harness's interactive approval flow:

- **Claude Code:** enabling a rule writes `permissions.defaultMode = "bypassPermissions"` beside
  `permissions.deny`. Claude deny rules are evaluated before the mode, so recorded denials still
  block. Disabling the final HAM rule removes the HAM-added mode.
- **Antigravity:** enabling a rule writes top-level `toolPermission = "always-proceed"` beside
  `permissions.deny`; the mode is removed after the final deny rule is disabled.
- **Codex:** enabling a rule writes top-level `approval_policy = "never"` and
  `default_permissions = "harness-asset-manager"`, changes the HAM profile to extend
  `:workspace`, and enables its allow-by-default network baseline before applying recorded
  domain denials. The profile is removed, and the HAM-added top-level settings are cleaned up,
  after the final rule is disabled. Re-enabling an existing rule reapplies these surrounding
  defaults rather than treating the existing binding as complete.
- **Codex limitation:** its current permission-profile config can express filesystem and network
  rules but not shell-command or MCP deny rules. HAM continues to classify those scopes as
  unsupported for Codex.

Validation for this change: backend `unittest discover` passes **694 tests**, focused permission
tests pass, Ruff passes, and `git diff --check` is clean.

### Next permissions milestone: Cursor adapter and auto-run handling

Cursor is currently `Permissions: Planned` in the capability matrix and has no `permissions`
binding in `harness_asset_manager/harness/catalog.py`. Do not add Cursor by copying the Claude or
Antigravity mapper: Cursor uses a separate CLI permissions surface and its product has changed
auto-run/allowlist behavior across releases.

Implementation investigation and design checklist:

1. **Confirm the supported configuration surfaces against the installed Cursor CLI.** The current
   public CLI permissions documentation points to global `~/.cursor/cli-config.json` and
   project-level `.cursor/cli.json`, with permission tokens such as `Shell(...)` and file rules.
   Verify the exact JSON schema, whether `deny` is still supported in the current release, and
   whether the IDE Agent reads these files or only `cursor-agent` does. Record precedence between
   global, project, workspace, and command-line settings before adding a catalog binding.
2. **Resolve auto-run mode separately from rule storage.** Identify the documented persistent key
   or CLI option for “run without prompts” / auto-run. Confirm that explicit deny rules remain
   authoritative in that mode. If the mode is UI-only, version-dependent, or does not guarantee
   deny-first evaluation, expose Cursor as unsupported with a clear caveat rather than writing an
   inferred setting. The desired HAM behavior is the equivalent of “always run unlisted actions;
   deny only recorded rules,” not Cursor's allowlist or classifier mode.
3. **Add a `cursor-permissions` mapper and catalog profile.** Map canonical scopes only where
   Cursor can enforce them. At minimum, investigate `shell` → `Shell(commandBase)`,
   `file_read` → `Read(path/glob)`, and `file_write` → the corresponding Cursor write token.
   Determine whether `web` and `mcp` have stable native permission tokens. Cursor's documented
   shell token may match only the first command token, while HAM shell patterns can include a
   command prefix such as `git push`; mark multi-token patterns unsupported unless Cursor's
   matching semantics can preserve that distinction.
4. **Preserve native configuration and ownership boundaries.** Use a JSON config-subtree adapter
   that merges only HAM-owned deny entries, retains unknown keys and user-authored allow/ask
   entries, and never rewrites project config while operating on global config. Define how
   managed IDs, unmanaged native rules, partial matches, drift, and disable cleanup work before
   enabling the family in the UI.
5. **Make adoption idempotent and reversible.** Enabling the first Cursor rule should apply the
   verified no-prompt mode plus the deny entry. Re-enabling an existing binding must repair a
   stale mode. Disabling the final HAM rule should remove only settings HAM can prove it owns and
   restore the prior native mode where ownership metadata makes that safe; do not erase a user's
   pre-existing auto-run choice.
6. **Test at three levels.** Add mapper round-trip and representability tests; adapter tests for
   global/project path resolution, preservation, unmanaged promotion, drift, and mode cleanup;
   and integration tests proving Cursor appears in the Permissions matrix only when the adapter
   is actually supported. Include a fixture for an older Cursor config whose auto-run mode is
   “auto”/review-like and prove adoption changes it to the verified denylist-only mode.
7. **Update capability and safety documentation only after verification.** Change Cursor from
   `Planned` to `Yes (Denylist)` only once both the CLI and IDE behavior are confirmed. Document
   unsupported scopes and any version-specific auto-run caveat alongside the mapper, and add a
   handoff entry with the exact Cursor versions tested.

## 2026-08-10 — Frontloaded README refactor & Hybrid Sync Architecture shipped

- **Refactored README.md**:
  - Frontloaded **What it does for you** and **Key Capabilities** table right below the header.
  - Frontloaded **Supported Harnesses** with logo grid and a comprehensive 7-harness x 6-family **Capability Matrix**, adding **Agents** explicitly.
  - Simplified Capability Matrix status entries (`Yes` / `Not Installable` / `Not Yet`) for clean consistency across all families.
  - Frontloaded **How to Use It** with quick installation, Web UI launch, and CLI reference.
- **Hybrid Sync Architecture & CLI `refresh --sync-all`**:
  - Added `--sync-all` flag to `harnessam refresh` CLI command to trigger auto-adoption and drift reconciliation across all asset families in one step.
  - Documented instant zero-copy symlink sharing (Skills & Agents) vs. on-demand drift auto-reconciliation for native configs (MCP, Slash Commands, Hooks, Permissions).
  - Added unit test coverage in `tests/unit/test_cli_commands.py`.

## 2026-08-10 — Antigravity (agy) Slash Commands & Hooks feature-completeness shipped

Implemented full Slash Commands coverage and feature-complete Hooks support for Antigravity (`agy`).

- **Slash Commands support for agy:**
  - Added `CommandFileBindingProfile` for `agy` in `catalog.py` pointing to `~/.gemini/antigravity-cli/commands/*.md` with `frontmatter_markdown` render format.
  - Updated `SlashTargetId` across backend models, API schemas, and frontend TypeScript definitions.
  - Added unit and integration tests verifying slash command creation, sync, frontmatter rendering, auto-adoption, and deletion.
  - Updated `README.md` status table and slash commands documentation.
- **Hooks multi-location discovery & bidirectional drift repair for agy:**
  - Added `discovery_config_path_resolvers` in `catalog.py` for `agy` hooks across user-level paths (`~/.gemini/config/hooks.json`, `~/.gemini/antigravity-cli/hooks.json`, `~/.gemini/antigravity/hooks.json`, `~/.gemini/antigravity-ide/hooks.json`) and project-level workspace paths (`.agents/hooks.json`).
  - Enhanced `FileBackedHooksAdapter` to scan and disable hooks across all discovery config paths while writing managed entries to canonical global config.
  - Enhanced `AntigravityHooksMapper.read_entries` with robust matcher canonicalization for native tool name variants (`run_command`, `bash`, `shell`, `view_file`, `read_file`, `write_to_file...`, `read_url_content...`, `*`, `any`).
  - Added integration tests for `agy` hook discovery across alternate paths, promotion into central store, and bidirectional drift repair (`adopt_target`).

Validation on this checkout: backend **693 unit and integration tests pass cleanly**, Ruff check passes with 0 errors.

## 2026-08-10 — Codex lossless adoption and configurable auto-adopt defaults shipped

Implemented the approved priority work for Claude Code, Codex, Antigravity (agy), and Cursor.
Hermes, OpenCode, and OpenClaw were not included in new behavior.

- **Codex preservation:** `parse_codex_agent()` now retains unmodeled TOML values. They are stored
  in a per-agent `.codex.toml` sidecar rather than shared Markdown, so Codex-only settings do not
  leak into Claude/Agy/Cursor symlinked agents.
- **Codex drift repair:** rendered Codex files now participate in the existing safe decision table.
  One-sided edits are adopted after semantic TOML verification; two-sided conflicts are left alone.
  Existing generated-file ownership and ledger baselines remain intact.
- **Auto-adopt defaults:** added per-family `autoAdoptHarnesses` settings, family support validation,
  API/OpenAPI, CLI (`harnessam settings auto-adopt-defaults`), and Settings UI controls. Defaults
  are applied only to usable targets; explicit existing bindings and disabled/unsupported harnesses
  win. The default remains empty to preserve existing behavior until the user selects targets.
- **Auditability:** automatic default bindings use the existing mutation/audit paths; failed default
  targets do not roll back a successful ownership adoption.

Validation on this checkout: backend **513 unit + 177 integration pass**, targeted Codex/agent,
settings, and family auto-adoption tests pass; frontend Settings tests pass (4), typecheck and
production build pass, Ruff passes, and frontend ESLint reports 0 errors / 23 existing warnings.
OpenAPI was regenerated for the new settings endpoint.

## 2026-08-10 (latest) — RECOMMENDATIONS.md refreshed against handoff CI evidence

Docs-only. No behaviour changed.

Closes the open item left by the 2026-08-09 handoff correction entry: `RECOMMENDATIONS.md`
still claimed the three timing-out frontend tests had "no CI evidence" and that the cause was
unestablished. Updated against verified state on `main` (`2195a84`):

- Header refresh date → 2026-08-10; notes local `npm test` can still red on the trio while
  **CI `frontend-validate` is green** on `c60d45a` (run `31291859168`).
- Shipped-batches list gains `c60d45a` (§1.2), `f9003b1` (family-wide auto-adoption), and
  `2195a84` (Stage 4 slash-command drift auto-repair).
- Tier-3 frontend-trio item rewritten: container-local ergonomics only, not a `main` regression.
- Suggested sequencing: Codex lossless adoption is now the next Tier-1 item; auto-adoption
  remainder also includes the default harnesses-on-adopt follow-up; trio demoted from "do next time npm test
  blocks" urgency now that CI is known green.

## 2026-08-09 — Cross-device sync planned; nothing implemented yet

Design session only. **No code changed.** `plan-cross-device-sync.md` is new; `README.md`
gained a "Cross-device sync — planned, not yet started" section; `RECOMMENDATIONS.md`
gained the `--state-dir` defect below. Read the plan before starting Phase 0 — several
decisions there are marked settled and are load-bearing.

The ask: one person, several machines, assets identical on all of them without hand-copying.

### The decisions that matter most

- **The store is the sync unit, not the harness directories.** Harness dirs hold symlinks
  (absolute, machine-specific), per-harness translations, and config files the user also
  owns. Folder-level sync (Dropbox/iCloud/Syncthing) breaks all three. Canonical records
  travel; each machine recomputes bindings locally.
- **`application/drift.py` is the merge engine — no new classifier.** The 2026-08-09
  entry below made it family-agnostic for slash commands; `remote` maps onto its
  `harness_sha256` and the last successful sync onto `baseline_sha256` with zero changes
  to the decision table. `clobber_one_sided` ("the side that moved holds the only edit in
  existence") is *provably true for one person's machines* — that is precisely why this is
  tractable, and precisely why teams are out of scope.
- **Git as transport, but HAM never invokes a git merge.** Fetch to a scratch ref,
  classify per record, write the result. A line-based merge of `manifest.json` is the most
  likely way this corrupts a portfolio.
- **Secrets excluded structurally, not redacted.** MCP `env`/`headers` *values* never
  enter the bundle; keys do, and the receiving machine reports "needs credential".
  `config_snapshots/redaction.py` is a regex pass over config text and is the wrong
  instrument for this — keep it only as a pre-publish refusal gate.
- **Tombstones decided up front** (§6). Retrofitting deletion semantics is the classic
  painful sync retrofit.

### Family sequencing — the non-obvious part

Sync difficulty is **not** family complexity. Because sync writes store records and lets
the existing projection path write harness files, binding shape mostly drops out; the
driver is content portability. Order: **agents → slash commands → skills → permissions →
hooks → MCP.**

- **Agents first**: a self-contained Markdown file with nothing machine-specific, and the
  only family whose drift machinery is already built and proven.
- **Permissions (4th) are more portable than they look**: `shell`, `web`, and `mcp` scopes
  are inherently machine-independent, and the file-glob idiom is already tilde- or
  project-relative (`permissions/store.py:29-33`).
- **Hooks (5th) are less portable than they look**: `HookSpec.command` is a raw shell
  string usually pointing at a local script. Arrival must check resolvability — a hook
  that looks enabled and silently never fires is worse than an absent one.
- **MCP last**: secrets, absolute paths in `command`/`args`, requires the binary installed,
  five config shapes, and the `extras` tuple must survive the bundle round-trip.

### Defect found from a code read — not yet fixed

`README.md` claimed `--state-dir` "isolates a run, which is how you keep CI or a throwaway
sandbox from touching the real store." **It does not.** `paths.py:77-98` uses
`STATE_DIR_ENV` only for `state_dir` (`runtime.json`, `server.log`); `config_dir` and
`data_dir` still resolve from XDG or the macOS default, so anyone following that advice
writes to their **real store**. Isolation needs `XDG_DATA_HOME` + `XDG_CONFIG_HOME` (plus
`HOME` for harness roots) — which is exactly what `tests/support/fake_home.py` does.

Logged as `RECOMMENDATIONS.md` §1.4 — Tier 1 on consequence, not on effort. The README
sentence is still wrong as of this entry; fix the doc or make the flag mean what it says.

### Test strategy — already affordable

`tests/support/fake_home.py` is a complete synthetic machine: `HOME`, all three XDG roots,
and a stub `PATH` with an executable per harness so `install_probe` detection works. **Two
of those plus a bare git repo is a full two-machine sync test, in process, in CI** — no
cloud, no second laptop. The conflict matrix belongs in the phase gate, not in manual QA.

### Explicitly out of scope, permanently

Multi-person and team distribution — served by the published Plugin versions. Do **not**
add a remote "role"/authority concept in anticipation; it was considered and dropped
deliberately. Roadmap (not now): profiles, standalone harmonization view, portfolio
snapshots (largely subsumed by git history), credential indirection, background sync,
rich conflict UI.

### Next step

Phase 0 — the portable/device-local split and bundle envelope, proven with agents only. It
has **no user-visible value**; everything else hangs off it. Gate: export → import into a
clean synthetic home is byte-identical, and a scanner proves zero device-local paths and
zero secret values in the bundle.

## 2026-08-09 — Slash-command drift auto-repair shipped (Stage 4 of plan-auto-adoption.md)

Slash commands now auto-repair already-managed target files that drifted, not just adopt new
unmanaged ones (that half shipped 2026-08-08). Implements `plan-auto-adoption.md` Stage 4.

- **`classify_drift()` is now family-agnostic**, moved to `harness_asset_manager/application/drift.py`
  and taking a plain `baseline_sha256` instead of an `AgentBindingRecord`. The agents ledger's
  `classify_drift()` is now a thin wrapper that extracts `record.store_sha256` and delegates —
  zero behavior change for agents, verified by leaving `agents/reconcile.py` and `agents/inventory.py`
  untouched.
- **No new persisted field was needed.** `sync-state.json`'s existing `contentHash` already *is*
  the store-rendered baseline (it is set to `hash_file(path)` right after writing
  `render_slash_command(command, format)` to that path). Reconcile only computes the *current*
  store hash fresh each pass; nothing new is stored on disk.
- **`SlashCommandsAutoAdoptService.reconcile()` grew a second pass, `_repair_drift()`**, gated by
  the same `auto_adopt.slash_commands` setting the 2026-08-08 new-file adoption already used —
  one toggle per family, not one per mechanism. It reuses the exact review actions a user would
  click manually: `clobber_clean` calls `restore_managed`, `clobber_one_sided` calls `adopt_target`.
  `collision`/`two_sided_conflict` are left for manual review, exactly like agents Stage 3 never
  auto-resolving a two-sided conflict. No new mutation logic was written for the actual repair.
- **Audit trail**: added `record_auto_repair` (operation `auto_repair`) beside the existing
  `record_auto_adopt` in `application/auto_adopt.py`, sharing an `_append` helper. No OpenAPI
  regen or frontend change needed — `ActivityEventResponse.parameters`/`operation`/`family` are
  already free-form strings and the Activity page already humanizes arbitrary values.
- **No other wiring changed.** `container.py` already wired `slash_command_queries.set_reconcile(
  slash_auto_adopt.reconcile)`; the CLI (`harnessam refresh`, `harnessam settings auto-adopt
  slash_commands`) and the Settings toggle already covered this family end-to-end.

### Evaluated: does this belong in any other family? No.

- **Skills**: directory symlinks; `rename(dir, dir-symlink)` fails `ENOTDIR`, so a managed skill
  binding cannot be clobbered at all — there is nothing to repair, only new directories to adopt
  (already shipped).
- **MCP / hooks / permissions**: config-subtree families. HAM writes into a file it does not own;
  there is no single binding/whole-file hash that can distinguish "clobbered" from "the harness
  legitimately changed something else in that file." `ObservedConfigAutoAdoptService` and
  `McpAutoAdoptService` correctly only ever promote equivalent *new* observations.
- **Codex agents:** now included after the 2026-08-10 lossless sidecar work. Codex slash commands
  were already covered by Stage 4; the remaining lossy-render rule applies only to any future
  rendered family without an equivalent preservation contract.

Agents (Stage 3) and slash commands (this change) remain the only two families whose binding
shape — "Harness Asset Manager writes a real file a harness can independently overwrite" — needs
this mechanism.

### Tests added

`tests/unit/test_drift.py` (new, exhaustive decision-table coverage), `tests/unit/test_agent_ledger.py`
(`ClassifyDriftTests` trimmed to the wrapper's own record→baseline responsibility, decision table
itself moved out), `tests/unit/test_slash_commands.py::SlashCommandDriftAutoRepairTests` (one-sided
adopts, clean-clobber resyncs without data loss, two-sided left untouched, disabled setting is a
no-op, idempotent), `tests/integration/test_slash_commands_api.py::test_one_sided_drift_is_auto_adopted_when_enabled`.

Validation: see the entry immediately below for the full-suite run this was checked against.

## 2026-08-09 — handoff.md corrected: stale duplicate heading and a resolved open-items list

Docs-only. No behaviour changed.

- **Two `(latest)` headings again** — the exact problem the 2026-08-08 docs-reconciliation entry
  fixed for the 2026-07-27 pair. `## 2026-08-08 — Family-wide opt-in auto-adoption implemented`
  below is chronologically *before* `## 2026-08-08 — Static-analysis gates completed` (`f9003b1`
  landed, then `c60d45a` — confirmed via `git log`), so its `(latest)` tag is removed here rather
  than rewriting the entry.
- **The "Still open, in priority order" list under the docs-reconciliation entry is stale in three
  of its four items**, and is marked superseded in place rather than rewritten (this file is an
  append-only log). Verified against the live repo, not assumed:
  1. `main` is pushed — local `main` and `origin/main` are both `c60d45a`.
  2. All seven branches that entry names to delete are gone; only `main` remains, locally and on
     the remote.
  3. `RECOMMENDATIONS.md §1.2` shipped in `c60d45a` (the entry directly above this one).
  4. Family-wide auto-adoption merged as `f9003b1`, not "on this working branch."
- **CI evidence for the flaky frontend trio now exists.** `ci.yml`'s `frontend-validate` job runs
  `npm test`; it passed on `c60d45a` (run `31291859168`), the same commit `RECOMMENDATIONS.md`'s
  Tier-3 entry says has no CI evidence yet. `SkillDetailContent`, `MarketplaceCliPage`, and
  `AgentsInUsePage` timing out is confirmed container-local, not a real regression.
  `RECOMMENDATIONS.md` still needs its own pass to reflect this; not done here since this pass is
  `handoff.md`-only.

## 2026-08-08 — Static-analysis gates completed

The static-analysis follow-up from `RECOMMENDATIONS.md §1.2` is implemented:

- Ruff now checks `harness_asset_manager`, `tests`, and `scripts`; all 9 script import-order
  findings and all 30 `F401` findings were removed. The remaining `F821`/`F841` rules stay as
  the intentional Ruff baseline.
- Pyright 1.1.411 is pinned in `requirements-dev.txt` with a committed basic-mode
  `pyrightconfig.json`. It type-checks the application and scripts, fails on undefined names,
  and reports the existing broader typing backlog as warnings so CI remains actionable without
  hiding the diagnostics.
- ESLint 10 with TypeScript ESLint and the stable React Hooks rules is configured in
  `eslint.config.mjs`; `npm run lint:frontend` covers `frontend/src`. Existing `any`, empty
  catch blocks, and hook-dependency findings remain visible as warnings.
- CI now runs full-scope Ruff, Pyright, and frontend ESLint.

Validation on this checkout: Ruff passes; Pyright reports 0 errors / 165 warnings; frontend lint
reports 0 errors / 23 warnings; the targeted TypeScript/build and backend checks remain the next
validation pass. The old static-analysis item below is superseded by this entry.

## 2026-08-08 — Docs reconciled against `main`; §1.1 confirmed already shipped

Documentation-only pass on `docs/refresh-open-items`. No behaviour changed. Written after
`feat/activity-view` was fast-forwarded into local `main` (`63cfbe4`) — **which is not yet
pushed; `origin/main` is still `2faa775`.**

### What was wrong, and what it now says

- **`RECOMMENDATIONS.md` §1.1 was stale and has been removed.** It still read "Remaining: flip
  those to preservation assertions," but PR #30 (`bd72d0a`, merged 2026-08-06) had already done
  it: `McpServerSpec` carries `extras`/`extras_dict()`, every transport mapper round-trips them
  via `_extras(raw, {…owned keys})`, `FrontmatterMarkdownCommandCodec` carries unowned
  frontmatter verbatim on `SlashCommand.frontmatter`, and `test_writer_round_trip.py` now
  asserts **preservation** (`test_unknown_frontmatter_keys_are_preserved`,
  `test_frontmatter_comments_are_preserved`, `test_unknown_stdio_fields_are_preserved`,
  `test_unknown_http_fields_are_preserved`, `test_unknown_fields_are_preserved`) plus
  `test_disabled_server_stays_disabled_on_write` — the exact OpenCode force-`enabled=True` case
  §1.1 named as open. Recorded in the shipped-batches list instead.
- **Checked, and there is no equivalent gap in hooks/permissions.** Those families have no
  `extras` plumbing, which looks like the same bug but is not: they are config-subtree families
  whose adapter loads the whole document, mutates in place, and atomically writes it back.
  Probed `claude-code-hooks.enable_hook` with a realistic document — unrelated sibling keys,
  a foreign hook entry, and an unmodeled per-entry key all survive, and the call is idempotent.
  This confirms the 2026-07-27 audit's "n/a for config-subtree families" verdict.
- **Stale test counts refreshed** (was 385/155/263) and the header no longer claims a green
  frontend suite it does not have — see below.
- **`ARCHITECTURE.md` said `ham snapshot`.** No such binary; PR #21 renamed the CLI to
  `harnessam` and fixed the README examples but missed this one.
- **`README.md`'s support matrix contradicted its own invariant.** The paragraph above it says
  harness order is declared once in `SUPPORTED_HARNESS_DEFINITIONS`, but the table was ordered
  Codex-first. Verified the real order at runtime — `['claude', 'codex', 'agy', 'cursor',
  'opencode', 'hermes', 'openclaw']` — and reordered the table to match. `ARCHITECTURE.md §3`
  was already correct.
- **The ruff gate is narrower than the docs implied.** CI runs
  `ruff check harness_asset_manager tests`, so `scripts/` has never been linted — it has 9
  auto-fixable `I001` violations today. Not a regression and not a CI failure; §1.2 now names
  widening the scope as its first remaining step.
- **`handoff.md` had two `(latest)` headings**; the 2026-07-27 one is now plain. The
  2026-07-12 "⚠️ Incomplete — resume here" block carries a SUPERSEDED banner rather than being
  rewritten — this file is an append-only log and its history is left intact.

### Validation state — read this before trusting a "green" claim

Measured on this branch: backend **496 unit + 169 integration pass**, `npm run typecheck`
clean, `npm run build` clean. **`npm test` is 275/278 and exits non-zero.** The three failures
are `SkillDetailContent`, `MarketplaceCliPage`, and `AgentsInUsePage` — async detail renders
that blow the default `waitFor` budget in this container (full run ~13 min, mostly environment
setup). Pre-existing and unrelated to any change here, but note the 2026-08-07 entry below
records this as "274/277," which was a miscount. Added as a Tier-3 item.

### Still open, in priority order

> **SUPERSEDED (2026-08-09)** — all four items below are resolved; see the entry at the top of
> this file for current status and evidence.

1. **Push `main`.** Local `main` is one commit ahead of `origin/main` and the activity view is
   in it. There was never a PR for `feat/activity-view`, so **it has never run in CI** — CI only
   triggers on `main` pushes and pull requests.
2. **Delete seven merged-but-undeleted branches**, contrary to the short-lived-branch rule in
   `CLAUDE.md`: `feat/activity-view`, `feat/mutation-audit-journal`,
   `fix/preserve-unknown-writer-fields`, `feat/harnessam-short-command`,
   `fix/readme-broken-image-links`, `fix/rebrand-skill-manager-remnants`, and
   `claude/harness-asset-manager-headless-cli-jze29n`. Verified via `git cherry -v main <branch>`
   plus the merged-PR list; the only commit not in `main` is `0748b8a` on
   `feat/mutation-audit-journal`, a docs-only handoff refresh that this entry supersedes.
3. **`RECOMMENDATIONS.md §1.2`** — pyright + ESLint + chip the ruff `F401` baseline. Now the
   only open Tier-1 item.
4. **Family-wide auto-adoption is now implemented** on this working branch; run the
   focused adoption tests and review the latest handoff entry before merging.

## 2026-08-08 — Family-wide opt-in auto-adoption implemented

Auto-adoption is now wired for the asset families that have a safe, family-specific
ownership transition:

- **Skills:** when enabled, equivalent unmanaged local directories are ingested into the
  shared store and replaced with directory symlinks. Different revisions and symlinks are
  left for review. The directory is renamed to a temporary backup before the link is made,
  so a failed link creation restores the original copy.
- **Slash commands:** equivalent unmanaged files are registered in the store and sync
  ledger without rewriting the source files. A same-name managed command is never silently
  replaced.
- **MCP:** identical unmanaged observations are adopted through the existing multi-harness
  adoption path; differing configurations remain a manual choice.
- **Hooks and Permissions:** equivalent parseable unmanaged observations are promoted into
  their manifests without rewriting harness-owned config documents.
- **Agents:** existing safe drift repair remains unchanged; Codex rendered-agent adoption
  remains excluded.

Each family has an independent `autoAdopt` setting (Agents on by default; the new family
paths off by default), Settings-page toggles, CLI support, Activity-journal entries, and
read-time reconciliation. The relevant list/detail read triggers reconcile before building
the response, so enabling a family takes effect on the next read without a restart.

The CLI form is `harnessam settings auto-adopt <family> --enable|--disable`, with
`agents`, `skills`, `slash_commands`, `mcp`, `hooks`, and `permissions` as the family
names. Auto-adoption is deliberately limited to the safe cases described above: it does
not overwrite a different managed source, pick a winner between conflicting observations,
or run as a background watcher. Config snapshots and CLI marketplace entries remain
outside the managed auto-adoption families.

For a headless one-shot pass, `harnessam refresh` reads all six managed asset families and
triggers their enabled reconciliation paths; `harnessam refresh --json` emits the refreshed
family names for scripts. It is not a background watcher, so cron or a systemd timer can
invoke it when periodic polling is wanted.

Follow-up to consider: add a user setting for each asset family that defines the default
harnesses to enable when an asset is auto-adopted. Today adoption registers the asset in the
shared store but does not enable it for every harness, so a newly adopted Claude skill still
requires an explicit Codex enablement. The setting should remain a default only — explicit
harness selections and unsupported-harness checks must continue to win.

Validation completed: targeted backend unittest suites pass, the new cross-family adoption
tests pass, Ruff is clean, frontend typecheck is clean, and the Settings frontend tests pass.

## 2026-08-07 — Mutation activity view implemented after PRs #30 and #31 merged

PRs #30 (unknown writer-field preservation) and #31 (mutation audit journal) are merged
into `main`. Follow-on work is implemented on `feat/activity-view`:

- `GET /api/activity` exposes up to 200 validated events newest-first. Journal reads are
  bounded to the final 1 MiB and tolerate malformed JSON, truncated writes, and records
  that do not match the v1 event schema.
- The new read-only Activity page appears in primary navigation, refreshes independently,
  and shows outcome, family, operation, safe parameters, changed paths, timestamps, and
  failure type. It includes empty/loading/error states, responsive styling, theme tokens,
  and English/Chinese copy.
- The generated OpenAPI client, README, architecture, and recommendations are updated.

Validation: 496 backend unit + 169 integration tests, Ruff, frontend typecheck, production
build, generated-contract stability, and all new/changed frontend tests pass. The full
frontend run passed 274/277; three untouched async-detail tests time out in this container
and reproduce when run separately (agents unsupported row, CLI detail, skill document).

Next product work after this branch merges is Stage 4 slash-command auto-repair.
Skills auto-adoption remains Stage 5 and default-off; Codex support remains deferred.

> Historical note: the following 2026-07-27 audit predates the family-wide implementation
> recorded above. Its agents-only, skills-no-op, and slash-command-404 conclusions describe
> the code at that time and are superseded by the latest entry.

## 2026-07-27 — Auto-repair coverage audited: agents only, and `autoAdopt.skills` is a no-op

Audit only, no behaviour changed. **The agents path is fine** — this entry is not about a
defect in it.

### Coverage, verified in code and against the live API

`container.py:347` is the **only** consumer of the kill switch, hardcoded
`auto_adopt_store.is_enabled("agents")`. Nothing else reads it.

| Family | Auto-repair | Why |
|---|---|---|
| agents | **yes** | Stages 1–3; the only wired path |
| skills | **no** | setting exists, zero consumers — see below |
| slash commands | **no** | drift *is* detected (`sync-state.json`, drifted/missing/unmanaged rows) but adoption is user-initiated: `import_unmanaged_command` / `_adopt_target` |
| mcp / hooks / permissions | **n/a** | config-subtree — HAM writes *into* a file it does not own, so there is no binding to clobber |

Two easy misreads, both checked rather than assumed:

- **`reconcile_server` (mcp) and `reconcile_hook` (hooks) are not drift repair.** They are
  user-initiated mutation methods that happen to share the word.
- **Skills are structurally immune to the bug that motivated all of this.** `rename()`
  onto a *directory* symlink fails `ENOTDIR`, so a harness cannot silently clobber a
  skill binding the way it can an agent's `.md`. Skills auto-adopt would be solving a
  different problem, not the same one.

### The defect: `autoAdopt.skills` persists and does nothing

`DEFAULTS` in `auto_adopt.py` declares `{"agents": True, "skills": False}`, and
`set_enabled` accepts any key in `DEFAULTS`. So:

```
PUT /api/settings/auto-adopt/skills {"enabled": true}   -> 200, persists to settings.json
PUT /api/settings/auto-adopt/slash_commands             -> 404 (honest)
```

`skills` is the only family that accepts a write it cannot honour. Verified live: it
round-trips through `GET /api/settings` as `{"agents": true, "skills": true}` while no
code path reads it. The frontend never renders that toggle, so this is API surface only
— but a persisted setting that silently does nothing is worse than a 404.

It is a deliberate Stage 4 placeholder (the `DEFAULTS` docstring says skills is
unimplemented because adopting a skill means `shutil.rmtree` on a real directory of the
user's). The fix is to refuse it until Stage 4 actually lands, not to delete the key.

**FIXED and merged.** `IMPLEMENTED = {"agents"}` now sits beside `DEFAULTS` in
`auto_adopt.py`, so "is a real family" and "we can act on it" are declared in one file
and cannot drift apart. `set_enabled` raises `ValueError` when enabling an unimplemented
family; `SettingsMutationService` maps it to **400**, leaving the existing `KeyError` →
**404** for genuinely unknown families untouched. Disabling stays **200** so a client
syncing the whole settings object does not break, and `GET /api/settings` still returns
both keys. When Stage 5 lands, the change is one entry in `IMPLEMENTED`.

Verified live, all four cases: enable-skills 400 · disable-skills 200 · enable-agents
200 · unknown-family 404. Backend 458 unit + 167 integration.

### `plan-auto-adoption.md` updated as a result

Stages after 3 were **renumbered**, and the reasoning is recorded inline as amendments:

- **Stage 4 is now slash commands**, not skills. Same mechanism as Stage 3 against a
  family that already has the ledger, the classification, and the review UI — it needs
  one extra hash (the store-side baseline) and can then reuse `classify_drift()`
  verbatim, since that is a pure function and family-agnostic.
- **Stage 5 is skills**, demoted. §12 already established that skills *cannot be
  clobbered*, so skills auto-adopt is a convenience feature, not the continuation of
  this plan. Its worst case is `shutil.rmtree` on a real user directory, versus slash
  commands rewriting a file HAM itself authored. Wrong thing to do next on every axis.
- **Stage 6 is Codex**, unchanged, still gated on a lossless TOML round-trip.
- §12's slash-commands verdict was softened from "already has it" — written before Stage
  3 existed and read as "nothing to do" — to "has the ledger and the diagnosis, not the
  repair."
- New rule recorded: **wire the consumer and add the settings key in the same change.**
  That is exactly how `autoAdopt.skills` became a persisted no-op.

## 2026-07-27 — Settings row layout fixed; ARCHITECTURE.md caught up

Merged to `main`. Two small things, both fallout from earlier work.

### The auto-adopt row collapsed its own grid

`.settings-row` is `grid-template-columns: 28px minmax(0, 1fr) auto` — icon, body,
trailing control. The Stage 3 auto-adopt row rendered **two** children, not three. A
missing child does not shift the rest left: `__body` landed in the fixed 28px icon
track, and since text cannot shrink below its longest word, the label overflowed a
column it could never fill — wrapping one word per line — while the toggle, laid out in
the 1fr track, was drawn across it.

Every other `.settings-row` (both storage rows, and `SettingsHarnessCard`) already
passed all three children. Fixed by conforming to the contract — the row gets a `Wrench`
icon like its neighbours — not by special-casing it. The contract is now stated on the
CSS rule itself, and pinned by a test that walks every rendered `.settings-row` and
asserts child count and order; verified it fails `2 != 3` with the icon removed.

**Worth knowing:** a row that genuinely wants no icon must still render an empty
`<span class="settings-row__icon" />`. Dropping the child silently reproduces this bug.

### ARCHITECTURE.md still described the retired packages model

§1, §2 and §4 documented `~/.harness-asset-manager/packages/<name>/{skills,agents}`,
which was retired in the **2026-07-24** agents rebuild. README had already been
corrected (`232c154`); ARCHITECTURE.md had not. §4 now documents the flat layout that
actually exists, including the Stage 1–3 additions (`bindings.json`, `agents-audit.json`,
`agents/conflicts/`) and which directories are safe to delete (only `marketplace/`).

Validation: typecheck clean · backend 451 + 162 · frontend **274** across 61 files ·
build clean · `ruff check harness_asset_manager tests` clean · `codegen:check` no drift.

## 2026-07-27 — Data dir converged on `~/.harness-asset-manager`

**No code changed.** This is an on-disk data migration plus corrections to the
2026-07-26 entry below, which was wrong in three load-bearing ways. The legacy dir is
migrated and verified but **not yet deleted** — see "Remaining" at the end.

### What moved into `~/.harness-asset-manager`

Written directly in the **final flat shape**, never as a legacy shape. This matters:
`_migrate_legacy_layouts` runs on *every* `build_backend_container`, and its trigger is
`any(skills_store_root.iterdir())`. Creating a `shared/` or `packages/local/` under the
new data dir would make the next start `shutil.move` those dirs into `skills/` and leave
every symlink pointing at them dangling. Writing straight to `skills/` disarms it.

| Item | Source | Note |
|---|---|---|
| `skills/{compress-text,delegate,distill-decision}` | legacy `shared/` | the live symlink targets |
| `skills/ogulcancelik--herdr` | legacy `skills/` | full git clone, carried as-is |
| `skills-manifest.json` | merged | 3 entries from legacy `manifest.json` + herdr from legacy `skills-manifest.json` |
| `agents/red-team.md` | legacy `agents/` | |
| `mcp/manifest.json` | legacy `mcp/` | the `codegraph` server |
| `hooks/manifest.json` | legacy `hooks/` | empty (`{"version":1,"hooks":[]}`) |
| `settings.json` | merged | `disabledHarnesses` merged **into** the existing `autoAdopt` via `update_settings_document` |

All three `shared/` skills fingerprinted **exactly equal** to their recorded revisions, so
the manifest carried over verbatim with no drift. `ogulcancelik--herdr` was already
drifted before this migration (recorded `f0df1f93…`, actual `5a95e2b4…`); the recorded
value was preserved rather than silently recomputed, so the app reports it honestly.

**Deliberately not migrated:** the legacy `permissions/manifest.json` held 4 `allow`
rules (`npm run`, `go test ./internal/tui/...`, `git fetch`, `mkdir`). HAM is
denylist-ONLY and `PermissionStore` purges `allow`/`ask` on load, so migrating them
would look like data loss when they vanished on first read. Also dropped: the 44 MB
`marketplace/` HTTP cache (regenerates), `skill-manager.db*` (inert, per 2026-07-24),
`server.log`, `runtime.json`, `.DS_Store`, lock files, and the empty `packages/local/`.

The two duplicate `compress-text` copies were resolved to the `shared/` one — it is what
`~/.claude/skills/compress-text` actually pointed at, and it is the copy whose fingerprint
matches its manifest entry.

### Three corrections to the 2026-07-26 entry

1. **`.migration.lock` does NOT suppress migration.** It is a plain `fcntl.flock` file
   (`atomic_files.py:47`), created fresh on every run. The old entry's step 3 ("clear
   the stale lock or it will suppress the migration path") describes a sentinel that
   does not exist. Nothing needs clearing.
2. **The dotfiles hazard is already dead.** `~/.dotfiles/.claude/` is **empty** —
   commit `a636574` removed `.claude/skills` from that repo. `~/.claude` is a **real
   directory**, not a symlink into dotfiles.
3. **`~/.skill-manager` was never the only copy.** `~/.claude` is itself a git repo, and
   its HEAD still holds the pre-symlink blobs of all three skills. `delegate` and
   `distill-decision` matched HEAD byte-for-byte; only `compress-text` differed.

### Symlinks repointed

`~/.claude/skills/{compress-text,delegate,distill-decision}` now point at
`~/.harnessam/skills/<name>`, matching what `FileTreeSkillsAdapter`
(`enable_shared_package` → `managed_root/<name>` → `store/<name>`) builds itself. Verified
the app **claims** them rather than merely tolerating them: `/api/skills` reports
`displayStatus: "Managed"` with `claude: "enabled"`, not unmanaged.

### Verification after restart, before anything was deleted

`/api/skills` 8 rows (4 managed = the migrated store, 4 unmanaged = the real dirs in
`~/.claude/skills`) · `/api/agents` 1 entry (Red-Team) · `/api/mcp/servers` includes
`codegraph` · `/api/settings` has **both** `autoAdopt` and `disabledHarnesses`, with
`opencode`/`openclaw` showing `supportEnabled: false` and dropping out of every family's
columns · no `shared/` or `packages/` reappeared under the data dir.

Confirmed nothing else on the machine referenced the legacy dir: no symlink under any
harness root pointed into it. `~/.claude.json` and `~/.gemini/antigravity-cli/settings.json`
do contain the string `skill-manager`, but every hit is the stale *project checkout* path
`~/projects/skill-manager` or the old `mode-io/skill-manager` repo name — none is the data dir.

### Remaining

- **`~/.skill-manager` still exists.** Backup at `~/.skill-manager-backup-20260727.tgz`
  (20.7 MB, 2177 entries, verified to contain all three `shared/` skills and every
  manifest). Migration is complete and verified, so removing it is the last step.
- **`~/.claude`'s own git repo is dirty** — 31 entries, including `D` on the three skills
  it tracked before they became symlinks. Left alone deliberately: committing there is the
  user's config-sync decision, not this task's.
- **Env var rename — DONE, on branch `chore/env-var-rename`, not merged.** See the
  section below.
- **Cosmetic, in user content:** `skills/compress-text/SKILL.md:93` tells the reader to run
  `python3 ~/.hermes/skills/compress-text/compress_stats.py`. That path does resolve (the
  Hermes copy exists) but it is harness-specific inside a store copy shared by every
  harness, and it points away from the `compress_stats.py` sitting next to it. Not changed.

### Env vars renamed — branch `chore/env-var-rename`, awaiting merge

All 15 `SKILL_MANAGER_*` vars are now `HARNESS_ASSET_MANAGER_*`, **with the old names
still read as a fallback** for one release. Renaming outright would have silently broken
any machine already exporting one: the old name would simply stop being read, with no
error, so the override would look like it had never been set.

`harness_asset_manager/env_names.py` owns every name and derives each legacy spelling
from the new one via `legacy_name()`, so the pairing cannot drift into a second list that
someone forgets to update. `env_get()` reads new-first, legacy-second and mirrors
`dict.get` exactly — **including returning an explicitly-set empty string** rather than
the default, because the marketplace clients normalize empty values themselves.

Two non-obvious things this surfaced, both now pinned by tests:

1. **An explicit `--state-dir` flag beats both spellings**, because `cli/main.py`
   `runtime_env()` injects the flag *as the new env name*. This makes the obvious
   pressure test ("export the legacy var and pass `--state-dir`") prove nothing —
   whichever wins, it cannot be attributed to the variable. The real test exports the
   var and passes no flag.
2. **Clearing an env var by setting it to `""` does not work here.** `env_get` tests
   membership, so an empty-string *new* name shadows a real *legacy* value and defeats
   the fallback. `isolated_env` pops the keys instead.

`resolve_platform_context` **merges** `os.environ` with the dict it is handed, so tests
that assert a default must clear the environment, not just pass an empty dict. Caught by
reproducing it: with `HERMES_HOME=/opt/hermes` exported, the Hermes default case failed
— on precisely the machines that run Hermes. Hermes' own `HERMES_HOME` is deliberately
**not** renamed; we do not own that name, and it sits last in the three-way precedence.

Verified the fallback suite is not decorative: deleting the legacy branch of `env_get`
fails all 7 of its tests, and restoring it passes them.

**Validation, run independently of the delegate:** typecheck clean · backend 451 unit +
162 integration · frontend 273 across 61 files · build clean · `ruff check
harness_asset_manager tests` clean. Note `ruff check .` reports 9 pre-existing I001
errors in `scripts/*.py` — outside CI's scope (`ci.yml` runs `ruff check
harness_asset_manager tests`), and not introduced here.

End-to-end pressure test reproduced directly, not taken on faith: legacy var alone →
`runtime.json`/`server.log` land in the legacy-named dir; both spellings set → the new
one wins and the legacy dir is never created.

**Delegation note:** agy did the fallback tests + README against the mechanism I had
already landed and pushed, and stayed inside its boundary exactly (tests + README only).
Two things worth recording: my brief contained the wrong pressure test (the `--state-dir`
trap above) and agy did **not** flag it — it was corrected mid-flight. And its new test
files were not hermetic; that was fixed here, not by agy. Its reported test counts were
accurate this time, but were re-run independently anyway.

**Not torn down:** agy pane `wX:p6`, worktree
`../harness-asset-manager-worktrees/agy-env-rename`, branch `agy-worktree-env-rename`.

## 2026-07-27 (later) — Stage 3 shipped: drifted agent bindings now repair themselves

Merged to `main`. `plan-auto-adoption.md` Stages 1–3 are all done. (The stages after 3 were
renumbered on 2026-07-27: slash commands is now Stage 4, skills Stage 5, Codex
Stage 6. None are started.) The entry below covers 1+2 and is
still accurate; this covers what changed on top.

### What it does now

A harness replaces a managed agent symlink with its own copy. On the next list
request, reconcile classifies it and — only where the outcome is provable — repairs it:

- **Identical copy** → relink. There is no content decision to get wrong.
- **Edited copy, store untouched since we linked** → adopt the edit into the store,
  relink every binding for that slug. That copy is the only edit in existence.
- **Both sides edited** → nothing. Ever. Stage 2's diagnosis is what the user sees.
- **Several harnesses, differing edits** → nothing adopted, nothing deleted; each
  divergent copy is *copied* to `<agents_root>/conflicts/<slug>.<harness>.md` and one
  issue names every side. "Newest wins" is explicitly rejected.
- **Codex** is excluded outright — the TOML round-trip is lossy (invariant 3).

Kill switch: `autoAdopt.agents` in `settings.json`, default **on**, read per call so
turning it off stops the *next* reconcile rather than the next restart. Toggle is in
Settings. Every automatic action lands in `<data_dir>/agents-audit.json` and is
surfaced as "Recent automatic repairs" on the agents review page — invariant 5, the
user must be able to see that we moved their content.

### Traps worth knowing before touching this

- **`file_lock` is not re-entrant.** It is `fcntl.flock(LOCK_EX)` on a freshly opened
  fd, so taking it twice in one process on the same path deadlocks. Every ledger and
  audit mutation takes its own lock internally, so reconcile holds a *separate*
  reconcile lock and never holds theirs. Do not "simplify" these into one lock.
- **`TargetResolver` moved to `adapters.py`** — reconcile needs it too, and importing
  it from `inventory.py` made the two modules circular.
- **Conflict copies live in a subdirectory on purpose.** `AgentStore.scan()` globs
  `agents_root.glob("*.md")`, top level only; a preserved copy written next to the
  store entries would be read back as an agent named `<slug>.<harness>.conflict`.
- **Reconcile ordering inside the store-write callback.** `store.write_raw()` during
  adopt fires the Stage-1 rebaseline callback *while reconcile holds its lock*. It is
  a no-op there because the bindings are still clobbered (not live) at that moment,
  and the fresh records are upserted after relinking. Different lock paths, so no
  deadlock — but it is the sharpest edge in this code, and only the integration tests
  reach it (the unit tests build an `AgentStore` without the callback).

### Delegation notes — agy did the engine, I did the wiring and the adversarial tests

Split deliberately: agy got `reconcile.py` + `audit.py` + unit tests against a written
interface, with an explicit off-limits list (`container.py`, `paths.py`, `api/`,
`frontend/`, the plan and this file). It respected the boundary exactly — the branch
touched only the four files it was allowed. It then did the frontend half against a
contract I had implemented and regenerated **first**, which is the ordering that stops
the invented-endpoint failures recorded further down this file. Its client test asserts
the fully composed URL (`toBe("/api/settings/auto-adopt/agents")`), not `.includes`.

Two things I changed after review, neither reported by agy:

1. **The mixed adopt path deleted clean harness copies without re-verifying them.**
   The all-clean path re-hashes immediately before unlinking; the adopt path did not,
   so a harness writing again between classification and deletion would have its edit
   discarded unweighed. It now refuses and leaves the file.
2. Banner/section copy corrected to match the real page titles.

The integration tests are mine, and cover what agy's unit tests structurally could
not: the store-write callback firing inside the reconcile lock, two harnesses with
differing edits over the real API, the kill switch, and idempotence across repeated
list requests. **Do not take a delegate's pass counts on faith** — agy reported 158
integration tests, which was its worktree's stale count; `main` had 162.

### Also fixed here: settings writers were clobbering each other

Adding a second key to `settings.json` exposed it. `HarnessSupportStore._write`
serialised **only** `disabledHarnesses`, so any other key was deleted on the next
harness toggle. Both writers now go through `settings_file.update_settings_document`,
which read-modify-writes under the shared lock and preserves keys it does not own —
the same "unknown keys survive" rule the agent frontmatter writer had to learn twice.
This was latent before today; nothing else was writing that file.

### Validation at completion, run independently

typecheck clean · backend 445 unit + 162 integration · frontend 273 across 61 files ·
build clean · `codegen:check` no drift · `ruff check` clean.

**Not torn down:** agy pane `wX:p3`, worktree
`../harness-asset-manager-worktrees/agy-agents-reconcile`, branch
`delegate/agy-agents-reconcile` (merged).

## 2026-07-27 — Auto-adoption Stages 1+2 shipped; defect #1 fixed; other families assessed

Branch `feat/agent-binding-ledger` off `main` (not merged yet). Implements
`plan-auto-adoption.md` Stages 1 and 2, and fixes defect #1 from the entry below.
**Stage 3 is not started and should not be started as a continuation** — it is the
first stage that can destroy content, and it needs a deliberate go-ahead.

### What shipped

- **`application/agents/ledger.py`** — `bindings.json` in the data dir (resolved via
  `AppPaths.bindings_ledger_path`, so it moves with the pending `~/.skill-manager`
  retirement rather than needing a second migration). Modelled on
  `SlashCommandSyncStateStore`, which had already solved this for slash commands.
  Every read path is total: missing / truncated / malformed → "no record" → the
  pre-ledger prompt-the-user behaviour. Never a destructive default.
- **`classify_drift()`** — §4's decision table as a pure function, one unit test per
  row. Stage 2 *names* drift and takes no action; the inventory reports
  clean-clobber / one-sided / two-sided in the binding cell and as an issue.
- **Codex** gets detection without automation (§5): `rendered_sha256` recorded at
  write time, local edits reported, never adopted.
- **Defect #1 fixed.** `atomic_write_text` now refuses a symlink destination
  (`os.replace` onto one destroys the link — the same mechanism that breaks our
  bindings, aimed inward). Forecloses the class permanently for any future caller.

### The two design rules that are NOT in the original plan — read before Stage 3

Both are amended into `plan-auto-adoption.md` inline, marked **AMENDED**.

1. **Rebaseline only *live* bindings.** Plan §3 said "store content changing for a
   slug → refresh `store_sha256` for all its harnesses." Taken literally that loses
   data: link (baseline A) → harness clobbers and edits → user edits in the HAM UI
   (store → B) → a blanket refresh makes `hash(store) == ledger` true again, row 3
   fires, and the auto-adopt discards the UI edit. Restricting the refresh to
   bindings that are still symlinks makes that case fall to row 4 and prompt.
   `test_store_edit_does_not_rebaseline_a_clobbered_binding` proves it.
2. **One owner for the baseline.** The routers call `agents_store.create/update`
   *directly*, bypassing `AgentMutationService`, so the refresh hangs off
   `AgentStore(on_store_write=…)` and is wired once in `container.py`. Binding
   records themselves are written in the mutation service — the adapters are shared
   with the read-only inventory, so they are the wrong place.

### Behaviour change outside the agents family — flagged deliberately

The symlink guard needed an opt-in for the legitimate case, and the config writers
(mcp / hooks / permissions / slash / codex) now pass `follow_symlinks=True`: they
resolve the link and replace the real file behind it. **This is a real improvement
for this machine specifically** — `~/.claude` is symlinked into `~/.dotfiles`, and
the old behaviour silently replaced such a symlink with a regular file. Covered by
`test_a_symlinked_config_is_written_through_not_replaced` (verified meaningful: it
fails without the opt-in). Everything HAM writes into its *own* data dir keeps the
strict default.

One known limit, not worth fixing now: `_lock_path()` still derives from the link
path, so two different symlinks pointing at the same real config would not serialize
against each other. Exotic; previously impossible only because each link got its own
materialized file.

### Other asset families — assessed, verdict is "nothing more to build"

Full reasoning in the new `plan-auto-adoption.md` §12. Summary: **agents** needed it
(built); **slash commands** already have it (`sync_state.json` + the drifted/missing/
unmanaged review rows — its only gap is a single hash with no store-side baseline, so
`adopt_target` stays a user decision); **skills** are structurally immune (directory
symlinks fail `rename()` with `ENOTDIR`); **mcp / hooks / permissions** are
config-subtree — HAM writes *into* a file it does not own, so there is no binding to
clobber and no whole-file hash that means anything. External-edit detection for those
is already the config-snapshots service's job. Do not build a second one.

`hash_file` moved to `harness_asset_manager/hashing.py` and is now shared between the
slash sync state and the agents ledger, so the two on-disk hash formats cannot drift.

### Frontend

`GET /api/agents` has always returned `issues[]`, and **nothing rendered it** — the
array was typed in `api/types.ts` and dropped on the floor. Stage 2's whole value is
the user not having to *notice* drift, so it is now surfaced: a compact count banner
on In Use, and the full verbatim reasons on "Agents to review". No API or schema
change (`codegen:check` clean). Delegated to a Sonnet subagent against the MCP
precedent; independently re-verified here, and its banner copy was corrected to match
the real page title rather than the sidebar label.

### Validation at completion, run independently

`npm run typecheck` clean · backend 422 unit + 158 integration · frontend 269 across
61 files · `npm run build` clean · `npm run codegen:check` no drift · `ruff check`
clean.

## 2026-07-27 — Symlink-durability audit: 3 defects to fix, 1 plan written

Came out of a filesystem-durability review of how bindings survive harnesses
writing their own config. Nothing here is broken *right now* — all three are
latent, and all three were verified in code, not inferred. **No code was changed.**

New: **`plan-auto-adoption.md`** — automatic re-adoption of drifted bindings, so a
harness editing an asset does not require a manual re-adopt. Read it before
touching anything in `application/agents/` or `application/skills/`.

### The mechanism everything below turns on

A tool that rewrites its own config writes to a temp file then `rename()`s onto the
target. `rename()` replaces the **symlink itself** with a regular file. Verified
empirically:

- `rename(file, file-symlink)` → symlink destroyed, target orphaned.
- `rename(dir, dir-symlink)` → fails `ENOTDIR` (errno 20). Directory symlinks are
  structurally immune.
- `rename(file, dir-symlink/file)` → resolves through the link, lands in the target.

So **skills (directory bindings) are safe and agents (file bindings) are not.**
`AgentHarnessAdapter.enable()` does `path.symlink_to(target)` where `binding_path()`
is `<output_dir>/<slug>.md` — a file symlink, for Claude/Cursor/AGY/OpenCode.

The damage is currently *safe and visible*, which is worth preserving: `owns()` →
`is_symlink()` → `is_enabled()` derives from the filesystem, so it cannot go stale;
a clobbered agent reads as disabled and appears in `unmanaged_paths()`. And
`enable()` already refuses with `real file exists at {path}; will not overwrite`
rather than blowing through it. **Do not "simplify" the derived-state model or those
refusals** — they are the reason this is an inconvenience instead of data loss.

### 1. `atomic_files.py:20` is the same clobber mechanism, aimed inward

`atomic_write_text()` ends in `os.replace(tmp_path, path)`. That is precisely the
operation that destroys a symlink.

Safe **today** purely by where it is pointed: rendered Codex files (real files by
design) and store files. It is one refactor from being pointed at a *binding* path
— someone adds "edit agent from the UI" and reaches for the obvious helper — at
which point HAM silently converts its own symlink into a real file and orphans the
store entry, with no error.

**Fix:** guard inside `atomic_write_text` — refuse when the destination is a
symlink, or require the caller to opt into resolving through it. A few lines, and it
forecloses the entire class permanently for agents and any future file-shaped asset.
Cheaper than any structural alternative. Do this one first; it is independent of
`plan-auto-adoption.md`.

### 2. `agents/adapters.py:20-24` docstring encodes an assumption that is false

The `AgentHarnessAdapter` docstring says, of the symlink model:

> the harness reads the same markdown+frontmatter the store holds … editing the
> store file updates every harness at once.

True as written, and the inverse is what people will assume: that editing *through
a harness* writes into the store. That only holds for a harness that writes **in
place**. Any harness whose editor writes atomically destroys the binding instead —
Claude Code's `/agents` editor is the concrete candidate.

**Fix:** state the inverse risk in the docstring. The assumption is load-bearing and
currently invisible to the next reader.

**Untested assumption worth one experiment:** nobody has confirmed whether Claude
Code's `/agents` editor writes atomically. Right now `~/.skill-manager/agents` holds
one agent (`red-team.md`) with **zero bindings in any harness dir**, so nothing is
exposed. When the first agent is bound: link it, edit via `/agents`, then check
whether `~/.claude/agents/<slug>.md` is still a symlink. That single test decides
whether this is operational or theoretical.

### 3. Codex agent round-trip is lossy

`adopt()` for a `renders` harness goes `parse_codex_agent()` →
`render_agent_document()`, which preserves only `name`, `description`, `prompt`.
Any other TOML the user added is dropped. Combined with the already-documented
*"**No drift detection**: re-enabling overwrites local edits to a rendered file"*,
this makes Codex unsafe to include in any automatic adoption — it is explicitly
scoped out of `plan-auto-adoption.md` v1 for this reason.

**Fix (prerequisite for Codex automation):** preserve unknown TOML keys through
parse/render, with a property test asserting `render(parse(x)) == x`.

### 4. Store path name discrepancy — three names in play

Live install writes `~/.skill-manager/` (`shared/`, `agents/`, `manifest.json`);
`ARCHITECTURE.md` §1 and §2 say `~/.harness-asset-manager/packages/`; the user
refers to it as `~/.harnessAM/`. There is a `.migration.lock` in the live dir.

Already tracked — see the **2026-07-26** entry on retiring the `~/.skill-manager`
data dir. Flagging it again only because `plan-auto-adoption.md` adds a new file
(`bindings.json`) to that directory: **resolve it through whatever resolves the data
dir, do not hardcode**, and land it after the rename or it will need moving twice.

## 2026-07-28 — #11 fixed and merged; #14 confirmed still blocked

### #11 — DONE. Merged to `main` at `cab72ae`.

Root cause found, not worked around: jsdom 30 now correctly computes `display: inline` for
unstyled `<span>` elements (jsdom 26 returned `""`, empty string). `dom-accessibility-api`'s
accessible-name separator logic only inserts a space between adjacent elements when
`display !== "inline"` (`accessible-name-and-description.js:252-253`), so the jsdom fix exposed
that the sidebar's label/count spans (`<span>Skills</span><span>13</span>`) have **never** had a
real space between them in the accessible name — screen readers have always announced "Skills13",
not "Skills 13". The old jsdom bug was accidentally masking a real, pre-existing a11y gap; this
was a correctness improvement in jsdom, not a regression the app introduced.

Fixed by inserting an explicit space text node between label and count in
`frontend/src/components/Sidebar.tsx` (`NavGroup`, `SidebarTopLink`, `SidebarLink`). Two things
worth knowing if this pattern comes up again:
- A **leading space inside the count `<span>`** (`{" "}{count}`) does *not* work — the accname
  algorithm trims/normalizes whitespace per-subtree before concatenating, so it gets silently
  dropped. The fix has to be a **separate sibling text node** between the two spans (a `<>{" "}
  <span>…</span></>` fragment).
- Verified in a real browser (Playwright/Chromium against the built app, not just jsdom) that the
  whitespace-only sibling text node doesn't get promoted to a CSS Grid item — per spec, text runs
  that are entirely whitespace aren't wrapped into an anonymous grid item, so `.sidebar-group__header`'s
  `display: grid` 4-column layout is unaffected. Screenshot-verified: chevrons and counts still
  align correctly.

Rebased the dependabot branch onto `main` (it predated the react-query 5.101.4 and
npm-distribution-channel-removal commits), landed the fix on top, then merged. Full suite green
independently: `npm ci`, `audit:check`, `codegen:check`, `typecheck`, 265 frontend tests, 387+155
backend tests, build. PR #11 closed with the root-cause explanation; dependabot branch deleted.
**Same run-together-accessible-name pattern likely exists elsewhere** (matrix cells, badges) —
not swept, since no other test happens to assert a spaced name on adjacent inline elements. Not
in scope for #11; flag if it comes up again.

### #14 — still blocked upstream, confirmed with fresh evidence, PR left open

Re-checked today: `npm view openapi-typescript versions` shows `7.13.0` is still the latest
(unchanged since #14 was filed), and `npm view openapi-typescript@latest peerDependencies` still
shows `{ typescript: '^5.x' }`. `npm ci` on the branch fails with a single ERESOLVE — confirmed no
other dependency in the project (`vite@8.1.5`, `vitest@3.2.4`, `@vitejs/plugin-react@6.0.4`) pins
a `typescript` peer range, so `openapi-typescript` is the sole blocker, not one of several.

Went further than an install check: installed the branch with `--legacy-peer-deps` in a
throwaway worktree (not landed) to see what forcing it would actually do. `npm run typecheck`
fails hard across 30+ files under real TS 7.0.2 — `TS2305: Module '"@testing-library/react"' has
no exported member 'screen'` (and `fireEvent`/`waitFor`/`within`), plus new implicit-`any` errors.
`npm run build` "succeeds" anyway because Vite/esbuild strips types without checking them — so
`npm run typecheck` is the only gate that would catch this, and forcing the install would have
shipped it broken. This confirms the prior handoff's "don't force it" instinct with hard evidence
rather than leaving it as a guess.

**Next steps:** re-run `npm view openapi-typescript versions` next time this is picked up. Stays
blocked until it (or whatever is causing the `@testing-library/react` type-resolution break under
TS7) ships support. PR #14 left open with findings commented; branch untouched.

## 2026-07-26 — TODO: retire the `~/.skill-manager` data dir (stale slug, and it is unversioned)

**Not started.** Filed from a vibebox session that tripped over the live symlink chain. Nothing
here has been changed — this is a note, not a shipped change.

The project rename to `harness-asset-manager` landed in the code (`APP_NAME` in
`harness_asset_manager/paths.py`, `pyproject.toml`, package dir), but the on-disk state did not
follow it cleanly. There are now **two data dirs**, and the one the code resolves to is not the
one that is actually being loaded:

| Path | State |
|---|---|
| `~/.harness-asset-manager/` | What `_base_dirs()` resolves to today (macOS: `~/.{APP_NAME}`, since no `~/Library/Application Support/harness-asset-manager` exists). `skills/` is **empty**. |
| `~/.skill-manager/` | Legacy dir. Holds the skills that are actually live, in the pre-package `shared/` layout, plus a partial `skills/` migration and a stale `.migration.lock` (2026-07-24). |

The live chain, which is what makes this load-bearing:

```
~/.claude/skills  ->  ~/.dotfiles/.claude/skills/   (real dir, tracked in the dotfiles repo)
    compress-text, delegate, distill-decision  ->  ~/.skill-manager/shared/<name>
    distill-function, dossier-delegate, herdr-orchestration, seen   (still real dirs)
```

So Claude Code loads three skills out of `~/.skill-manager/shared/`, which the renamed code no
longer points at.

**Two problems, in priority order.**

1. **`~/.skill-manager/` is not a git repo and has no remote.** It is the only copy of those three
   skills. Worse, because the dotfiles repo tracked them as regular files before they were
   replaced by symlinks, both `~/.dotfiles` and `~/.claude` currently show them as *deleted* — so
   a routine "commit and push my config" would record their deletion and propagate it to every
   other machine, where the symlink targets do not exist. Get the dot folder under version
   control before anything else.

2. **The slug is stale.** `~/.skill-manager` should be `~/.harness-asset-manager`. Note the env
   var names are stale in the same way and were missed by the rename:
   `SKILL_MANAGER_SETTINGS_PATH` and `SKILL_MANAGER_STATE_DIR` (`paths.py:11-12`), plus
   `skill-manager.db*` inside the legacy dir.

**Suggested order when picking this up:**

1. Put `~/.skill-manager/` under git (or copy it somewhere backed up) — it is the single point of
   failure and everything below can destroy it.
2. Decide which dir wins. `~/.harness-asset-manager/` matches the code but is empty;
   `~/.skill-manager/` has the data in a legacy layout. Migrating the data across, then letting
   `container.py`'s `shared/` → `skills/` migration run, is likelier to be right than repointing
   the code backwards.
3. Clear the stale `.migration.lock` in whichever dir survives — it has been sitting since
   2026-07-24 and will suppress the migration path in `container.py`.
4. Rename the `SKILL_MANAGER_*` env vars, keeping the old names as fallbacks for one release.
5. Only then resolve the dotfiles/`~/.claude` git state, so the deletions get recorded
   deliberately (as a move to symlinks) rather than as data loss.

## 2026-07-25 — User-Level Native Config Snapshot Service & Web UI Controls

**Shipped on `main`**. All backend services, CLI commands, Web UI controls, unit/integration tests, and documentation are complete.

- **Storage Location**: Canonical baselines and timestamped snapshots stored under `~/.harnessam/configs/<harness_id>/`.
- **Target Harness Config Matrix**:
  - `claude`: `~/.claude.json`, `~/.claude/settings.json`
  - `codex`: `~/.codex/config.toml`
  - `agy`: `~/.gemini/antigravity-cli/settings.json`, `~/.gemini/antigravity-cli/mcp_config.json`, `~/.gemini/config/mcp_config.json`, `~/.gemini/config/hooks.json`
  - `cursor`: `~/.cursor/mcp.json`, `~/.cursor/hooks.json`
  - `opencode`: `~/.opencode/opencode.jsonc` (or `~/.config/opencode/opencode.json`)
  - `hermes`: `~/.hermes/config.yaml`
  - `openclaw`: `~/.openclaw/openclaw.json`
- **Triggers**:
  1. *Pre-Write / Pre-Sync*: Automatically takes a snapshot prior to HAM writes.
  2. *Webapp Launch / Startup Scan*: Hash-checks existing native files vs latest snapshot; captures external edits automatically.
  3. *On-Demand*: CLI (`ham snapshot` / `python -m harness_asset_manager snapshot`) or Web UI "Take Snapshot Now" button.
- **Web UI Component**:
  - Added `ConfigSnapshotsSection` component to Settings Page ([SettingsPage.tsx](file:///Users/hgill/projects/skill-manager/frontend/src/features/settings/screens/SettingsPage.tsx)).
  - Shows active snapshot baselines, SHA-256 prefixes, trigger badges (*Manual*, *External*, *Pre-Write*), timestamps, and a 1-click **Take Snapshot Now** button.
- **Safety & Storage Policy**:
  - SHA-256 hash deduplication (skips duplicate snapshot creation if content is unchanged).
  - Secret redaction pipeline (redacting API keys, bearer tokens, OAuth secrets prior to export/backup).
  - Preserves real files in harness home folders to avoid atomic `rename()` symlink severing.
- **Verification**:
  - Backend pytest suite: 543 / 543 passed.
  - Frontend Vitest suite: 265 / 265 passed across 61 test files.
  - `npm run typecheck` and `npm run build` clean.

---

## 2026-07-25 — Unforking, Project Rename, Sidebar Simplification & Denylist-ONLY Permission Model

All work landed cleanly on `main` at `execsumo/harness-asset-manager`.

- **Standalone Repository & Renaming**:
  - Un-forked from `execsumo/skill-manager` into a standalone public repository: [`execsumo/harness-asset-manager`](https://github.com/execsumo/harness-asset-manager).
  - Renamed Python package directory from `skill_manager` to `harness_asset_manager`.
  - Updated `pyproject.toml` (`harness-asset-manager`), CLI binary entry points, `package.json`, Homebrew formula template, PyInstaller spec, and all import references across 225 files.
  - Pushed all branches and release tags (`v0.1.0` through `v0.3.1`).
- **Branch Cleanup**:
  - Deleted merged branch `delegate/agy-agents-ui` locally and remotely.
  - Pruned remote tracking branches `origin/Desktop-app` and `origin/Fix-Scan-Config-page`.
  - Merged `permissions-ux-redesign` into `main` and deleted the feature branch.
- **Simplified Single-Link Sidebar Navigation**:
  - Converted **Permissions** into a direct top-level link in the sidebar (`topLinks`), removing obsolete nested sub-links (`All` / `Needs Review`).
  - Aligned `.sidebar-top-link` CSS typography (text color `var(--color-text)`, font size `0.92rem`, font weight `600`) to match group headers (*Agents*, *Skills*, *Slash Commands*, *MCP*, *Hooks*, *Marketplace*).
- **Strict Denylist-ONLY Permission Model**:
  - Replaced legacy allow/ask harmonization with a strict **Denylist-ONLY model** across Claude Code, Antigravity, and Codex.
  - `allow` and `ask` decisions are rejected by mappers with `"HAM operates in Denylist ONLY mode"`.
  - Removed decision filter toggles from `PermissionsPage.tsx`.
  - `PermissionStore` automatically purges legacy `allow`/`ask` records on load and rewrites `permissions/manifest.json` on disk.
- **Verification**:
  - Backend pytest suite: 541 / 541 passed.
  - Frontend Vitest suite: 265 / 265 passed across 61 test files.
  - `npm run typecheck` and `npm run build` clean.

---

## 2026-07-24 — RECOMMENDATIONS.md Tier 1 shipped

All four Tier 1 items from `RECOMMENDATIONS.md` landed on `main` in merge `98c3417`
(short-lived branch `fix/tier-1-hardening`, now deleted).

- **Audit gates**: react-router bumped to 7.18.1 (clears all current advisories except
  `GHSA-qwww-vcr4-c8h2`, which is RSC-mode-only and N/A for this client-only SPA —
  allowlisted with justification in `scripts/audit_gate.cjs`). `npm run audit:check` now
  runs in `frontend-validate`; `pip-audit` runs in `backend-compat`.
- **Request guards** (`harness_asset_manager/api/guards.py`): ASGI middleware rejects non-loopback
  `Host` headers (DNS rebinding) and non-loopback `Origin` on mutations (simple-request
  CSRF). Non-browser local clients send no `Origin` and are unaffected. `--host` now
  requires `--allow-remote` for non-loopback binds, with a loud warning; `start` passes it
  through. Chosen over a per-launch token: equal browser-side protection, zero plumbing,
  Vite dev flow untouched.
- **Static serving**: SPA catch-all uses `is_relative_to(dist_root)`; regression test with
  a `dist-secret` decoy sibling (`tests/integration/test_static_frontend.py`).
- **Deletion pass**: removed the fully-unused `harness_asset_manager/db/` package (was creating and
  migrating `harness-asset-manager.db` on every launch with zero readers), the removed LLM-scan
  feature's `scan` extras + `data/prompts/` payloads + PyInstaller spec entry, and the
  duplicate `certifi` pin. Marketplace clients now derive User-Agent from `__version__`.

Validated: typecheck, 349 unit + 155 integration, 263 frontend tests, build,
`codegen:check`, `audit:check`, version sync — all green.

Note for future sessions: existing user data dirs may still contain a `harness-asset-manager.db`
file from before the removal. It is inert; leave it (do not delete user files silently).

---

## 2026-07-24 — `permissions-ux-redesign` triaged: half salvaged, half deliberately dropped

The branch had sat 4 weeks and 87 commits behind `main`, unpushed. It is now backed up at
`fork/permissions-ux-redesign` — **do not merge it**.

**Salvaged (landed on `main`):** `c2d2770`, the decision/applied-state split. Permissions
carry a decision (allow/ask/deny) *and* a per-harness applied state; the UI reused
"Enabled/Disabled" for the second on rows that already showed the first, so a deny rule
offered "Enable all". The applied-state axis is now Applied / Not applied / Differs /
Untracked. It also removed the In Use matrix's bulk-select column, which was decorative —
the page passed `checkedIds={new Set()}` and `onToggleChecked={() => {}}`. Needs Review
keeps its checkboxes; those are wired to real state.

**Dropped on purpose:** `d3005b1`, the "Tier 2 pilot" that merges Permissions' In Use and
Needs Review into a single page. It contradicts the entry below — the Agents rebuild
standardized every family on the two-view pattern, which Permissions still uses and the
sidebar still renders as two children. "Tier 2" appears in no plan doc. **If you want a
single-page inventory, that is a cross-family design decision to make deliberately, not a
branch to merge.** A trial merge also produced 5 conflicts and would orphan
`PermissionsNeedsReviewPage.test.tsx`, which postdates the branch.

Two resolutions worth knowing when reading the salvage commit: `MatrixTable` did **not**
regain the branch's `hasCheckboxColumn` prop (it existed only to align the `<colgroup>`
that `b967504` deleted), and Needs Review kept `main`'s matrix layout over the branch's
older card layout.

---

## 2026-07-24 — One canonical harness order; disabled harnesses leave the matrices

**Landed on `main` and running.** Reported symptom: the Slash commands matrix led with
OpenCode, and OpenCode still had a column there despite being switched off in Settings.

### The ordering rule, now stated once

Harness order is **Claude, Codex, Antigravity, Cursor, OpenCode, Hermes, OpenClaw**, and
it lives in exactly one place: the declaration order of `SUPPORTED_HARNESS_DEFINITIONS`
in `harness_asset_manager/harness/catalog.py`. Every family reaches it through
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
  `../harness-asset-manager-worktrees/agy-agents-fe`): flat `/agents/use` + `/agents/review`
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
  works). agy pane `wP:p4` + worktree `../harness-asset-manager-worktrees/agy-package-store`
  kept alive for Stage 4.
- **Also on `main`:** upstream mode-io merge `0b54469` (came in mid-session from
  another agent) + `9224d79` fixing its artifacts (duplicate hermes mapper key,
  duplicate README Hermes cell, upstream png). Fork features verified intact.
- **Stage 2 (agents family + Claude compile) — DONE, merged as `5f8f808`.** Agents
  live in `packages/<slug>/agents/*.md`; `AgentsService` (scan/resolve/compile) in
  `harness_asset_manager/application/agents/`; `GET /api/agents` +
  `POST /api/agents/{ref}/compile` (`dryRun`, `projectDir`); provenance marker +
  refuse-to-overwrite-foreign-files; OpenAPI regenerated. 11 new unit tests.
- **Stage 3 (cursor/codex targets + degradation reports) — DONE, merged as `dec09ae`.**
  Cursor → `<project>/.cursor/rules/harness-asset-manager.<slug>.mdc` (projectDir required);
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
  `../harness-asset-manager-worktrees/{agy-package-store,agents-family}`, merged branches
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
- **Skills**: categorized `~/.hermes/skills/<category>/<skill>/`, shared under `harnessam`; the legacy `harness-asset-manager` category remains readable.
- **Hermes skill discovery**: reads `.hub/lock.json` + `.bundled_manifest`; excludes
  bundled/official/optional skills, while unclassified local/self-learned skills remain
  discoverable and adoptable; external hub provenance is retained when available.
  `origin_harness` provenance is threaded through the store manifest.
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
  Done in the backend presenter (`harness_asset_manager/application/settings/presenters.py`,
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
  - Home source: `homeDir` added to `GET /api/health` (`harness_asset_manager/api/routers/health.py`).
  - `useHomeDir` reads context (default `null`), so path-displaying components still render in
    tests without a QueryClient — paths just pass through unabbreviated.

- **Hermes Agent added as a harness** (`harness_asset_manager/harness/catalog.py`), CLI probe `hermes`,
  root `~/.hermes`. It is **catalog-driven, so it flows app-wide**, not settings-only. Verified
  live: appears in Settings, Skills inventory/detail, MCP inventory columns, and slash targets.
  - Skills: `~/.hermes/skills` (env override `SKILL_MANAGER_HERMES_ROOT`).
  - MCP: `~/.hermes/mcp.json`, subtree `mcpServers`, codec `hermes`
    (`HermesMapper(_TypedMcpServersMapper)` in `harness_asset_manager/application/mcp/mappers.py`).
  - Slash: `~/.hermes/commands`, frontmatter Markdown. **Required extending the closed slash
    allowlist** — `SlashTargetId` Literal (backend `models.py` + `api/schemas/slash_commands.py`,
    frontend `api/types.ts`) and `TARGET_ORDER` in `slash_commands/targets.py`. This gap silently
    dropped Hermes from slash targets until fixed; regenerated `openapi.json`/`generated.ts`.
  - Logo: `assets/harness-logos/hermes-logo.svg` (+ `frontend/src/assets/...`), from lobehub,
    re-filled `#7d8590` (theme-neutral; logos render as `<img>` so `currentColor` won't inherit).

- Validation: `npm run typecheck`, `bash scripts/test_backend.sh` (300 + 127), `npm test` (269),
  `npm run build`, `npm run codegen:openapi` — all green.

### Hermes follow-up — retired from the roadmap

The remaining Hermes hooks, MCP, permissions, and live-install verification work is intentionally
scrapped as of 2026-08-10. Do not resume it. The historical implementation notes remain below
only to explain past changes; active work is limited to Claude Code, Codex, Agy, and Cursor.

### Housekeeping

- **Nothing is committed.** Changes are in the working tree on `main`. Per `CLAUDE.md`, land via a
  short-lived branch off `main` → merge back → delete. Run the full validation suite before commit.
- **Restart the running instance** to pick up backend changes; `frontend/dist` is already rebuilt.
- `README.md` updated (Hermes row + provisional footnote). `README.zh-CN.md` was **removed** from
  this fork (not needed); its link was dropped from `README.md`.

---

## 2026-07-25 — Tier-1 recommendations batch

Landed the high-value Tier-1 recommendations from `RECOMMENDATIONS.md` (see that file for the
open remainders). Full suite green at commit time: backend unit 385 + integration 155, frontend
263, `npm run typecheck` clean, `ruff check` clean, OpenAPI drift gate clean.

1. **Supply-chain automation (was §1.4, shipped).** Added `.github/dependabot.yml` (npm + pip +
   github-actions, weekly, grouped) and SHA-pinned every action in `ci.yml` / `release.yml` with a
   `# vN` comment for auditability. No bare `@vN` refs remain.

2. **Golden writer round-trip tests (was §1.1, partial).** New `tests/unit/test_writer_round_trip.py`
   pins, for the slash frontmatter codec and every MCP transport mapper: idempotency, owned-field
   preservation, and a *characterization* of the unknown keys/comments currently dropped
   (OpenCode's force-`enabled=True` is called out explicitly). The data-loss surface is now locked;
   the remaining work is to flip those to preservation assertions (hardening the codecs/spec to
   carry unknown fields), tracked in `RECOMMENDATIONS.md §1.1`.

3. **Ruff lint gate (was §1.2, partial).** `[tool.ruff]` in `pyproject.toml` enforces `I` (import
   sorting — applied across the tree) + `F` (pyflakes), with `F401`/`F821`/`F841` baselined green
   (documented in-config). `requirements-dev.txt` pins ruff; a "Backend lint" step runs it in CI.
   A blanket `ruff --fix` was attempted and **reverted** — it rewrote import paths and broke test
   collection, so the baseline cleanup is deferred to a verified per-module pass. pyright + ESLint
   are the remaining §1.2 slice.

4. **Hermes slash provisional label (was §1.3, partial).** The Hermes `slash_commands` binding
   in `harness/catalog.py` now carries a provisional `support_note` surfaced via
   `SlashTarget.supportNote`. MCP/hooks labeling still needs a `support_note` threaded through the
   typed MCP/hooks read models (OpenAPI regen) — see `RECOMMENDATIONS.md §1.3`.

### Notes

- isort-only (`ruff --select I001 --fix`) reorganized imports across ~120 files; mechanical and
  verified (suite green). The combined/auto fixes were not kept.
- `requirements-dev.txt` is new; the runtime `requirements.txt` is unchanged, so `pip-audit` scope
  is unchanged.

## 2026-08-16 — Asset-family page consolidation (shipped), sidebar consolidation (NEXT STEP)

Merged at `8a65135`. Five of six families now use **one inventory page** with a URL-backed `?status=`
filter instead of separate "In Use" and "Needs Review" pages: permissions (pre-existing), hooks
(pilot), agents, skills, slash-commands. Validation on merged `main`: frontend **300/300**, backend
suite **exit 0 / 81% coverage**, typecheck + build clean, lint 0 errors.

This also resolves the open question recorded on 2026-07-24 (see the `permissions-ux-redesign` triage
entry above), which asked that a single-page inventory be "a cross-family design decision to make
deliberately, not a branch to merge". It was made deliberately; this is the record.

**MCP is deliberately excluded.** Its review view is not the same inventory filtered by `entry.kind` —
it hits `GET /mcp/unmanaged/by-server`, returning identity-grouped *sightings* with an `identical`
flag, and adopts via `POST /mcp/unmanaged/adopt` with a config-choice dialog for conflicting configs.
Unifying it requires reshaping the backend response, not a UI refactor. Start there, not in the frontend.

### The established pattern

1. One page per family at `/<family>`; status in the URL so views stay deep-linkable.
2. Bulk adopt kept and **untracked-only** — checkbox renders only on `kind === "unmanaged"` rows; the
   dock appears only when ≥1 is selected. (The permissions merge had dropped bulk-select entirely.)
3. One row component switching on **cell state**, not row kind — untracked cells stay clickable
   (`state: "observed"`), not dead disabled markers.
4. Routes live in `features/<family>/routes.tsx`, imported by **both** `App.tsx` and the routing
   tests, so a changed redirect target fails a test instead of drifting silently.
5. Untracked rows visible under `status=all` and `status=untracked` only.

### NEXT STEP — collapse the sidebar to one entry per family

Consolidation currently stops at the page. The sidebar still shows a two-child group per family
(`In Use` / `Needs Review`), which now deep-links into the *same* page with different filters. Both
children were kept deliberately, to preserve the "N need review" count badge that the permissions
merge had silently lost (`sidebar.ts` surfaces only `total` for permissions).

That is now the wrong shape, and it carries a live inconsistency:

```ts
{ key: "hooks-use", to: hooksRoutes.inUse, label: productLanguage.inUse, count: hooksCounts.inUse }
// hooksRoutes.inUse === "/hooks"  -> page defaults to status "all"  -> renders managed + untracked
// hooksCounts.inUse  === entries.filter(kind === "managed").length  -> counts managed only
```

So the badge says e.g. 10 while the view it opens shows 13 rows. The label promises "In Use" and
delivers everything. Same in all four families.

**The intended end state:** one sidebar entry per family. The **group heading itself becomes the
link** — clicking "Skills" loads `/skills` showing *all* skills, not just managed. No child rows.

Work required:

- `app/capability-registry/sidebar.ts` — make the family group a link rather than a container of two
  children; drop `*-use` / `*-review` child entries for the five consolidated families.
- Decide what count the single entry shows. `total` matches the default view; if the needs-review
  count is still worth surfacing, it needs a second badge or affordance on the same row — **do not
  simply drop it**, that regression is the reason the two-child group existed at all.
- `features/<family>/public.ts` — `*Routes.inUse` / `.needsReview` become redundant once nothing links
  to them; keep whatever the legacy redirects in `routes.tsx` still need.
- Leave MCP's genuine two-page group alone.
- Sidebar rendering is shared, so verify the group-as-link change does not disturb families that are
  legitimately still grouped.

### Also shipped 2026-08-16 — Hermes-origin skills were wrongly classified as unmanaged

Merged at `836b655` (fix `157381e`). **This reclassified 55 of 69 manifest entries.** Live inventory
went from `{"managed": 14, "unmanaged": 59}` to `{"managed": 69, "unmanaged": 4}` — verified against
real data before and after, not predicted.

**Symptom:** a skill the manifest already recorded as managed (`defuddle`) was shown as `Unmanaged`
with an Adopt button; `POST /api/skills/{ref}/manage` returned `409 package already exists in store`.
A closed loop with no exit from the UI.

**Root cause:** `_is_excluded_hermes_store_package` in `application/skills/inventory.py` excluded any
Hermes-origin package whose `source_kind == "centralized"`. Its own comment noted that self-learned
Hermes skills *are* centralized once managed — so the rule excluded exactly the skills that
`ARCHITECTURE.md:56` and `README.md:287` say must be "discoverable and adoptable". Only bundled/official
Hermes packages should be hidden, and those are handled by `excluded_hermes_names`, which is retained.
Every one of the 55 Hermes entries matched the deleted clause.

Regression test: `test_existing_hermes_origin_package_is_managed_not_adoptable` in
`tests/integration/test_skills_mutations.py` — verified to fail without the fix.

**Operational lesson worth keeping.** The bug was first reported as "Adopt does nothing", and the first
symptom found was `GET /api/skills` hanging while `/api/hooks` and `/api/agents` returned 200. That hang
was a *stale server process* running pre-`4cc1ed2` code with the skills auto-adopt deadlock — not the
reported bug. **Rebuilding `frontend/dist` updates the UI, but backend fixes require restarting the
server.** Check process start time against the relevant commit before diagnosing.

## State at end of session 2026-08-16 — resume here

`main` = `836b655`. Working tree clean, no delegate worktrees or branches outstanding.

**Validation on `836b655`:** frontend `npm test` **300/300 (62 files) exit 0**; backend `exit 0` /
81% coverage; typecheck `0`, build `0`, lint `0 errors` (12 warnings, was 17 pre-consolidation);
`frontend/dist` rebuilt to match.

A first run of the frontend suite showed 299/300 while a backend suite, a production build and two
server restarts were running alongside it. Re-run on an idle machine: 300/300. The two usual suspects
(`MarketplaceCliPage`, `SkillDetailContent`) and all 12 skills test files also passed in isolation.
This is the load flakiness described under "Gotchas" below, not a defect.

**Running instance:** served from the repo checkout on `0.0.0.0:8000` with `--allow-remote`, reachable
at `http://vibebox.goose-marlin.ts.net:8000/`. Note the API is **unauthenticated** — anyone who can
reach the port can mutate local harness config. Restart with `--host <tailscale-ip>` if tailnet-only
exposure is wanted.

### Next steps, in priority order

1. **Sidebar consolidation** — the section immediately above. One entry per family, group heading
   becomes the link, `/skills` shows all skills. Decide where the needs-review count goes; do not drop it.
2. **MCP** — the last two-page family. Backend reshape first (see the exclusion rationale above).
3. **Unverified in a browser.** The four consolidated pages have test coverage but nobody has confirmed
   spacing, empty states, or the bulk-adopt dock visually. `/hooks`, `/agents`, `/skills`,
   `/slash-commands`, plus each one's `?status=untracked` deep link.

### Settings path environment-dependence — resolved 2026-08-17

**Resolved 2026-08-17 in merge commit `b3146d3`.** Without an explicit override, settings now resolve
to `data_dir / "settings.json"`, so changing only `XDG_CONFIG_HOME` no longer changes the settings
path. No live settings files were migrated, overwritten, or deleted.

**Historical snapshot (recorded 2026-08-16; retained below):**

**Not fixed. No delegate assigned.** Found 2026-08-16 while investigating the skills bulk adoption.

**Symptom.** The user's stored settings — `disabledHarnesses: ["cursor", "opencode"]`,
`autoAdoptHarnesses.agents: ["claude","codex","agy","cursor"]`, and the `autoAdopt` flags — silently
stopped taking effect. The app now reads an entirely different settings file and falls back to
defaults, with no error and no migration.

**Two files exist, and the audit log shows the handover:**

```
~/.config/harnessam/settings.json   9 writes, 2026-08-15 06:35 → 19:09   ← the real settings
~/.harnessam/settings.json          2 writes, 2026-08-16 21:54           ← what the app reads now
```

**Mechanism** — `harness_asset_manager/paths.py`. `settings_path = config_dir / "settings.json"`
(line ~55), and `config_dir = _xdg_dir(env, "XDG_CONFIG_HOME", default_linux)` in `_base_dirs`. So the
settings location depends on whether `XDG_CONFIG_HOME` is set **in the environment that launched the
server**:

```sh
# XDG unset (e.g. a plain shell):
./.venv/bin/python -c "from harness_asset_manager.paths import resolve_app_paths as r; print(r().settings_path)"
#   -> /home/dev/.harnessam/settings.json

# XDG_CONFIG_HOME set (e.g. a desktop session):
XDG_CONFIG_HOME=/home/dev/.config ./.venv/bin/python -c "from harness_asset_manager.paths import resolve_app_paths as r; print(r().settings_path)"
#   -> /home/dev/.config/harnessam/settings.json
```

This is **not** a one-time migration that was missed — it can flip back and forth depending on how the
server is launched. Note `data_dir` does *not* drift the same way (`_resolve_linux_default_store` pins
it), so `skills-manifest.json` and the stores stayed consistent throughout; only `config_dir` diverges.

**Impact.** Low right now: `cursor` and `opencode` both report `installed: false` and their
directories are absent, so nothing can be written to them. But a user who disabled a harness and later
installs it would find it silently active again. The lost `autoAdopt` flags happen to have *reduced*
risk here rather than increased it.

**Fix directions** (pick deliberately — this is a data-location decision, not a bug-swat):

- Resolve settings from `data_dir` rather than `config_dir`, so it tracks the same pinned store as
  every manifest; or
- Read the legacy `~/.config/<app>/settings.json` as a fallback and migrate it once, the way
  `_resolve_linux_default_store` already does for the data store; or
- Make the divergence loud — fail or warn when a settings file exists at the other candidate path.

**Do not delete `~/.config/harnessam/settings.json`** — it is the only copy of the user's real
settings. Restoring `disabledHarnesses` into the active file is a separate, pending decision; the user
has been told and has not asked for it yet.

### Gotchas that cost time this session

- **`npm test` flakes under load.** `MarketplaceCliPage.test.tsx` and `SkillDetailContent.test.tsx` fail
  intermittently when several vitest runs share the machine (`environment` timings exceed 1500s and
  `waitFor` expires). Both pass in isolation. **Run one suite at a time**; do not chase them.
- **`ss` / `netstat` report nothing in this WSL environment.** Use `pgrep` and `curl` to check ports.
  A `--port` that is already taken is silently ignored and the app binds a random port instead.
- **`../` escapes the repo.** `harnessAM/checkout` is a symlink to `harness-asset-manager`, so a
  relative worktree path lands in `/home/dev/projects/`. Use absolute paths for `git worktree add`.
- **`.gitignore` trailing slashes match directories only.** `.venv/` and `node_modules/` did not match
  the symlinks agents create; fixed in `5e76369`, but the same trap applies to any new entry.


## "Method Not Allowed" when adding a tag (2026-08-23) — a stale server, not a code bug

**Symptom.** Adding the tag `test` in the Skills asset-details panel returned
`{"detail":"Method Not Allowed"}` (HTTP 405).

**It was not a code bug.** The server process on `:8000` had started at **17:04**;
the tags feature landed at **17:44** (`d45e61e`, merged `9c04780` at 17:53). The
running process predated the route by forty minutes. `frontend/dist` *was* current
(rebuilt 17:58), which is why the tag UI rendered and the button was clickable —
**a fresh frontend served by a stale backend.** Restarting the server fixed it;
the tag now persists.

### Why it presented as 405 instead of 404 — worth knowing, it will recur

`api/routers/skills.py:41` declares `@router.get("/{skill_ref:path}")`. `:path` is
**greedy**, and that route is declared **before** every sub-route (`/tags`,
`/document`, `/enable`, …). Starlette matches in declaration order: a request whose
sub-route does not exist still matches this catch-all on **path** but not on
**method** — a *partial* match — and a partial match with no later full match is
reported as **405**.

So **any** unknown sub-path under `/api/skills/...` says "Method Not Allowed",
which points you at the HTTP verb instead of at the missing route. Asset tags are
Phase 1 (Skills first); agents, hooks and MCP are next and will hit this again.

**A fix is delegated to agy** on a short-lived branch — unknown sub-paths must 404,
with a regression test that fails if the catch-all starts swallowing them again.
**Not merged; pending review.**

### The diagnostic that settles it in one step

Do not read the route table off the running app — `/openapi.json` returns **200 with
the SPA's HTML**, not JSON, because of the frontend catch-all. Compare process start
time against the commit that added the route instead:

```bash
ps -eo pid,lstart,cmd | grep "[p]ython -m harness_asset_manager serve"
git log -1 --format='%h %ad %s' --date=format:'%Y-%m-%d %H:%M' <commit-that-added-it>
```

Then prove it: run current `HEAD` on a spare port and reissue the request.

```bash
.venv/bin/python -m harness_asset_manager serve --host 127.0.0.1 --port 8099 --no-open-browser &
curl -X PUT "http://127.0.0.1:8099/api/skills/shared%3Aacademic-research/tags" \
  -H 'Content-Type: application/json' -d '{"tags":["test"]}'
```

`200` there and `405` on `:8000` means stale process, full stop.

### Live-state changes from this session

- **The `:8000` process was restarted and is now started differently.** The old one
  ran with `--socket-fd 3` and had been orphaned to PID 1, so its socket could not
  be reproduced. It now runs:

  ```bash
  cd ~/projects/harness-asset-manager && nohup .venv/bin/python -m harness_asset_manager \
    serve --host 0.0.0.0 --port 8000 --no-open-browser --allow-remote > /tmp/ham-serve.log 2>&1 &
  ```

  Same host, port and `--allow-remote` as before, so the tailnet front door
  (`:443 → 127.0.0.1:8000`) is unchanged and was verified `200` afterwards.
- **The tag store is `~/.harnessam/asset-tags.json`** (with a `.lock` beside it). It
  was **empty** before this — the feature had never completed a write, consistent
  with every attempt 405ing. It now holds `skills:shared:academic-research: ["test"]`,
  which is the tag the user was trying to add. Remove it from the UI if unwanted.

**Confirming the `ss`/`netstat` gotcha above:** `ss -ltn | grep :8000` reported the
port free while the old process was still shutting down. Only `curl` was reliable.
