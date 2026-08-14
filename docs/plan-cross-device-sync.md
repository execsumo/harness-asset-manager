# Plan — Cross-device sync

**Status: not started.** Written 2026-08-09 from a code read, after a design discussion.

**Goal:** one person, several machines. Assets HAM manages should be the same on every
machine that person uses, without copying files by hand or re-installing from the
marketplace on each one. HAM already collapses *many harnesses → one store*; this adds
*many machines → one store*, using the same store as the unit.

**Explicitly not a sharing feature.** Multi-person and team distribution are out of
scope permanently, not deferred — that need is served by the published Plugin versions.
See §12.

---

## 1. The store is the sync unit — not the harness directories

**Decision: sync `~/.harnessam/` (or the XDG `harnessam` data/config roots), recompute bindings locally on arrival.
Settled — do not re-litigate.**

The obvious cheap alternative is "point Dropbox/iCloud/Syncthing at `~/.claude`". It
cannot work, and the reasons are the same reasons HAM exists:

| Family | How it binds | What naive folder-sync does to it |
|---|---|---|
| Skills | directory symlink into the harness skills root | link target is `/Users/alice/...`; meaningless under `/home/alice/...` |
| Agents | file symlink (Codex: rendered TOML) | same, plus Codex renders are generated per machine |
| Slash commands | rendered files per target format | fine to copy, but the sync-state hashes describe the *other* machine |
| MCP | translated into JSON / TOML / YAML / JSONC per harness | five different config shapes, none of them the canonical record |
| Hooks, Permissions | **merged into** config files the user also owns | overwrites the receiving machine's own unmanaged keys |

`paths.py:80-98` already diverges macOS (`~/.harnessam`) from Linux (XDG),
so absolute paths differ between machines even for the same user. Anything that
transports resolved paths is wrong on arrival.

The canonical records, by contrast, are portable by construction — that is what they
were normalized *for*. Sync them, and let each machine's existing projection code write
the harness files it already knows how to write.

**Corollary that removes most of the perceived risk:** sync never writes a harness
config file. It writes store records; the existing, tested, `flock`-serialized
projection path does the rest. The dangerous part of this feature is the *content*
crossing machines, not the writing.

---

## 2. The conflict engine already exists

`application/drift.py` is a pure, family-agnostic three-way classifier over three
hashes. Its docstring already invites this reuse: *"Any family whose binding shape is
'Harness Asset Manager writes a real file a harness can independently overwrite' can
reuse this."* A second machine is such a thing.

| `classify_drift` parameter | Meaning today | Meaning for sync |
|---|---|---|
| `baseline_sha256` | what the ledger recorded when we last bound | what we recorded at the last successful sync |
| `harness_sha256` | what the harness-owned copy holds now | what the remote holds now |
| `store_sha256` | what the store would produce now | what this machine's store holds now |

The four outcomes carry over unchanged:

| `DriftKind` | Sync meaning | Action |
|---|---|---|
| `clobber_clean` | both sides identical | no-op |
| `clobber_one_sided` | only one side moved since the baseline | take the side that moved |
| `two_sided_conflict` | both moved | preserve both, report, change nothing |
| `collision` | no usable baseline | report, change nothing |

**Newest-file-wins remains not a rule.** It is the exact failure the existing design
refuses, and a clock skew between two machines makes it worse here than it is locally.

`clobber_one_sided` — "the side that moved holds the only edit in existence, so nothing
can be discarded by preferring it" — is **provably true for one person's machines** and
is why this plan is tractable. It would be false across people, which is one more reason
§12 holds.

---

## 3. Transport: git, and HAM never lets git merge

**Decision: a private git remote the user owns. Settled.**

- No service to build or operate, no accounts, no new trust boundary — the local-first,
  no-authentication positioning in the README survives intact.
- History, diff, and rollback come free (and largely subsume a separate snapshot
  feature — see §12).
- Named atomic revisions are exactly the baselines §2 needs. Folder-sync products
  (iCloud, Dropbox, Syncthing) cannot provide one: they replicate mid-write and have no
  consistent point to call "the state we both last agreed on".

