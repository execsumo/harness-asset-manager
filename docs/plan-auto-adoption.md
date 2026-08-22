# Plan — Automatic re-adoption of drifted bindings

**Status: Agents shipped 2026-07-27; family auto-adoption shipped 2026-08-08; slash-command
drift auto-repair (Stage 4) shipped 2026-08-09; Codex lossless agent adoption and configurable
auto-adopt defaults shipped 2026-08-10.** Skills, slash commands, MCP, Hooks, and Permissions
now have opt-in, family-specific adoption paths, and slash commands and Codex agents additionally
auto-repair already-managed drifted files. Amendments
made while building are marked
**AMENDED** inline:
§3's rebaseline rule, §5's exclusion from it, and §4's conflict-file location. Read
those before extending this — the literal wording of §3 loses data and there is a test
proving it.

Written 2026-07-27 from a code read.
**Goal:** stop requiring a manual re-adopt every time a harness edits an asset out
from under HAM. Edits should flow back into the store and out to the other
harnesses without the user driving it, in whichever direction they happen.

Read `handoff.md` (2026-07-27 entry) for the defects found alongside this.

---

## 1. Two different problems, do not merge them

The user's ask is one sentence but the mechanics split cleanly in two. Building one
mechanism for both is the main way this goes wrong.

| | **Skills** | **Agents** |
|---|---|---|
| Binding shape | symlink to a **directory** | symlink to a **file** |
| Can a harness destroy the binding? | **No.** `rename()` of a directory onto a directory-symlink fails `ENOTDIR` at the kernel. Writes inside resolve through the link into the store. | **Yes.** Write-to-temp + `rename()` onto the path replaces the symlink with a regular file. This is how the harness's own editor writes. |
| What actually drifts | New skill folders created *directly* in a harness's skills root never enter the store | An existing binding silently stops being a binding, and the two copies diverge |
| What automation means | auto-**adopt new** local dirs | auto-**detect and repair** broken bindings |
| Existing machinery | `FileTreeSkillsAdapter.adopt_local_copy()` (`shutil.rmtree` + `symlink_to`), driven by `SkillMutationService._manage_entry()` | `AgentMutationService.adopt(ref, on_conflict)` / `adopt_all()` |

Both are real, both are worth automating, but they need different safety rules —
skills adoption is destructive (`rmtree`), agent repair is not.

Evidence on the current machine: `~/.claude/skills` holds four unmanaged local
dirs (`distill-function`, `dossier-delegate`, `herdr-orchestration`, `seen`)
alongside three healthy symlinks. `~/.skill-manager/agents` holds one agent
(`red-team.md`) with zero bindings anywhere, so nothing is currently drifted —
this is being built before it bites, not after.

---

## 2. Why reconcile-on-read, not a filesystem watcher

**Decision: reconcile on read. Do not add a watcher.** Settled — do not re-litigate.

- There is no background infrastructure to hang a watcher on. The only thread in
  the codebase is `application/mcp/availability.py:119`, and it is a stdout reader.
  No `watchdog` dependency, no scheduler, no lifespan tasks.
- `AgentInventoryService.build()` and the skills `scan_all_adapters()` already run
  on every list request. That is the natural reconcile point and it already exists.
- A watcher is a new dependency, a new failure surface (missed events, editor
  atomic-write storms, cross-platform behaviour), and it would still need exactly
  the reconcile logic below underneath it. It buys latency, which nobody asked for.

Reconcile runs at the top of inventory build, and must be idempotent and cheap — see
§6 for the cost rule.

**AMENDED (shipped):** it takes a **dedicated reconcile lock**, not the ledger's.
`file_lock` is `fcntl.flock(LOCK_EX)` on a freshly opened fd, so taking it twice in one
process on the same path deadlocks — and every ledger mutation takes the ledger lock
internally. Reconcile must never hold the ledger lock while calling ledger methods.
The same applies to the audit log's lock.

---

## 3. The binding ledger — the actual deliverable

Everything else depends on this. Today `adopt()` raises `AgentAdoptConflict`
whenever the store already holds the slug:

```python
store_path = self.store.path_for(slug)
if store_path.exists():
    if on_conflict is None:
        raise AgentAdoptConflict(slug, store_path, harness_path)
```

