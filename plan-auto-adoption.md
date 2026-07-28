# Plan — Automatic re-adoption of drifted bindings

**Status:** not started. Written 2026-07-27 from a code read, no implementation yet.
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

Reconcile runs at the top of inventory build, under the existing `file_lock`, and
must be idempotent and cheap — see §6 for the cost rule.

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

`delegate` may be bound into Claude, AGY, and Hermes simultaneously. Resolve
**per slug, not per binding**: gather every drifted binding for a slug first, then
decide once.

- Exactly one harness diverged → adopt it, relink the rest. (Row 3.)
- Several diverged, **identical** content hashes → same edit seen from several
  places. Adopt once, relink the rest.
- Several diverged, **differing** content → **do not auto-resolve.** Keep the store
  as-is, preserve each divergent copy as `<store>/<slug>.<harness>.conflict.md`,
  and surface one issue naming every side. The user picks.

"Newest mtime wins" is explicitly rejected for the differing-content case: it
silently discards the other harness's edit, which is the exact failure this whole
plan exists to prevent.

---

## 5. Codex is not symmetric — scope it out of v1

The user expects drift "from codex, or from claude, or from hermes." Codex cannot
be treated like the others:

- Codex is a `renders` harness (`adapters.py`, `renders` → `.toml`). There is no
  symlink; HAM writes a real file carrying `GENERATED_MARKER`.
- Adoption *from* Codex round-trips through `parse_codex_agent()` →
  `render_agent_document()`, which keeps only `name`, `description`, `prompt`.
  Any other TOML the user added is **dropped**. That is lossy, and doing it
  automatically means silently discarding content.
- `enable()` on the renders path overwrites with no drift detection at all — the
  class docstring says so outright: *"**No drift detection**: re-enabling
  overwrites local edits to a rendered file."*

**v1: symlink harnesses only** (Claude, Cursor, AGY, OpenCode, Hermes). For Codex,
do the cheap useful half — store `rendered_sha256` at write time, compare on
reconcile, and when it differs surface *"Codex's copy was edited locally"* as an
issue with the existing manual adopt action. Detection without automation.

Automating Codex needs a lossless round-trip first (preserve unknown TOML keys
through parse/render, with a property test proving `render(parse(x)) == x`). That
is its own piece of work — do not smuggle it into this one.

---

## 6. Cost rule

Reconcile runs on every list request, so it must not hash the world.

Hash a file only when **both**: a ledger record exists for that (slug, harness),
**and** the file's `mtime`/`size` differ from what the ledger recorded. Everything
else is a `stat()`. Files with no ledger record are already handled by the
existing `unmanaged_paths()` walk and need no hashing at all.

---

## 7. Skills — auto-adopt new local directories

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
- Skip anything matching the existing exclusion policies (Hermes bundled/learned
  skills are already handled by `_hermes_scan_policy`; do not regress that).

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

1. **Ledger, write-only.** Record on `enable()`/`disable()`. No reads, no
   behaviour change. Ship it, let records accumulate.
2. **Classification, read-only.** Implement §4 as a pure function over
   `(ledger_record, harness_hash, store_hash)`. Surface `clobbered` as a distinct
   issue kind in the inventory, separate from `unmanaged`. Still no automatic
   action — this alone removes most of the pain, because the user stops having to
   *notice* drift.
3. **Auto-repair the provable cases.** Rows 2 and 3 only, behind
   `auto_adopt.agents` (default on). Rows 1 and 4 keep prompting.
4. **Skills auto-adopt**, behind `auto_adopt.skills` (default off).
5. **Deferred:** Codex, gated on a lossless TOML round-trip.

Stage 2 is the highest value-per-risk. If the work stalls, stall it there.

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
- No automatic Codex adoption (§5).
- No change to the derived-state model. `is_enabled()` must keep deriving from the
  filesystem — the ledger is strictly additional evidence, never the authority.
