# Recommendations

> Review of 2026-07-25, refreshed against `main` on 2026-08-09 (harness support tiers; OpenClaw
> retired; §1.4 `--state-dir` fix). Verified by running the suites: backend unit (508) +
> integration (175) pass, `npm run typecheck` is clean, `npm run codegen:check` reports no drift,
> `npm run build` succeeds, `ruff check harness_asset_manager tests scripts` is clean, `pyright`
> reports 0 errors against its 165-warning basic-mode baseline (unchanged), and
> `npm run lint:frontend` completes with 23 warnings, 0 errors. `npm test` was **278/278 green** in
> this container in ~43s — the three async detail tests recorded below as timing out did **not**
> reproduce here. That does not close the Tier-3 entry (no CI evidence either way yet), but it
> does mean the suite is not currently blocking.
> Ordered by value: each tier outranks the next. Within a tier, items are ordered by
> value-for-effort. Effort scale: **S** < 1 hour, **M** hours–a day, **L** multi-day.
>
> **This list is kept to open items only — shipped work is removed.** Shipped batches:
> 2026-07-24 merge `98c3417` (audit gates, loopback guards, static-root containment, dead-code pass);
> 2026-07-25 Tier-1 batch (Dependabot + SHA-pinned actions; golden writer round-trip tests; ruff lint
> gate; Hermes slash provisional label);
> 2026-08-06 PR #30 `bd72d0a` (§1.1 — writers now preserve unknown user fields);
> 2026-08-07 `63cfbe4` (§2.1 — mutation activity view);
> 2026-08-08 (static-analysis adoption — full-scope Ruff, Pyright, and ESLint) — see `handoff.md`;
> 2026-08-09 (§1.4 — `--state-dir` now isolates config, data, and state together, matching what
> the README already claimed; see `handoff.md`).
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

### 1.3 Label Hermes MCP & hooks provisional — do NOT verify — S

**Rescoped 2026-08-09** when the four core harnesses (Claude Code, Codex, Antigravity,
Cursor) were declared and the rest dropped to best effort. This was the top Tier-1 item at
M effort; under the tier split its expensive branch is no longer worth doing.

**Shipped (2026-07-25):** the Hermes **slash** binding carries a provisional `support_note`
surfaced through `SlashTarget.supportNote`. The agents binding was already labeled
unavailable.

**Remaining, reduced:** thread a `support_note` through `ConfigSubtreeBindingProfile` → the
MCP/hooks read models (typed, so it needs an OpenAPI regen) and mark both provisional.
**Do not validate against a real Hermes build** — Hermes is `best_effort`, and per
`SupportTier` a best-effort harness may ship on documented assumptions carrying a note.
The "repeatable new-harness verification checklist" this item used to carry moved to §2.3,
where it now needs two checklists — one per tier.

### 1.5 Antigravity has no slash-command binding — M

Antigravity is a **core** harness with a declared gap: `catalog.py` binds five of six
families for `agy`, omitting `slash_commands`, so the shared prompt library does not reach
it. Pinned in `tests/unit/test_harness_support_tiers.py::KNOWN_CORE_GAPS`, which is what
now makes the gap loud rather than invisible.

Antigravity is also the least-tested core harness — at the time of the tier split it was
referenced by 11 test files against Claude's 26, Codex's 21 and Cursor's 19, and by fewer
than OpenCode (13) or Hermes (12). Closing this gap is the natural way to pull coverage
back where it belongs.

**Action:** verify whether Antigravity exposes a slash-command surface at all (probe the
CLI, real read, real write, round-trip diff — the §2.3 core checklist), record the evidence
in `handoff.md`, then either implement `CommandFileBindingProfile` for `agy` or record it
as verifiably impossible and remove the entry from `KNOWN_CORE_GAPS`.

### 1.6 Cursor has no permissions binding — M

Denylists reach Claude, Codex, and Antigravity but not Cursor, which is a core harness.
Same treatment as §1.5: verify Cursor's current permission surface first, then implement or
prove impossible. Also pinned in `KNOWN_CORE_GAPS`.

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

**Action:** write `docs/adding-a-family.md` + `docs/adding-a-harness.md` checklists. The harness
one needs **two** bars, matching `SupportTier`: a core harness must be verified against a live
CLI (probe, real read, real write, round-trip diff, evidence in `handoff.md`), while a
best-effort harness may ship on documented assumptions carrying a `support_note`. §1.5 and §1.6
are the first two users of the core checklist. Only after that, evaluate extracting a shared
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

1. **Closed:** §1.1 2026-08-06 (PR #30), §2.1 2026-08-07 (activity view), §1.2 2026-08-08
   (static-analysis adoption), §1.4 2026-08-09 (`--state-dir` isolation).
2. **§1.3 next**, an S: label Hermes MCP & hooks provisional and stop. Do not verify.
3. **Then §1.5, then §1.6** — the two declared gaps in core harnesses. §1.5 first: it is both a
   functional gap and the weakest-tested core harness, so the work pulls coverage where it belongs.
   Both start with verification against a live CLI, not implementation.
4. **When planning the next family or harness:** 2.3 first (it now needs a per-tier harness
   checklist); use the shipped journal for traceability, and add 2.2 to keep coverage honest —
   2.2 is also what would have caught Antigravity's thin coverage before a grep did.
5. **Tier 3 housekeeping** rides along whenever its files are touched next.
