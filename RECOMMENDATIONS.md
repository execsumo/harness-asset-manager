# Recommendations

> Review of 2026-07-25, refreshed against `main` on 2026-08-08. Verified by running the suites:
> backend unit (496) + integration (169) pass, `npm run typecheck` is clean, `npm run build`
> succeeds, `ruff check harness_asset_manager tests scripts` is clean, `pyright` completes with
> its current basic-mode warning baseline, and `npm run lint:frontend` completes with warnings.
> `npm test` is **275/278 — not green**: three async detail tests (`SkillDetailContent`, `MarketplaceCliPage`,
> `AgentsInUsePage`) time out under this container's `waitFor` budget and reproduce in isolation.
> They are pre-existing and unrelated to the entries below, but the suite does exit non-zero and
> the cause is not yet established — see the Tier-3 entry on the three timing-out frontend tests.
> Ordered by value: each tier outranks the next. Within a tier, items are ordered by
> value-for-effort. Effort scale: **S** < 1 hour, **M** hours–a day, **L** multi-day.
>
> **This list is kept to open items only — shipped work is removed.** Shipped batches:
> 2026-07-24 merge `98c3417` (audit gates, loopback guards, static-root containment, dead-code pass);
> 2026-07-25 Tier-1 batch (Dependabot + SHA-pinned actions; golden writer round-trip tests; ruff lint
> gate; Hermes slash provisional label);
> 2026-08-06 PR #30 `bd72d0a` (§1.1 — writers now preserve unknown user fields);
> 2026-08-07 `63cfbe4` (§2.1 — mutation activity view);
> 2026-08-08 (static-analysis adoption — full-scope Ruff, Pyright, and ESLint) — see `handoff.md`.
> Partially-shipped items below keep their number and describe only the remaining scope.

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

### 1.3 Finish labeling (or verify) the Hermes harness — M

**Shipped (2026-07-25):** the Hermes **slash** binding now carries a provisional `support_note`
("…unverified against a real Hermes install; writes may not take effect…") in
`harness/catalog.py`, surfaced to the UI via the existing `SlashTarget.supportNote` path. The agents
binding was already labeled unavailable (no agent-definition format).

**Remaining:** MCP and hooks are still written on unverified assumptions with no provisional label.
Thread a `support_note` through `ConfigSubtreeBindingProfile` → the MCP/hooks read models (typed,
so it needs an OpenAPI regen) and mark both provisional, **or** validate against a real Hermes
build and record the evidence in `handoff.md` (as was done for Claude/agy agent symlinks). With
seven more harnesses on the README roadmap, define a repeatable "new harness verification" checklist
(probe CLI, real read, real write, round-trip diff) and reuse it per harness.

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
one pairs with §1.3's verification checklist). Only after that, evaluate extracting a shared
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
- **Three frontend tests time out locally, so `npm test` exits non-zero.** `SkillDetailContent`,
  `MarketplaceCliPage`, and `AgentsInUsePage` each `await findBy…` on an async detail render and
  blow the default `waitFor` budget in a dev container (full run ~13 min, mostly environment
  setup); they reproduce when run in isolation. **Not yet diagnosed** — CI was last green on
  `main` at `2faa775`, which predates the activity-view commit, so no CI evidence exists for the
  current tree. First step is to run these three in CI and see whether they fail there too; only
  then decide between raising the `waitFor` budget and making the detail render deterministic.
  A suite that cannot be trusted to go green locally stops being a gate. — **S**
- **Clean local scratch from the repo dir.** The orphaned `harness_asset_manager/db/` package is
  **gone** (fixed); no `.pytest_cache` remains. What lingers is untracked `__pycache__/*.pyc`
  throughout the tree. Harmless but confusing — the project standardizes on `unittest`, so either
  document pytest compatibility or add the cache dirs to a cleanup target. — **S**

---

## Suggested sequencing

1. **§1.1 closed 2026-08-06** (PR #30), **§2.1 closed 2026-08-07** (activity view), and
   **§1.2 closed 2026-08-08** (static-analysis adoption). **§1.3** (label or verify Hermes MCP &
   hooks) is now the next Tier-1 item.
2. **When planning the next family or harness:** 2.3 first; use the shipped journal for traceability,
   and add 2.2 to keep coverage honest.
3. **Tier 3 housekeeping** rides along whenever its files are touched next — except the flaky
   frontend trio, which is worth doing on its own the next time `npm test` blocks someone.