and the docstring is explicit about why: *"the server never guesses, because
either choice discards someone's content."* That is correct **today**, because a
clobbered binding and a genuine name collision are indistinguishable — both
present as "store has this slug, and there is an unmanaged real file at the
binding path."

They are only indistinguishable because HAM keeps **no record of prior bindings**.
Deriving state purely from the filesystem is what makes `is_enabled()` immune to
staleness (a genuine strength — keep it), but it also means the moment a binding
is destroyed, all knowledge that it ever existed is destroyed with it.

A ledger makes the distinction decidable and turns one specific case from a guess
into a proof.

### Location and format

`<data_dir>/bindings.json`, written with the existing `atomic_write_text` +
`file_lock` (`atomic_files.py`). **Note the pending data-dir rename** — see the
2026-07-26 handoff entry about retiring `~/.skill-manager`; put this behind
whatever resolves the data dir rather than hardcoding.

```jsonc
{
  "version": 1,
  "agents": {
    "<slug>": {
      "<harness_id>": {
        "target":       "/abs/path/to/store/agents/<slug>.md",
        "linked_at":    1783997184.96,
        "store_sha256": "…",   // store content at the moment we linked
        "rendered_sha256": "…" // renders harnesses only: what we wrote out
      }
    }
  }
}
```

The ledger is a **cache, never a source of truth.** If it disagrees with the
filesystem, the filesystem wins and the ledger entry is dropped. A deleted or
corrupt ledger must degrade to exactly today's behaviour (everything unrecognised
becomes a normal conflict prompt), never to data loss. State a test for this.

### Written on

- `AgentHarnessAdapter.enable()` succeeding → upsert record
- `disable()` succeeding → delete record
- store content changing for a slug → refresh `store_sha256` for all its harnesses

### AMENDED (shipped) — where the writes actually live, and the rebaseline rule

Two corrections from implementation. Both are load-bearing; do not "restore" the
original wording.

1. **The writes live in `AgentMutationService`, not in the adapter.** The adapters are
   shared with the read-only inventory; the mutation service is the only write funnel,
   so one place records and one place forgets. `AgentStore` gained an `on_store_write`
   callback because the routers call `store.create` / `store.update` *directly*,
   bypassing the service — that callback is the single owner of the store baseline.

2. **Refresh only bindings that are still live symlinks.** The bullet above, taken
   literally, loses data. Timeline: we link (baseline A) → a harness clobbers the link
   and edits its copy → the user edits the agent in the HAM UI (store becomes B). If
   the write refreshed *all* harnesses, the ledger would now say B, `hash(store) == B`
   would match, and row 3 would fire — auto-adopting the harness copy and discarding
   the UI edit. Restricting the refresh to live bindings makes that case fall to row 4
   (two-sided) and prompt, which is correct: the two edits really are independent.
   Proven by `test_store_edit_does_not_rebaseline_a_clobbered_binding`.

   The rule reads: a live binding is a symlink, so the harness is *already* reading
   what we just wrote; re-baselining keeps a later clobber classifiable as one-sided.
   A broken binding is measured against the content it actually derived from.

---

## 4. The decision table

For an unmanaged file at `binding_path(slug)` for harness `H`
(`is_file() and not is_symlink()`):

