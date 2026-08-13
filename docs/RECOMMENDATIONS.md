# Recommendations

> Review of 2026-07-25, refreshed on 2026-08-10. Verified suites on
> earlier same-tree commits: backend unit (496) + integration (169) pass, `npm run typecheck` is
> clean, `npm run build` succeeds, `ruff check harness_asset_manager tests scripts` is clean,
> `pyright` completes with its current basic-mode warning baseline, and `npm run lint:frontend`
> completes with warnings. Locally, `npm test` can still exit non-zero on three async detail tests
> (`SkillDetailContent`, `MarketplaceCliPage`, `AgentsInUsePage`) under this container's `waitFor`
> budget — this was later resolved; the current local frontend suite is green.
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
> 2026-08-10 (Codex lossless agent adoption/drift repair + configurable auto-adopt defaults);
> 2026-08-12 (`~/.harnessam` store rename, safe legacy migration, and housekeeping);
> 2026-08-12 (extension-family and harness contribution checklists).
> 2026-08-12 (machine-readable API error envelopes and frontend `ApiError` handling).
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

## Tier 2 — Strategic investments

### 2.2 Coverage measurement with a ratchet — S–M

496 backend unit tests, 169 integration tests, and 62 frontend test files (278 tests) exist, but
nothing measures what they cover, so gaps are invisible — the unknown-field data loss fixed by
PR #30 lived in well-tested-looking code for months.

**Action:** add `coverage.py` to `scripts/test_backend.sh` and `vitest --coverage` to CI; report
per-package coverage and ratchet the threshold (fail if it drops). The point is trend, not a
vanity number.

---

## Suggested sequencing

## Suggested sequencing

1. **Next:** §2.2, coverage measurement with a ratchet. It is the best follow-on for keeping
   the newly expanded auto-adoption behavior honest across the priority harnesses.
2. **Closed recently:** `--state-dir` full isolation (2026-08-12), Codex lossless adoption and configurable auto-adopt defaults (2026-08-10),
   §1.1 (PR #30, 2026-08-06), §2.1 activity view (2026-08-07), §1.2
   static-analysis (2026-08-08), family-wide auto-adoption (2026-08-08), slash-command drift
   auto-repair / `plan-auto-adoption.md` Stage 4 (2026-08-09).
3. **Auto-adoption plan remainder:** Stages 1–4 shipped; skills new-directory adoption shipped
   opt-in (plan §7 / former Stage 5). The Codex gate and default-harness follow-up are now shipped.
4. **When planning the next family or harness:** use the new family/harness checklists first;
   then use the shipped activity journal for
   traceability, and add 2.2 to keep coverage honest.
5. **Housekeeping closed:** documentation is under `docs/`, Windows import boundaries and socket
   binding are hardened, frontend tests are green locally, and `scripts/clean-local-caches.sh`
   handles reproducible local scratch.
