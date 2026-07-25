# Recommendations

> Review of 2026-07-24, commit `0d071a6` (`main`). Verified by reading the code and running the
> suites: backend 347 unit + 146 integration tests pass, `npm run typecheck` clean.
> Ordered by value: each tier outranks the next. Within a tier, items are ordered by
> value-for-effort. Effort scale: **S** < 1 hour, **M** hours–a day, **L** multi-day.
>
> **This list is kept to open items only — shipped recommendations are removed.** The first
> batch (dependency audit gates, loopback request guards, static-root containment, dead-code
> pass) landed 2026-07-24 in merge `98c3417`; see `handoff.md` for the record.

## Already strong — don't churn these

- Atomic writes + `flock` for file mutations (`skill_manager/atomic_files.py`), with a dedicated
  store-concurrency test.
- OpenAPI contract discipline: generated TS client committed, `codegen:check` drift gate in CI.
- One canonical harness catalog (`skill_manager/harness/catalog.py`) that drives every family.
- Subprocess calls are all list-form (no `shell=True`); marketplace fetchers use a pinned CA
  context with TLS fixtures under test.
- CI matrix across Python 3.11–3.14 plus a full packaging smoke on four OS/arch targets.

---

## Tier 1 — High value, moderate effort

### 1.1 Codify the round-trip test that your own retrospective calls for — M

`plan-agents-simplify.md` ends with a hard-won lesson: two data-loss bugs shipped with the same
shape — *"a component rewrote a whole artifact from the subset of fields it understood"* — and
names the test that catches it: **"read a realistic file, write it, diff the parts you never
touched."** Agents got that fix; the other writers haven't been audited for the same class.

**Action:** for every component that writes a user-authored file — MCP config mappers
(`application/mcp/mappers.py`), hooks settings writers (`application/hooks/harness_application.py`),
slash-command frontmatter codecs, permissions writers — add golden round-trip tests using
*realistic* fixtures (messy key order, unknown keys, empty strings, comments). Diff the untouched
regions byte-for-byte. This is the cheapest insurance against the worst bug class this product
can have: silently destroying user config. Consider `hypothesis` for frontmatter/JSON round-trip
properties once the golden tests exist.

### 1.2 Add static-analysis gates the codebase already half-adopted — M

Fifteen backend files carry `# noqa: BLE001` comments — ruff/flake8-blind-except rule codes —
yet **there is no ruff config, no mypy/pyright config, no ESLint/Prettier config, and no lint
step in CI**. Someone linted once; nothing keeps it true. The Python code is consistently typed,
so a type checker should be nearly free to adopt.

**Action:** add `ruff` (lint + format) and `pyright` (or `mypy`) with a committed config and a CI
step; add ESLint (typescript + react-hooks rules) for `frontend/src`. Baseline existing
violations rather than fixing them in the adoption PR.


### 1.3 Verify or visibly label the Hermes harness — M

Per `handoff.md`, Hermes MCP (`~/.hermes/mcp.json`) and slash (`~/.hermes/commands`) conventions
are **unverified assumptions**, hooks are unimplemented, and the adapters "have never run against
a real Hermes install." The app writes to real user config based on those assumptions.

**Action:** either validate against a real Hermes build (and record the evidence in
`handoff.md`, as was done for Claude/agy agent symlinks), or mark the binding provisional —
`unavailable_reason`-style — so users aren't trusting unverified writes. With seven more
harnesses on the README roadmap, define a repeatable "new harness verification" checklist
(probe CLI, real read, real write, round-trip diff) and reuse it per harness.

### 1.4 Dependency-update and supply-chain automation — S–M

No Dependabot/Renovate config, and GitHub Actions are pinned by major tag (`actions/checkout@v6`)
rather than commit SHA. The audit gate shipped in `98c3417` catches advisories in CI; this
closes the loop: advisories are found automatically, updates arrive as PRs, and the CI matrix
(which is genuinely good) validates them.

**Action:** add `.github/dependabot.yml` (npm + pip + github-actions ecosystems, weekly), and
SHA-pin the actions in both workflows.

---

## Tier 2 — Strategic investments

### 2.1 A mutation audit journal — M–L

A tool whose job is mutating local config has almost no observability: exactly one module uses
`logging` (`db/migrations.py`), and uvicorn runs with `access_log=False`. When something goes
wrong in a user's setup — or a user asks "what did Skill Manager change?" — there is no answer
on disk.

**Action:** append a structured record (JSON Lines) to
`${XDG_DATA_HOME}/skill-manager/audit.log` for every mutation: timestamp, family, operation,
target paths, outcome. This doubles as product surface later (an activity view) and strengthens
the trust story that "Needs Review" already builds.

### 2.2 Coverage measurement with a ratchet — S–M

493 backend tests and 62 frontend test files exist, but nothing measures what they cover, so
gaps are invisible (e.g. the two data-loss bugs in §1.1 lived in well-tested-looking code).

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

- **Root doc sprawl.** `handoff.md` (21 KB), two `plan-agents-*.md`, and this file sit beside a
  22 KB README. Move plans/handoffs under `docs/` (keeping the handoff discipline that clearly
  works) and leave a pointer at the root. — **S**
- **Windows is architecturally excluded, not just unsupported.** `atomic_files.py` imports
  `fcntl` at module top level, so the package doesn't even *import* on Windows. Fine while the
  README badges say macOS/Linux — just gate the import so "Windows support" later is a port of
  one module, not an archaeology dig. — **S**
- **`choose_port` / `bind_socket` TOCTOU race** (`runtime/server.py:32-49`): probe-bind, close,
  re-bind. Two quick starts can collide between the probes. Bind once and keep the socket (the
  code already passes `fd` to uvicorn, so this is mostly deleting the probe). — **S**
- **Clean local scratch from the repo dir.** Stale `test_scan_*.pyc` and `.pytest_cache` linger
  in the working tree (untracked, but confusing); the project standardizes on `unittest`, so
  either document pytest compatibility or remove the cache dirs. — **S**

---

## Suggested sequencing

1. **Next (all S/M):** 1.4 (Dependabot + SHA pinning) as one PR, then 1.1 (round-trip tests),
   1.2 (lint/type gates), and 1.3 (Hermes verification).
2. **When planning the next family or harness:** 2.3 first, 2.1 alongside, 2.2 to keep it honest.
3. **Tier 3 housekeeping** rides along whenever its files are touched next.

