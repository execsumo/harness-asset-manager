# Plan — Adopting a synced store on a new device

**Status: Phase 0 shipped 2026-09-02** (`36afd4e` — skills now record per-harness binding
intent). Phases 1–3 unbuilt.

Written 2026-09-02 from a code read.

**Goal:** when a user dotfiles `.harnessAM` and clones it onto a second machine, give them one
deliberate action that rebuilds their bindings there — instead of re-enabling every asset on
every harness by hand.

Read `plan-auto-adoption.md` first. This plan reuses its drift vocabulary and its invariant that
losing a ledger degrades to "prompt the user", never to a destructive default.

---

## 1. Why this is not a startup pass

The tempting version of this feature runs at boot and silently links everything the store says
should be linked. It is wrong, and the code already says why.

`AgentBindingRecord` (`application/agents/ledger.py:19-27`):

> A **cache, never a source of truth.** `is_enabled()` keeps deriving from the filesystem.

Enablement is derived from disk across every family. That has a consequence people miss: **a
fresh device and a device where the user deliberately disabled everything are byte-for-byte
identical observations.** There is no signal at startup that separates them. Anything automatic
is therefore guessing, and guessing wrong writes into `~/.claude`, `~/.codex` and friends —
directories whose whole reason for having a drift subsystem is that other writers touch them.

So the missing bit is supplied by a human, once, explicitly. A confirmed CTA is a legitimate way
to promote a cache to intent. A boot-time pass is not.

Three rules fall out of this and constrain everything below:

- **Additive only.** Apply creates bindings. It never removes a local binding merely because the
  synced intent lacks it — the user may have turned that off on *this* machine on purpose.
- **Never overwrite.** An occupied target is a conflict to report, not a file to replace.
- **Never widen support.** Apply does not install harnesses and does not re-enable a harness the
  user disabled in `disabledHarnesses` (`harness/support_store.py:19-51`).

---

## 2. What survives a sync today

Verified by code read. This table is the spec's foundation; re-check it before extending.

| Family | Per-harness intent in the synced store? | Where | Binding mechanism |
|---|---|---|---|
| **Agents** | ✅ | `bindings.json` — slug → harness → record, portable `~/` paths (`agents/ledger.py:49-50`) | symlink to file; rendered file for Codex |
| **Slash commands** | ✅ | `sync-state.json` — command → target → record (`slash_commands/sync_state.py:18-33`) | rendered file |
| **Skills** | ✅ *(Phase 0)* | `enabledHarnesses` on `SkillStoreEntry` (`skills/manifest.py`) | symlink to directory |
| **MCP** | ❌ | `McpServerSpec` has no harness field (`mcp/store.py:52-77`) | config-file merge |
| **Hooks** | ❌ | `HookSpec` has none; status derived from live scans (`hooks/managed_state.py:89-94`) | config-file merge |
| **Permissions** | ❌ | `PermissionSpec` has none (`permissions/store.py:25`) | config-file merge |

Two groups, and they are not the same problem:

- **Placement families** (agents, slash commands, skills) bind by creating a filesystem object at
  a path. Intent is present for all three. Conflict = "something already occupies that path".
- **Config-merge families** (MCP, hooks, permissions) bind by merging keys into a harness's own
  config file. Intent is absent, and conflict is key-level, not file-level.

Phase 1 does the placement families only. Do not merge the two — that is the same trap
`plan-auto-adoption.md` §1 warns about.

### What `refresh --sync-all` actually does

It flips `set_auto_adopt(family, enabled=True)` for all six families, then calls each query path
once (`cli/commands/refresh.py:32-41`). Query-path reconcilers only act on assets already present
in a harness directory: skills auto-adopt processes `kind == "unmanaged"` entries
(`skills/auto_adopt.py:67`), and agent reconcile skips any slug whose `binding_path` does not
exist (`agents/reconcile.py:99`). On a device whose disk is empty, both are no-ops.

