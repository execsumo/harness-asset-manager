# Handoff

Running status for in-flight work. Read this before resuming. Newest session on top.

## 2026-08-09 (latest) — Cross-device sync planned; nothing implemented yet

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
- **Codex** (both agents and slash): excluded regardless of family — the TOML/rendered round-trip
  is lossy (plan invariant 3).

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
`~/.harness-asset-manager/skills/<name>`, matching what `FileTreeSkillsAdapter`
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

- **Storage Location**: Canonical baselines and timestamped snapshots stored under `~/.harness-asset-manager/configs/<harness_id>/`.
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
- **Skills**: categorized `~/.hermes/skills/<category>/<skill>/`, shared under `harness-asset-manager`.
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

### ⚠️ Incomplete — resume here

> **PARTLY SUPERSEDED (2026-08-08) — do not resume from this list as written.** Item 2's MCP
> half was resolved on 2026-07-13 by the migration to upstream's product-accurate Hermes impl
> (`~/.hermes/config.yaml`, YAML `mcp_servers`); only the *slash* convention is still
> unverified. The "Housekeeping" note below ("Nothing is committed… working tree on `main`")
> described that session only — it landed long ago. Items 1, 3, and 4 are still open and are
> tracked in `RECOMMENDATIONS.md §1.3` and the README support matrix. Current status is at the
> top of this file.

1. **Hermes hooks — NOT implemented (the main open item).** Hermes has no `hooks` binding, so it
   is correctly absent from the Hooks views. Deferred because hook config formats are
   harness-specific (each harness has its own event taxonomy + file shape) and Hermes' real
   schema is unknown. Reusing another harness's hook codec would write structurally-wrong config.
   **To finish:** obtain Hermes' actual hooks schema (event names, config file path, JSON/TOML
   shape), then add a `HookMapper` in `harness_asset_manager/application/hooks/mappers.py` + register it,
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