**Invariant: HAM never invokes a git merge.** Fetch to a scratch ref, read the remote
tree, classify per record in HAM's model, write the result. A line-based merge of
`manifest.json` is the single most likely way this feature corrupts someone's portfolio.

---

## 4. The portable / device-local split

The riskiest decision in the plan; everything else hangs off it. Get it wrong and one
machine's reality is projected onto another.

| Travels | Never travels | Why |
|---|---|---|
| `skills/` package trees | `bindings.json` | records this machine's link targets |
| `agents/*.md` | `configs/` | native config snapshots of *this* machine |
| `mcp/manifest.json` (minus secrets, §5) | `runtime.json`, `server.log` | process state |
| `hooks/manifest.json` | `marketplace/` | disposable cache |
| `permissions/manifest.json` | `audit.log` | per-machine journal; see §12 |
| `slash-commands/commands/` | `slash-commands/sync-state.json` | hashes describe this machine's renders |
| `skills-manifest.json` | `settings.json` → `disabledHarnesses` | which harnesses exist here is a machine fact |
| per-asset enablement **intent** | `agents-audit.json`, `agents/conflicts/` | local reconciliation history |

**Intent travels; placement does not.** "This skill should be enabled wherever it is
supported" crosses machines. "This skill is symlinked at
`/Users/alice/.claude/skills/x`" does not. Without the intent, a new machine receives a
full portfolio with nothing wired up, and the bootstrap moment — the whole point — does
not happen.