**It cannot backfill bindings, and `README.md:813` is wrong to imply it can** (the command table
at `README.md:665` oversells it too). Fixing that text is part of Phase 1.

---

## 3. Phase 0 — recorded intent for skills ✅

Shipped in `36afd4e`. `SkillStoreEntry.enabled_harnesses` (serialized `enabledHarnesses`),
written at all five sites that create or remove a skill binding: `enable_skill`, `disable_skill`,
`set_skill_all_harnesses`, `enable_managed_package`, and adoption in `_manage_entry`.

Properties worth preserving in anything that touches it: omitted from JSON when empty (old
manifests stay byte-identical); sorted and de-duplicated (a dotfiled manifest must not churn in
git diffs); total on read (malformed intent → none recorded, never raises); best-effort on write
(the adapter already succeeded, so a failed manifest write must not turn a completed enable into
a 500). Reuse `normalize_enabled_harnesses` rather than re-implementing the coercion.

---

## 4. Phase 1 — the planner

New module: `harness_asset_manager/application/adopt/`.

### 4.1 Data model

```python
Action = Literal["link", "skip", "conflict"]

@dataclass(frozen=True)
class AdoptionAction:
    family: str            # "skills" | "agents" | "slash_commands"
    ref: str               # skill_ref / agent slug / command name
    display_name: str
    harness: str
    action: Action
    target: Path           # where the binding would land on THIS device
    reason: str | None     # machine-readable skip/conflict code
    detail: str | None     # human sentence for the UI

@dataclass(frozen=True)
class AdoptionPlan:
    actions: tuple[AdoptionAction, ...]

    @property
    def linkable(self) -> tuple[AdoptionAction, ...]: ...
```

The planner is **pure with respect to mutation**: it reads the store and stats the filesystem,
and writes nothing. That is what makes `--dry-run` trustworthy and the plan cheap enough to
compute on every page load.

### 4.2 Per-asset decision

For each `(ref, harness)` pair in recorded intent:

| Condition | Result | `reason` |
|---|---|---|
| Harness not installed on this device | `skip` | `harness-not-installed` |
| Harness support disabled in settings | `skip` | `harness-support-disabled` |
| Store no longer holds the asset | `skip` | `asset-missing-from-store` |
| Target already the correct binding | `skip` | `already-linked` |
| Target exists, foreign content | `conflict` | `target-occupied` |
| Otherwise | `link` | — |

`already-linked` is what makes the operation idempotent, and idempotence is what makes it safe to
offer repeatedly and safe to script. Test it explicitly: applying a plan twice must yield zero
actions the second time.

For `target-occupied`, classify with the existing family-agnostic table in `application/drift.py`
and carry the `DriftKind` into `detail`. Do not invent a second opinion about clobbering — there
is already one, it is tested, and disagreeing with it is how the two paths drift apart.

### 4.3 Sources of intent

- **Skills** — `enabled_harnesses` per `SkillStoreEntry`.
- **Agents** — `AgentBindingLedger.load()`, slug → harness. Records whose `target` fails
  `from_portable_path` (a legacy absolute path from another machine) are already dropped on load;
  they must surface as `skip` / `asset-missing-from-store`, never as a crash. There is an existing
  test for that degradation: `test_cross_device_legacy_absolute_paths_degrade_safely`.
- **Slash commands** — `SlashCommandSyncStateStore.load()`, command → target.

---

## 5. Phase 1 — the applier

The apply primitives already exist and are already proven to work on a fresh machine by
`tests/unit/test_cross_device_arrival.py:146-168`:

| Family | Call |
|---|---|
| Agents | `agents_mutations.enable(slug, harness)` |
| Skills | `skills_mutations.enable_managed_package(package_path, harness)` |
| Slash commands | `slash_command_mutations.sync_command(name, targets=[...])` |

So the applier is a loop with bookkeeping, not new binding logic. Requirements:

- Takes an explicit list of actions (from a plan the caller reviewed) — never re-derives its own
  plan internally, or the UI's preview and the applied result can disagree.
