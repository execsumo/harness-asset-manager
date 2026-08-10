# Recommendations

> Review of 2026-07-25, refreshed on 2026-08-10. Verified suites on
> earlier same-tree commits: backend unit (496) + integration (169) pass, `npm run typecheck` is
> clean, `npm run build` succeeds, `ruff check harness_asset_manager tests scripts` is clean,
> `pyright` completes with its current basic-mode warning baseline, and `npm run lint:frontend`
> completes with warnings. Locally, `npm test` can still exit non-zero on three async detail tests
> (`SkillDetailContent`, `MarketplaceCliPage`, `AgentsInUsePage`) under this container's `waitFor`
> budget — **CI `frontend-validate` is green** on `c60d45a` (run `31291859168`), so the timeouts
> are confirmed container-local, not a regression on `main`. See the Tier-3 entry.
> Ordered by value: each tier outranks the next. Within a tier, items are ordered by
> value-for-effort. Effort scale: **S** < 1 hour, **M** hours–a day, **L** multi-day.
>
> **Current priority scope:** Claude Code, Codex, Antigravity (agy), and Cursor. Hermes,
> OpenCode, and OpenClaw are intentionally out of the active roadmap; references to them below
> are retained only where they describe shared behavior or shipped compatibility.
>
> **This list is kept to open items only — shipped work is removed.** Shipped batches:
> 2026-07-24 merge `98c3417` (audit gates, loopback guards, static-root containment, dead-code pass);
> 2026-07-25 Tier-1 batch (Dependabot + SHA-pinned actions; golden writer round-trip tests; ruff lint
> gate);
> 2026-08-06 PR #30 `bd72d0a` (§1.1 — writers now preserve unknown user fields);
> 2026-08-07 `63cfbe4` (§2.1 — mutation activity view);
> 2026-08-08 `c60d45a` (§1.2 — static-analysis adoption: full-scope Ruff, Pyright, ESLint);
> 2026-08-08 `f9003b1` (family-wide opt-in auto-adoption + `harnessam refresh`);
> 2026-08-09 `2195a84` (`plan-auto-adoption.md` Stage 4 — slash-command drift auto-repair);
> 2026-08-10 (Codex lossless agent adoption/drift repair + configurable auto-adopt defaults).
> Partially-shipped items below keep their number and describe only the remaining scope.
> See `handoff.md` for the full chronological record.

## Already strong — don't churn these

- Atomic writes + `flock` for file mutations (`harness_asset_manager/atomic_files.py`), with a dedicated
  store-concurrency test.
- OpenAPI contract discipline: generated TS client committed, `codegen:check` drift gate in CI.
- One canonical harness catalog (`harness_asset_manager/harness/catalog.py`) that drives every family.
- Subprocess calls are all list-form (no `shell=True`); marketplace fetchers use a pinned CA
  context with TLS fixtures under test.
- CI matrix across Python 3.11–3.14 plus a full packaging smoke on four OS/arch targets.
- Ruff lint gate in CI (`[tool.ruff]` in `pyproject.toml`): import sorting + pyflakes enforced
  and baselined green; `requirements-dev.txt` pins the tool.

---

## Tier 1 — High value, moderate effort

### 1.4 `--state-dir` does not isolate the store, but the README says it does — S

Found 2026-08-09 during cross-device sync planning (`plan-cross-device-sync.md` §13).

The README's Scripting section says `--state-dir` "isolates a run, which is how you keep CI or
a throwaway sandbox from touching the real store." It does not. `paths.py:77-98` uses
`STATE_DIR_ENV` only for `state_dir` (`runtime.json`, `server.log`); `config_dir` and `data_dir`
still resolve from XDG or the macOS default. **A user following that advice writes to their real
store** — the exact outcome the sentence promises to prevent. Effort is Tier-3-sized; the
consequence is not, which is why it sits here.

**Action:** either correct the sentence (isolation needs `XDG_DATA_HOME` + `XDG_CONFIG_HOME`,
plus `HOME` for harness roots — what `tests/support/fake_home.py` already does), or make
`--state-dir` mean what it says by having it override all three base dirs. Prefer the latter if
cross-device sync proceeds, since its two-machine test strategy leans on real isolation.

---

## Tier 2 — Strategic investments

### 2.2 Coverage measurement with a ratchet — S–M

496 backend unit tests, 169 integration tests, and 62 frontend test files (278 tests) exist, but
nothing measures what they cover, so gaps are invisible — the unknown-field data loss fixed by
PR #30 lived in well-tested-looking code for months.