`settings.json` is shared with other stores and must be merged through
`settings_file.update_settings_document`, never serialized wholesale (that function
exists because a store that writes only its own keys deletes everyone else's).

---

## 5. Secrets are excluded structurally, not redacted

**Decision: MCP `env` and `headers` values are never serialized into the bundle. Keys
travel; values do not. Settled.**

The receiving machine materializes the server with its keys present and values absent,
and reports it in Needs Review as *needs credential*. This turns the most dangerous part
of the feature into its own small feature: a new laptop tells you exactly which
credentials it is missing.

`config_snapshots/redaction.py` is a regex pass over config *text* and is the right tool
for its own job. It is the wrong instrument here and must not be relied on as the
boundary — MCP env is already structured key/value data, so exclusion is exact rather
than best-effort. Keep the regex scan only as a pre-publish **refusal** gate over the
whole serialized bundle: if it matches anything, abort the publish. Warning is not
enough. A secret committed to git is in the history permanently, and removing the file
later does not remove it.

Hook `command` strings are free-form shell and can contain an inline credential
(`curl -H "Authorization: Bearer ..."`). The same pre-publish gate covers them; this is
one reason hooks sequence late (§8).

---

## 6. Deletion — tombstones, decided up front

The classic sync failure, and the one most likely to be retrofitted painfully. "Asset
absent on the remote" is ambiguous: deleted deliberately, or never arrived yet? A union
merge resurrects deleted assets forever; a mirror merge lets one machine's absence
delete everything.

**Decision: the bundle carries explicit tombstones** — asset id, family, deletion time —
retained for a bounded window (90 days), after which absence means absence. A tombstone
newer than this machine's baseline deletes locally; older than it, ignore.

---

## 7. Phase sequence — the mechanism

Each phase has a gate that can fail before the next one starts.

### Phase 0 — The split and the bundle envelope

**Ships:** portable/device-local split (§4), bundle format with its own version number,
tombstone shape (§6), structural secret exclusion (§5). Proven end-to-end with **agents
only** (§8).

**User-visible value:** none. Say so honestly rather than dressing it up.

**Gate:** export → import into a clean synthetic home reproduces a byte-identical
portfolio; a scanner proves the bundle contains zero device-local paths and zero secret
values.

### Phase 1 — Provision (one-way)

**Ships:** `harnessam sync init <remote>`, `harnessam sync pull`. Read-only. Local
divergence is *reported*, never merged.

**Value:** the loveable moment — new machine, one command, the portfolio is there and
wired into whatever harnesses that machine has. Also covers ephemeral and headless
devices (devcontainers, VPS, CI), which should pull and never push; for them this is not
a stepping stone but the correct permanent behaviour.

**Gate:** two synthetic devices plus a bare repo in CI; a container smoke test that
pulls and binds correctly against a *different* installed-harness set than the source.

### Phase 2 — Converge (bidirectional)

**Ships:** `harnessam sync publish`, the merge engine (§2), tombstone propagation,
per-asset **don't-sync** flag (§12 — the cheap stand-in for profiles).

**Value:** real two-machine sync.

**Gate:** the full conflict matrix — every `DriftKind` × {edit, delete, both-edit,
rename} — against two synthetic devices, plus a property test over the pure classifier.

### Phase 3 — The config-injection families

**Ships:** permissions → hooks → MCP, one at a time, each with its own portability
handling (§8). Each family is independently shippable; the UI states which families sync,
in the same honest way the harness matrix already prints "Not Yet" cells.

### Harness scope — core first, at every phase

**Decision: correctness on the core four before the best-effort harnesses are considered
at all. Settled.** The tier is declared in `catalog.py` (`support_tier`) and reachable via
`core_harness_ids()`; see README → Supported harnesses → Support tiers.

- **Phase 1's gate is a core-harness gate.** "A target machine with a different
  installed-harness set" means a container that receives Claude and Codex bindings
  correctly — not one that happens to exercise Hermes.
- **Phase 3 reaches correctness on core before touching the rest.** MCP is the clearest
  case: it is hardest precisely because of the number of config shapes, and cutting the
  set to the core four removes a third of them from the critical path.
- Best-effort harnesses are not *excluded* from sync — records are harness-agnostic, so
  they come along. They are excluded from the **gates**. A sync bug that only manifests on
  OpenCode does not block a phase.

### Phase 4 — Make devices visible

**Ships:** device presence per asset ("on 2 of 3 machines") and a differences summary on
Overview. Deliberately *not* a third matrix axis — at two or three machines the axis costs
more than it returns.

---

## 8. Family sequence — the payload

Sync difficulty is **not** the same as family complexity. Because sync never writes
harness config files (§1), binding shape is mostly not the driver. The driver is
**content portability**: does this record mean the same thing on another machine?

| # | Family | Binding shape | Device-specific content | Verdict |
|---|---|---|---|---|
| 1 | **Agents** | file symlink (Codex renders) | none | trivial — start here |
| 2 | **Slash commands** | rendered files | none | trivial |
| 3 | **Skills** | directory symlink | none; bulk is the only issue | easy |
| 4 | **Permissions** | merged into shared config | occasional absolute path glob | moderate |
| 5 | **Hooks** | merged into shared config | `command` references local scripts | hard |
| 6 | **MCP** | translated into 5 config shapes | secrets, absolute paths, requires the binary installed | hardest |

**1. Agents.** A single self-contained Markdown file: frontmatter plus a prompt body. No
paths, no secrets, no machine assumptions. It is also the only family whose drift
machinery is already built and battle-tested (`bindings.json`, `classify_drift`,
`agents/conflicts/`), so Phase 0 proves the envelope against the family with the most
existing scaffolding. Codex's rendered TOML is generated locally on arrival and never
travels.

**2. Slash commands.** Name, description, prompt. `$ARGUMENTS` is resolved at runtime, so
nothing in the record is machine-bound. Already calls `classify_drift` directly, and
rendering is one-way (store → harness), so arrival has no adoption decision to make.

**3. Skills.** Portable text and files, and the safest binding shape in the codebase —
a directory symlink cannot be clobbered by an atomic rename (the kernel refuses it), so
the arrival state is stable. The only new question is bulk: skill packages carry scripts
and resources. **Decision: ship bytes, not locators.** `SourceDescriptor.is_source_backed`
could let a marketplace skill be re-fetched on arrival instead of transported, but that
makes sync depend on a network fetch and on the upstream still existing at that revision.
Transport the bytes; revisit only if repository size becomes a real complaint.

**4. Permissions.** The most portable of the three config-injection families, and the
right one to prove the pattern on. Of the five scopes, `shell` (command prefix), `web`
(domain), and `mcp` (`server/tool`) are fully machine-independent, and the `file_read` /
`file_write` idiom is already tilde- or project-relative (`~/.zshrc`, `./secrets/**`).
Only an absolute glob is a problem, and it is rare. Low secret risk. Denylists are also
the family where being out of sync is most consequential, so it earns its place ahead of
hooks.

**5. Hooks.** The record is portable in shape but its `command` is a raw shell string
that usually references a script or binary on the originating machine. Arrival must
therefore **check resolvability** and report an unresolvable hook rather than syncing a
hook that silently never fires — a hook that looks enabled and does nothing is worse than
an absent one. Also the family most likely to carry an inline credential (§5), and its
representability already differs per harness (partial on agy and OpenCode), though that
is modeled today and needs no new work.

**6. MCP.** Everything hard about sync lives here, which is why it goes last rather than
first despite being the family users feel most: secrets in `env` and `headers` (§5);
absolute paths in `command` and `args` (`/Users/alice/.local/bin/uvx` vs
`/home/alice/...`); a record that is only meaningful if the underlying binary is installed
on the target; five config shapes; and the `extras` tuple of preserved unknown fields
that must survive a round trip through the bundle exactly as it survives a round trip
through a harness config today.

**MCP path handling.** Tokenize `${HOME}` on publish, re-resolve on arrival, and re-probe
the command against `PATH`. When it cannot be resolved, materialize the record and mark it
needs-attention. **Never write a harness config containing a command path known not to
exist** — a broken server reads to the user as "sync is buggy" and costs more trust than
the missing server would.

---

## 9. Safety invariants

1. **Sync never writes a harness config file directly.** It writes store records; the
   existing projection path writes harness files.
2. **HAM never invokes a git merge.** (§3)
3. **Newest-wins is never a resolution rule.** (§2)
4. **Two-sided conflicts change nothing.** Preserve both sides, report, move on —
   exactly as `agents/conflicts/` does today.
5. **Sync is staged.** Compute the entire plan and decide every write before applying
   any of them. Never interleave classification with mutation.
6. **Secret values never enter the bundle**, and a pre-publish match aborts rather than
   warns. (§5)
7. **Losing the sync state degrades to "no baseline", never to a destructive default** —
   the same rule the agents ledger already follows (`collision`, ask the user).
8. **Sync runs after local reconciliation has settled, never interleaved with it.** (§10)
9. **Every sync mutation goes through the audited service wrappers**, and sync is opt-in
   per family exactly as `autoAdopt` already is.

---

## 10. Pre-mortem — how this fails

Ranked by likelihood × severity, with the mitigation each one buys.

1. **It resurrects deleted assets, or propagates a delete nobody wanted.** The most
   under-designed part of every sync system. → Tombstones, decided in Phase 0 (§6).
2. **It eats someone's work.** One data-loss incident on a config manager and the feature
   is never re-enabled. → Invariants 2–5.
3. **A secret lands in git history permanently.** → Invariant 6, structural exclusion (§5).
4. **Conflict fatigue poisons a feature that already works.** Needs Review is trustworthy
   today because every entry is real. Fill it with routine sync noise and users stop
   reading it — degrading the harness drift detection they already rely on. → Track
   conflict rate as a metric with a budget; keep sync differences visually distinct from
   harness drift; the common case must produce zero entries.
5. **Ping-pong with auto-adopt.** Machine A adopts a harness-rewritten file and publishes;
   B pulls, projects, B's harness rewrites it, B adopts and publishes back. Infinite
   commits and audit noise. → Invariant 8, plus oscillation detection: one asset flipping
   between a small set of hashes stops and reports instead of continuing.
6. **Nobody sets it up.** A `brew install` app that now wants a git remote and a
   push/pull model has a real onboarding cliff. → Make the headless/container case the
   documented hero path; that audience already lives in git. Let `sync init` create the
   repo where it can.
7. **Platform skew breaks arrivals.** Absolute paths, macOS ↔ Linux. → §8 MCP path
   handling; mark needs-attention rather than writing a broken config.
8. **Bundle version skew.** Machines update at different times (brew on one, source on
   another). → Version the bundle; refuse rather than corrupt; and make sure a refusal
   cannot deadlock two machines permanently — the newer side must still be able to
   publish something the older side can at least read and report.
9. **Repository bloat** from skill resources over time. → Accepted for now (§8); revisit
   with real numbers.

---

## 11. Tests

`tests/support/fake_home.py` is already a complete synthetic machine — `HOME`, all three
XDG roots, and a stub `PATH` with an executable per harness so `install_probe` detection
works. **Two of those plus a bare git repo is a full two-machine sync test, in process, in
CI.** The whole merge engine is testable from day one with no cloud and no second laptop;
the conflict matrix belongs in the gate, not in manual QA.

- Property test over `classify_drift` — it is pure and filesystem-free, so exhaustive
  coverage of the three-hash space is nearly free.
- Round-trip: export → import into a second synthetic home is byte-identical.
- Bundle scanner: asserts no device-local path and no secret value can appear.
- Conflict matrix: every `DriftKind` × {edit, delete, both-edit, rename}.
- Divergent-harness arrival: source machine has seven harnesses, target has two.
- Oscillation: reconcile + sync together must reach a fixed point, not a loop.

---

## 12. Non-goals

**Permanently out of scope:**

- **Multi-person and team distribution.** Served by the published Plugin versions. This
  is not deferred — merge rules that are correct for one person's machines are wrong
  across people (§2), and building for both produces a worse tool for each. Do not add a
  remote "role" concept in anticipation; there is nothing to anticipate.
- **A hosted service, accounts, or a HAM-operated backend.**

**Roadmap, deliberately not now:**

- **Profiles / device classes.** The per-asset don't-sync flag in Phase 2 is the cheap
  stand-in and covers the stated case (a few work-only MCP servers). Build real profiles
  only if the flag proves too blunt.
- **A standalone harmonization view.** The useful part folds into Phase 4's Overview
  differences.
- **Portfolio snapshots and rollback.** Largely subsumed: once Phase 2 ships, git history
  *is* portfolio rollback (§3).
- **Credential indirection** (keychain / 1Password resolution on arrival). The structural
  exclusion in §5 stands on its own.
- **Automatic or background sync.** Explicit verbs only. There is no background
  infrastructure to hang a watcher on — see `plan-auto-adoption.md` §2, whose reasoning
  applies here unchanged.
- **Rich conflict-resolution UI.** Two-sided conflicts require editing the same asset on
  two machines between syncs, which is rare for one person. Preserve copies, add a Needs
  Review row, build nothing else until the conflict rate says otherwise.
- **Device attribution in `audit.log`.**

---

## 13. Defect found while writing this — fixed 2026-08-09

`README.md` claimed `--state-dir` "isolates a run, which is how you keep CI or a throwaway
sandbox from touching the real store." It did not: `paths.py`'s old `_base_dirs()` used
`STATE_DIR_ENV` only for `state_dir` (`runtime.json`, `server.log`); `config_dir` and
`data_dir` still resolved from XDG or the macOS default, so anyone following that advice
wrote to their real store. Tracked as `RECOMMENDATIONS.md` §1.4.

**Fixed**, ahead of Phase 0. When `STATE_DIR_ENV` is set, `_base_dirs()` now collapses
`config_dir`, `data_dir`, and `state_dir` into that one directory — the same shape the
macOS default already produces when no XDG variable is set, just requested explicitly.
`--state-dir` now means what the README always said it meant: any single command, or a
whole CI run, can be pointed at one throwaway directory and genuinely touch nothing else.

This is a narrower fix than §11's test strategy needs and does not replace it. `--state-dir`
collapses one run into one directory; `fake_home.py`'s separate `HOME` + three XDG roots
deliberately keep config/data/state apart, the same way a real machine does, which is what
lets those tests catch the platform-skew failures §10 item 7 calls out. Both are correct,
for different jobs: `--state-dir` for "isolate this one run," `fake_home.py` for "simulate
a realistic machine."