- Re-checks each target immediately before acting. The plan may be seconds old; the disk is
  authoritative at the moment of the write.
- Per-action failures aggregate and do not abort the run, matching `set_skill_all_harnesses`
  (`skills/mutations.py:123-136`). One bad asset must not strand the other forty.
- Applies `conflict` actions only when the caller passed them explicitly. Default selection
  excludes them.
- Invalidates read models once at the end, not per action.
- Writes a `MutationAuditJournal` entry per applied action, mirroring `record_auto_adopt`.

---

## 6. Phase 1 — surfaces

### API

New router `api/routers/adopt.py`:

- `GET /api/adopt/plan` → the plan payload.
- `POST /api/adopt/apply` → body carries the selected actions; returns per-action results
  (`applied` / `failed` with error text).

### CLI

New command `harnessam adopt` (`cli/commands/adopt.py`), sharing the planner with the API:

```
harnessam adopt --dry-run     # print the plan, change nothing
harnessam adopt               # interactive confirm, then apply
harnessam adopt --yes         # non-interactive; for dotfiles bootstrap scripts
harnessam adopt --yes --json  # machine-readable, for the same
```

The headless path is not a nice-to-have. A new device is very often a server reached over SSH,
and the whole feature lives inside a dotfiles workflow — `adopt --yes` is the line users will put
at the end of their bootstrap script.

### Web UI

A dismissible banner on the workspace, not a buried settings toggle.

- **Trigger:** the plan contains ≥1 `link` action. Derived state — deliberately **not** a
  first-run flag, so it re-appears correctly if someone wipes `~/.claude` later.
- **Flow:** banner → review sheet (grouped by family, conflicts listed separately and unchecked)
  → apply → per-row result.
- **Dismissal must be device-local.** Persist it under `xdg_state_home`, never in the synced
  store — a dismissal that travels in `.harnessAM` would suppress the banner on every future
  device, which is precisely the machine that needs it.

---

## 7. Testing

Beyond unit coverage of the decision table:

- **Extend `test_cross_device_arrival.py`.** It already builds two machines and copies a store; it
  is the natural home for "machine B plans N links, applies them, and every binding is live and
  rooted under B's paths".
- **Idempotence.** Apply, then re-plan: zero actions.
- **Additive-only.** A binding present on B but absent from synced intent survives apply untouched.
- **Occupied target.** A foreign file at the target yields `conflict`, is excluded by default, and
  is still byte-identical after an apply that did not select it.
- **Harness absent.** Intent naming an uninstalled harness yields `skip`, never an error.
- **Degradation.** A corrupt `bindings.json` / manifest yields an empty plan, not a 500.

---

## 8. Phase 2 — config-merge families

Two steps, in order, and only after Phase 1 has shipped and been used:

1. **Record intent.** Give `McpServerSpec`, `HookSpec` and `PermissionSpec` the same treatment
   skills got in Phase 0 — a per-harness set, written where bindings are applied, omitted when
   empty, total on read.
2. **Extend the planner.** Their conflict semantics differ: the unit is a key inside a shared
   config file, not a path. "Occupied" means the harness config already defines that server / hook
   / permission with different content. Resolve at key granularity and reuse each family's existing
   merge-and-render path rather than writing config files from the adopt module.

---

## 9. Open questions

- **Does intent belong to the store or to a profile?** Today it is one flat set per asset. A user
  with a work laptop and a personal desktop may want different bindings per machine from one
  synced store. Named profiles would answer that; they are out of scope here, and the current
  shape does not preclude adding them later.
- **Should apply offer to *remove* bindings absent from intent?** Deliberately no in Phase 1
  (§1). If it is ever added it must be a separate, separately-confirmed action with its own
  preview — never folded into the same button.
- **Marketplace-sourced assets whose store copy is missing.** Currently `skip`. Offering to
  re-fetch from source is a reasonable Phase 3, but it turns an offline-safe local operation into
  a network one, which is a different risk profile and needs its own opt-in.