| Ledger record for (slug, H)? | `hash(harness_file)` vs `hash(store_file)` | `hash(store_file)` vs `ledger.store_sha256` | Classification | Automatic action |
|---|---|---|---|---|
| no | — | — | **collision** (today's behaviour) | none — prompt, as now |
| yes | equal | — | **clobber, no divergence** | **relink.** Delete the harness copy, recreate the symlink. No content decision exists. |
| yes | differ | **equal** (store untouched since link) | **clobber, one-sided edit** | **adopt.** Harness copy is provably the only edit → `replace_store`, then relink every harness bound to this slug. |
| yes | differ | differ (both sides changed) | **two-sided conflict** | **none.** Surface as an issue. Never auto-resolve. |

Row 3 is the whole point: `store_sha256` from the ledger proves the store side did
not change, so `replace_store` is no longer a coin flip that discards someone's
content — it is the only edit that exists. That is what unblocks automation
without violating the principle the docstring is defending.

### Multi-harness divergence — stated rule, not left to the implementer

`delegate` may be bound into Claude, AGY, and Cursor simultaneously. Resolve
**per slug, not per binding**: gather every drifted binding for a slug first, then
decide once.

- Exactly one harness diverged → adopt it, relink the rest. (Row 3.)
- Several diverged, **identical** content hashes → same edit seen from several
  places. Adopt once, relink the rest.
- Several diverged, **differing** content → **do not auto-resolve.** Keep the store
  as-is, preserve each divergent copy as `<store>/<slug>.<harness>.conflict.md`,
  and surface one issue naming every side. The user picks.

**AMENDED (shipped):** the preserved copies go in `<agents_root>/conflicts/<slug>.<harness>.md`,
a **subdirectory**, not alongside the store files. `AgentStore.scan()` globs
`agents_root.glob("*.md")` — top level only — so a file written next to the store
entries would be read back as an agent named `<slug>.<harness>.conflict`. The
subdirectory makes that structurally impossible rather than relying on a filter.

Also shipped: the divergent harness copies are **left exactly where they are**. The
preserved copies are copies, not moves. Nothing is deleted in the case we cannot
decide.

"Newest mtime wins" is explicitly rejected for the differing-content case: it
silently discards the other harness's edit, which is the exact failure this whole
plan exists to prevent.

---

## 5. Codex is not symmetric — preserve it explicitly

The user expects drift "from Codex, Claude, Agy, or Cursor." Codex cannot
be treated like the others:

- Codex is a `renders` harness (`adapters.py`, `renders` → `.toml`). There is no
  symlink; HAM writes a real file carrying `GENERATED_MARKER`.
- Adoption from Codex preserves the modeled fields in Markdown and stores every
  unmodeled TOML field in an opaque `.codex.toml` sidecar. Codex-only fields do not
  leak into Markdown files symlinked into Claude, Agy, or Cursor.
- Rendered Codex files retain their rendered baseline hash. Reconcile compares the
  current rendered TOML semantically, so a one-sided Codex edit can be adopted safely
  while a two-sided conflict remains for manual review.

**AMENDED (shipped):** Codex is also excluded from the store-write **rebaseline**, for
the mirror-image reason. A store write reaches a symlinked harness automatically; it
does not reach a rendered file at all. Re-baselining Codex would record "the harness
has this content" about a copy that just went stale. Its `rendered_sha256` is recorded
at write time and only ever compared, never refreshed from the store side.

This is shipped behind the existing `auto_adopt.agents` setting, with tests covering
unknown nested fields, store edits, one-sided repair, and two-sided conflicts.

---

## 6. Cost rule

Reconcile runs on every list request, so it must not hash the world.

Hash a file only when **both**: a ledger record exists for that (slug, harness),
**and** the file's `mtime`/`size` differ from what the ledger recorded. Everything
else is a `stat()`. Files with no ledger record are already handled by the
existing `unmanaged_paths()` walk and need no hashing at all.

---

## 7. Skills — auto-adopt new local directories

**Implemented 2026-08-08 (opt-in, default off).** Formerly Stage 5, not Stage 4 — reordered
2026-07-27 behind slash commands (see §9). This is
a *different* mechanism from the rest of this plan: it is not clobber repair, because
skills cannot be clobbered (§12). Treat it as an optional convenience feature, and do it
only if it is wanted for its own sake.

Separate mechanism, separate setting, **default off**, because
`adopt_local_copy()` calls `shutil.rmtree(existing_dir)` on the user's real
directory.

Order of operations is non-negotiable and already modelled by
`SkillMutationService._manage_entry()`: **ingest into the store first, verify the
store copy exists and its content hash matches, and only then** `rmtree` +
symlink. A crash between those steps must leave the user's directory intact.

- Trigger: reconcile finds a directory in a harness skills root that is not a
  symlink and is not owned.
- Same-name collisions across harnesses follow §4's multi-harness rule — differing
  content is never auto-resolved.
- Skip anything matching the existing harness-specific exclusion policies; do not regress
  those ownership boundaries.

The clobber problem does **not** apply here — directory symlinks cannot be
replaced by `rename()`. Do not build clobber detection for skills.

---

## 8. Safety invariants

Every one of these deserves a test that proves the *unsafe* path is still refused.

1. Never delete a real file or directory until its content is in the store and
   hash-verified.
2. Never auto-resolve a two-sided conflict.
3. Never auto-adopt from a `renders` harness (v1).
4. A missing, truncated, or unparseable ledger degrades to today's prompt-the-user
   behaviour, never to a destructive default.
5. Every automatic action appends to an audit log surfaced in the UI. Silent
   repair is nearly as bad as silent breakage — the user must be able to see that
   HAM moved their content, and what it decided.
6. Keep the existing refusals in `enable()` / `disable()` /
   `disable_shared_package()` / `prepare_remove()` intact. They are the reason
   this failure is currently safe rather than destructive.

---

## 9. Stages

Each stage ships independently and leaves the tree working.

1. **✅ SHIPPED — Ledger, write-only.** Record on `enable()`/`disable()`. No reads, no
   behaviour change. Ship it, let records accumulate.
2. **✅ SHIPPED — Classification, read-only.** Implement §4 as a pure function over
   `(ledger_record, harness_hash, store_hash)`. Surface `clobbered` as a distinct
   issue kind in the inventory, separate from `unmanaged`. Still no automatic
   action — this alone removes most of the pain, because the user stops having to
   *notice* drift.
3. **✅ SHIPPED — Auto-repair the provable cases.** Rows 2 and 3 only, behind
   `auto_adopt.agents` (default on). Rows 1 and 4 keep prompting.
4. **✅ SHIPPED (2026-08-09) — Slash commands auto-repair drifted managed files.**
   Reuses the existing `content_hash` in `sync-state.json` as the baseline — no new
   persisted field was needed, since it already records what HAM wrote at that
   target the last time it wrote there. `classify_drift()` moved to the
   family-agnostic `application/drift.py` and is called directly; rows 2 and 3
   call the existing `restore_managed`/`adopt_target` review actions
   automatically, behind the same `auto_adopt.slash_commands` flag the new-file
   adoption pass already used (one setting per family, not one per mechanism).
   Rows 1 and 4 keep prompting. See §12.
5. **✅ SHIPPED (2026-08-08) — Skills auto-adopt**, behind `auto_adopt.skills`
   (default off). A *different* mechanism (§7), not clobber repair: it adopts
   genuinely **new** unmanaged directories and never repairs an existing binding,
   because a directory symlink cannot be clobbered (§12, `ENOTDIR`).
   `SkillsAutoAdoptService.reconcile()` groups unmanaged inventory entries, refuses
   any group whose local copies have differing revisions, refuses symlinks and
   non-directories, and delegates the move itself to
   `SkillsMutationService.manage_entry()` — which owns the non-negotiable
   ingest → verify → replace ordering from §7. Wired read-time in `container.py`.
   **Marker corrected 2026-08-10:** §7 recorded this as implemented on 2026-08-08 but
   this list still showed it unshipped, so the plan contradicted itself for two days.
6. **✅ SHIPPED (2026-08-10) — Codex lossless adoption and rendered drift repair.**
   Unknown TOML fields are stored in a Codex-only sidecar, verified semantically on
   adoption, and preserved when the shared agent is edited. One-sided rendered drift
   is repaired automatically; two-sided conflicts remain manual.

Stage 2 is the highest value-per-risk. If the work stalls, stall it there.

### AMENDED 2026-07-27 — why slash commands now comes before skills

The original order put skills next simply because §7 was written first. After Stage 3
shipped, that is the wrong order on every axis that matters:

| | slash commands (new Stage 4) | skills (now Stage 5) |
|---|---|---|
| Mechanism | same as Stage 3, already proven | new one, unproven |
| Worst case | rewrites a file **HAM authored** | `shutil.rmtree` on a **user's real directory** |
| Missing piece | one extra hash | ingest + verify + rmtree + symlink ordering |
| Problem solved | drift users hit today | drift that **cannot happen** (§12: `ENOTDIR`) |

Skills auto-adopt is a convenience feature wearing this plan's clothes. Slash commands
is the actual continuation of it. Do skills only if it is wanted for its own sake.

### AMENDED 2026-07-27 — do not ship the setting before the mechanism

Stage 3 added `"skills": False` to `DEFAULTS` in `auto_adopt.py` for a Stage 4 that had
not been built. Because `set_enabled` accepts any key in `DEFAULTS`, `PUT
/api/settings/auto-adopt/skills {"enabled": true}` returned **200 and persisted**, while
`container.py` reads only `is_enabled("agents")` — a setting that silently did nothing.
Unknown families correctly 404'd; the half-declared one was the only dishonest case.

Now refused with a 400 until the mechanism lands. **When adding Stage 4 or 5, wire the
consumer and flip the guard in the same change** — a declared-but-unread preference key
is worse than an absent one, because it reads as a working feature.

**AMENDED 2026-08-10 — the guard is now fully open, and that is correct.**
`IMPLEMENTED: set[str] = set(DEFAULTS)` in `application/settings/auto_adopt.py`, so no
family is refused any more. That is the intended end state, not a regression: every
family in `DEFAULTS` now has a real consumer, which is exactly the condition this rule
asks for. The rule still binds for any *future* family — add it to `DEFAULTS` only in
the change that wires its consumer. Note the mechanism this guard protected has
changed shape: with `IMPLEMENTED` derived from `DEFAULTS` rather than listed
separately, the two can no longer drift, but they also can no longer express
"declared but not yet wired." A future half-built family must therefore be held back
from `DEFAULTS` itself.

---

## 10. Tests

- Decision table (§4): one unit test per row, pure function, no filesystem.
- Multi-harness: one slug bound to three harnesses; assert one-diverged adopts,
  identical-diverged adopts once, differing-diverged refuses and writes
  `.conflict` files.
- Ledger degradation: delete / truncate / corrupt the ledger → behaviour is
  identical to today's, nothing destroyed.
- Crash safety for skills: simulate failure between ingest and `rmtree`; the
  user's directory must survive.
- Regression: the existing refusals still fire. `enable()` on a real file must
  still raise `real file exists at {path}; will not overwrite`.
- Reconcile is idempotent: running it twice changes nothing the second time.

---

## 11. Non-goals

- No filesystem watcher (§2).
- No content merging. HAM picks a side or asks; it never merges two versions.
- No automatic adoption for a rendered family without a lossless preservation contract;
  Codex agent TOML now has that contract and shipped in Stage 6 (§5).
- No change to the derived-state model. `is_enabled()` must keep deriving from the
  filesystem — the ledger is strictly additional evidence, never the authority.

---

## 12. Does this pattern belong in the other asset families? — verdict

Asked and answered 2026-07-27, from the code, and **re-audited 2026-08-08** after the
family-wide implementation. There are six families and they fall into four groups,
decided by binding shape. The current implementation is intentionally family-specific:
automatic ownership changes happen only when observations are equivalent.

| Family | Binding shape | Verdict |
|---|---|---|
| **agents** | `AgentFileBindingProfile` — file symlink | **Needs it.** Built here. |
| **slash_commands** | `CommandFileBindingProfile` — HAM writes a real file | **Needs it. Adopts equivalent new unmanaged files, and auto-repairs already-managed drifted ones (Stage 4, shipped 2026-08-09).** |
| **skills** | `FileTreeBindingProfile` — directory symlink | **Adopts equivalent new unmanaged directories; existing links are structurally immune.** |
| **mcp / hooks / permissions** | `ConfigSubtreeBindingProfile` | **Promotes equivalent unmanaged observations; never chooses between differing configs.** |

The remainder of this section preserves the original design audit and rejected alternatives.
The shipped read-time adopters are `SkillsAutoAdoptService`,
`SlashCommandsAutoAdoptService`, `McpAutoAdoptService`, and
`ObservedConfigAutoAdoptService`; all are independently gated by `autoAdopt` settings.

**Slash commands already shipped this pattern, before the agents ledger existed.**
`SlashCommandSyncStateStore` (`slash_commands/sync_state.py`) is the same ledger —
`{name: {target: {path, contentHash, renderFormat}}}`, versioned, `atomic_write_text`
+ `file_lock`, dropping malformed records on read rather than raising. Classification
lives in `read_models.py` (`_sync_entries`, `_tracked_review_rows`) and produces
`drifted` / `missing` / `unmanaged` rows with `restore_managed` / `adopt_target` /
`remove_binding` actions. The agents ledger was modelled on it deliberately, and
`hash_file` is now shared from `harness_asset_manager/hashing.py` so the two cannot
drift apart in format.

Its one gap: it records a single hash (what HAM wrote) with no store-side baseline, so
it can prove *that* a file changed but not that the change is one-sided. `adopt_target`
therefore stays a user decision.

**AMENDED 2026-07-27 — this is now Stage 4, and the verdict above is softened.** The
original wording ("already has it") was written before Stage 3 existed and reads as
"nothing to do." Re-audited from the code today: slash commands **detect** drift and
surface it for review, but every repair is user-initiated (`import_unmanaged_command`,
`_adopt_target`). No slash-command binding is ever repaired automatically. That is not
the same as having this pattern — it is Stage 2 without Stage 3.

The follow-on was gated on "if Stage 3 proves the pattern out." Stage 3 shipped and
held. So it is unblocked, and it is the cheapest remaining work in this plan:

- Record a second hash — the store-side content at write time — alongside the existing
  `contentHash`, in the same `sync-state.json` record.
- Feed both into `classify_drift()`. It is already a **pure function** over
  `(ledger_record, harness_hash, store_hash)` and is family-agnostic; reuse it rather
  than writing a second decision table. The four rows carry over unchanged.
- Rows 2 and 3 auto-repair; rows 1 and 4 keep prompting, exactly as agents does.
- Gate it behind a new `auto_adopt.slash_commands` key, **added in the same change as
  its consumer** (see §9's amendment on not shipping the setting early).
- Every §8 invariant applies unchanged, including the audit log — the existing "Recent
  automatic repairs" surface should grow a family column rather than gain a sibling.

Cheaper than agents was: the ledger, the classification inputs, the review rows, and the
UI all exist. The reason to do it is that slash commands is the one remaining family
where the drift is **real and reachable today** — unlike skills, which cannot be
clobbered at all.

**AMENDED (shipped 2026-08-09) — corrections against what was actually built.** Two
details above did not survive contact with the implementation:

- **No second hash was needed.** The existing `contentHash` already *is* the
  store-rendered baseline: it is set to `hash_file(path)` immediately after writing
  `render_slash_command(command, format)` to that path, so it is byte-identical to
  hashing the rendered command at that moment. The only new computation is the
  *current* store hash, `hash_text(render_slash_command(current_command, format))`,
  computed fresh each reconcile — nothing new is persisted.
- **`auto_adopt.slash_commands` already existed** (added when new-unmanaged-file
  adoption shipped 2026-08-08), so this reused it rather than adding a second key.
  One toggle covers every safe automatic ownership change for a family; see §9 item 4.
- The audit trail is the mutation audit journal (`record_auto_repair`, `operation:
  "auto_repair"`, appended to `data/audit.log`), not the agents-specific
  `AgentAuditLog` — that mechanism was itself generalized into the mutation audit
  journal by the 2026-08-07 mutation-audit work, after this section's "grow a family
  column" note was written.
- `classify_drift()` was generalized to take a plain `baseline_sha256` instead of an
  `AgentBindingRecord`, and moved to `harness_asset_manager/application/drift.py`.
  The agents ledger's `classify_drift()` is now a thin wrapper over it.

**Skills cannot be clobbered.** A skill binds as a *directory* symlink, and
`rename(dir, dir-symlink)` fails `ENOTDIR` at the kernel — verified empirically (see
the 2026-07-27 handoff entry). A harness writing into the directory resolves *through*
the link into the store, which is the behaviour we want. §7's skills work is a
genuinely different mechanism (auto-adopt *new* local directories, `rmtree`-adjacent,
default off) and must not be folded into the agents one.

**Config-subtree families do not have a binding to clobber.** MCP, hooks, and
permissions write *into* a config file the harness owns (`~/.claude.json`,
`~/.cursor/hooks.json`, …). There is no symlink, and no whole-file hash means anything
because the harness legitimately rewrites the rest of the file at will. The right
mechanism for external edits there already exists and is a different one: the config
snapshots service (2026-07-25 handoff) hashes those files, captures external changes
at startup, and keeps timestamped baselines. Do not build a second one.