**Action:** add `coverage.py` to `scripts/test_backend.sh` and `vitest --coverage` to CI; report
per-package coverage and ratchet the threshold (fail if it drops). The point is trend, not a
vanity number.

### 2.3 Document the family/harness template; then decide on extraction — M

Each family (skills, MCP, hooks, permissions, agents, slash commands) re-implements the same
octet: store / mappers / adapters / inventory / mutations / queries / read_models / harness
application — e.g. `hooks/mappers.py` is 897 lines, `permissions/mappers.py` 683. The mirroring
is deliberate and has real benefits (families evolve independently), but the *knowledge* of what
a conforming family needs exists only in the plans and handoffs.

**Action:** write `docs/adding-a-family.md` + `docs/adding-a-harness.md` checklists (the harness
one pairs with a repeatable new-harness verification checklist). Only after that, evaluate extracting a shared
"family framework" for the truly invariant parts (manifest store, matrix read model) — with the
checklist as the spec it must satisfy. Do not extract first: the agents rebuild shows the cost of
a bespoke abstraction that had to be torn out.

### 2.4 Machine-readable API error codes — S–M

Every error is `{"error": "<human string>"}` (`api/errors.py`), so the frontend can only branch
on message text — brittle under rewording and under i18n (several features already have `i18n.ts`
modules).

**Action:** add a stable `code` field (`"skill_not_found"`, `"harness_unavailable"`, …) alongside
`error`; adopt incrementally in the frontend where behavior branches on errors today.

---

## Tier 3 — Housekeeping (low priority, cheap when touched next)

- **Root doc sprawl.** `handoff.md` (69 KB and growing), `plan-auto-adoption.md`, two
  `plan-agents-*.md`, and this file sit beside a 36 KB README. Move plans/handoffs under `docs/`
  (keeping the handoff discipline that clearly works) and leave a pointer at the root. — **S**
- **Windows is architecturally excluded, not just unsupported.** `atomic_files.py` imports
  `fcntl` at module top level, so the package doesn't even *import* on Windows. Fine while the
  README badges say macOS/Linux — just gate the import so "Windows support" later is a port of
  one module, not an archaeology dig. — **S**
- **`choose_port` / `bind_socket` TOCTOU race** (`runtime/server.py:32-49`): probe-bind, close,
  re-bind. Two quick starts can collide between the probes. Bind once and keep the socket (the
  code already passes `fd` to uvicorn, so this is mostly deleting the probe). — **S**
- **Three frontend tests time out in this container; CI is green.** `SkillDetailContent`,
  `MarketplaceCliPage`, and `AgentsInUsePage` each `await findBy…` on an async detail render and
  blow the default `waitFor` budget here (full local run ~13 min, mostly environment setup);
  they reproduce in isolation. **CI evidence:** `ci.yml`'s `frontend-validate` job runs
  `npm test` and passed on `c60d45a` (run `31291859168`) — post activity-view and static-analysis,
  pre Stage-4 only by docs/behavior-unrelated commits. Confirmed **container-local**, not a
  `main` regression. Remaining work is optional local ergonomics: raise the `waitFor` budget,
  make the detail render deterministic, or document the container quirk so a red local suite is
  not mistaken for a broken tree. — **S**
- **Clean local scratch from the repo dir.** The orphaned `harness_asset_manager/db/` package is
  **gone** (fixed); no `.pytest_cache` remains. What lingers is untracked `__pycache__/*.pyc`
  throughout the tree. Harmless but confusing — the project standardizes on `unittest`, so either
  document pytest compatibility or add the cache dirs to a cleanup target. — **S**

---

## Suggested sequencing

1. **Next:** §2.2, coverage measurement with a ratchet. It is the best follow-on for keeping
   the newly expanded auto-adoption behavior honest across the priority harnesses.
2. **Closed recently:** Codex lossless adoption and configurable auto-adopt defaults (2026-08-10),
   §1.1 (PR #30, 2026-08-06), §2.1 activity view (2026-08-07), §1.2
   static-analysis (2026-08-08), family-wide auto-adoption (2026-08-08), slash-command drift
   auto-repair / `plan-auto-adoption.md` Stage 4 (2026-08-09).
3. **Auto-adoption plan remainder:** Stages 1–4 shipped; skills new-directory adoption shipped
   opt-in (plan §7 / former Stage 5). The Codex gate and default-harness follow-up are now shipped.
4. **When planning the next family or harness:** 2.3 first; use the shipped activity journal for
   traceability, and add 2.2 to keep coverage honest.
5. **Tier 3 housekeeping** rides along whenever its files are touched next. The container-local
   frontend trio is optional local ergonomics now that CI is known green — only prioritize it if
   a red local `npm test` is blocking someone.
