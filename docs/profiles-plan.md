# Plan — Work / Home profiles

**Status: unbuilt.** Written 2026-09-14 from a code read of `main` at `46c822b`; revised the
same day after a risk review (§2 S10–S11, §3.5.1, §3.8, §4.2 step 7, §9.3 ordering, §10, §11).

**Goal:** let the user switch this device between a **Work** and a **Home** profile, where a
profile is the set of assets that should be live in the harnesses while it is active. Every
asset belongs to Work, Home, or **both** — and "both" is one canonical asset in the store,
never a copy. Membership must be editable one asset at a time and in batch, from every family
page, and switching profiles must be previewable, idempotent, and reversible.

This document is written to be handed to an orchestrating agent. §9 is the delegation packet:
phases, branch discipline, definition of done, and validation. Everything before it is the
design those delegates must follow. Decisions marked **Settled** are not to be re-litigated by
a delegate; if one looks wrong, stop and escalate rather than build around it.

Read first: `docs/bootstrap-new-device.md` (its §9 asks exactly this question and its planner
and applier are reused here) and `docs/plan-auto-adoption.md` §2–§3 (the intent-versus-disk
vocabulary and the lock rules).

---

## 1. The model in one paragraph

Three facts, three homes:

| Fact | Example | Lives in | Synced across devices? |
|---|---|---|---|
| **Membership** — which profile(s) an asset belongs to | `skills:acme-deploy → [work]` | `<data_dir>/profiles.json` (new sidecar, same shape as `asset-tags.json`) | Yes |
| **Intent** — which harnesses an asset should be bound to *when its profile is active* | `enabledHarnesses`, `bindings.json`, `sync-state.json` | Existing per-family stores, **unchanged** | Yes |
| **Active profile** — which profile this device is in | `{"active": "home"}` | `<state_dir>/profile.json` (new, device-local like `bootstrap_dismissal.json`) | **No** |

Desired on-disk state on a device is the intersection: **an asset's intent is applied only if
the asset is a member of the device's active profile.** Switching profiles recomputes that
intersection and diffs it against disk. Nothing else changes meaning.

Consequences worth stating explicitly:

- **"Both" is not a copy.** Membership is a sidecar attribute on the single store asset,
  exactly like a tag. There is one `SKILL.md`, one agent file, one MCP spec. Only the sidecar
  entry says which profiles it applies in.
- **Intent survives a profile switch.** Suspending an asset (because its profile went inactive)
  removes its bindings from disk but leaves `enabledHarnesses` / the agent ledger / the slash
  sync record intact, so the next switch back knows where to put it. This is the crux of the
  design; see §3.
- **Two devices can be in different profiles at once** without fighting over the synced store,
  because the only per-device fact is not synced. A work laptop at Work and a desktop at Home
  share one `.harnessAM` and each applies its own slice.
- **The default is a no-op.** An asset with no sidecar entry is in both profiles, and a device
  with no `profile.json` is in Work. A user who never touches the feature sees no change to any
  harness file. There is no migration step.

---

## 2. Settled decisions

Each of these was weighed against at least one alternative. The alternative is named so a
delegate does not rediscover it and think it is new.

**S1 — Membership is its own sidecar, not a reserved tag.** Tags are free-form, case-folded,
and inert; membership has side effects on harness files and a fixed vocabulary. Storing it as
`profile:work` tags would let a bulk-tag edit silently unbind assets and would put profile
chips in the tag filter bar. Reuse the *store pattern* (`AssetTagStore`: `<family>:<ref>` keys,
total reads, atomic locked writes, unknown keys preserved) in a new `ProfileMembershipStore`;
do not reuse the store instance.

**S2 — The active profile is device-local.** It goes under `state_dir`, never `data_dir`, for
the same reason `BootstrapDismissalStore` does: a synced "active profile" would flip every
other device the moment one changes. A user with one device gets no downside.

**S3 — Switching is a real mutation with a preview, not a view filter.** The point of the
feature is that `~/.claude`, `~/.codex` and friends contain only the Work assets at work. A
filter-only "profile" would leave every asset bound everywhere and merely hide rows. The switch
therefore produces a plan (§4), shows it, and applies it — the same shape as bootstrap.

**S4 — Suspend keeps intent; the normal disable path clears it.** Today every `disable_*`
records `bound=False` and every `_disable` on agents calls `ledger.forget`. A profile switch
must *not* go through those, or the second switch back has nothing to restore. Each family gets
a suspend primitive (§3) that unbinds on disk without touching recorded intent. The
alternative — snapshot intent into `profiles.json`, disable normally, restore later — was
rejected: it couples devices (device B's switch rewrites the intent device A relies on) and
turns one synced fact into two that can disagree.

**S5 — Enabling an inactive asset on a harness auto-extends its membership.** If the user
toggles asset X onto Claude while X is Home-only and the device is at Work, the toggle succeeds
(disk truth always wins, and a bookkeeping rule must never refuse a direct action) and X's
membership becomes `[work, home]`, with a toast saying so. The alternative — refuse with a 409 —
was rejected because it makes the matrix lie about what is clickable. Disabling an inactive
asset is a no-op on disk and does not touch membership. **Confirmed by the user 2026-09-14:**
frictionless is the preference; a user who did not want the extension permanently undoes it
from the row badge, which is one click.

**S6 — Exactly two profiles, fixed ids `work` and `home`, in v1.** The store format is a list of
profile ids per asset so a third profile is a data change later, but every UI control is a
two- or three-state segmented control, not a list editor. Do not build profile CRUD.

**S7 — Naming: HAM "Profiles" are not Hermes "Profiles".** The codebase already uses "profile"
for a Hermes Bot's `HERMES_HOME` (`hermes_profile.py`, `hermes_profiles.py`, `hermes:<profile>`
binding targets, `harness-scope-missing`). In code, the new module is `application/profiles/`
and Hermes code keeps its `hermes_` prefix — no collision. In **user-visible copy**, a Hermes
profile is a **Bot** (README already says "Bots (Profiles)"); any UI string that currently says
"profile" for a Hermes target is renamed to "Bot" in Phase 3 so the word means one thing on
screen.

**S8 — Absent means both.** The sidecar stores an entry only when membership is narrower than
both profiles. Writing `[work, home]` deletes the key. This keeps the file small, makes the
default self-evident when someone opens the JSON, and means the bootstrap gate (§4.4) has no
special case for old stores. **Confirmed by the user 2026-09-14** together with "a device
with no `profile.json` is at Work".

**S9 — Reuse the bootstrap planner and applier for the bind side.** They already know how to
turn intent into `link` / `skip` / `conflict` for all six families, re-check disk before
writing, aggregate failures, and audit. The profile switch adds an *unlink* side and composes
the two. Do not write a second "bind everything in intent" loop.

**S10 — One harness set per asset, regardless of profile.** An asset's intent ("Claude and
Codex") is the same in Work and Home; profiles only decide *whether* it applies. "This skill
on Claude at work but on Codex at home" is explicitly not wanted (**user decision
2026-09-14**), so no per-profile intent key is to be added to any store, now or as a
"cheap" follow-up. Anyone who needs it writes a new plan.

**S11 — An agent carries its skills.** `AgentMutationService._enable` calls
`auto_enable_skills_for_agent` (`agents/mutations.py:465`), so linking an agent links its
referenced skills on that harness. A Work agent that references a Home-only skill would
therefore pull that skill into Work on every switch, and S5 would then silently widen the
skill to Both. Rule: **assigning membership to an agent extends its referenced skills'
membership to cover the agent's**, done in the membership service and reported in the
response (`implied: [{family, ref, profiles}]`) so the UI can say "also applies to 2 skills".
Narrowing a skill below an agent that references it is allowed but the response carries a
`warnings` entry naming the agent; the next switch will widen it back, which is the honest
outcome of S5, not a bug.

---

## 3. Backend: the domain layer

New package `harness_asset_manager/application/profiles/`.

### 3.1 Constants and identity

```python
PROFILE_IDS: tuple[str, ...] = ("work", "home")
PROFILE_LABELS = {"work": "Work", "home": "Home"}
DEFAULT_ACTIVE_PROFILE = "work"
Membership = tuple[str, ...]   # sorted, deduped, subset of PROFILE_IDS; () means "both"
```

Asset keys are `<family>:<ref>` using the **same ref the tag service uses** for that family:
`skill_ref` for skills, agent `ref`/slug, MCP server `name`, hook `id`, permission `id`, slash
command `name`. Skills are the one family whose *intent* is keyed differently (`package_dir` in
the manifest, see `skills/mutations.py:_record_binding`); the desired-state function (§3.4)
resolves that through the inventory entry, never by string surgery.

### 3.2 `ProfileMembershipStore` — `<data_dir>/profiles.json`

Copy the four invariants of `AssetTagStore` verbatim, including the docstring intent:

1. Keys are `<family>:<ref>`; no device-local paths.
2. Total reads: absent / truncated / corrupt → empty map, never raises.
3. Atomic writes under `file_lock(path.with_suffix(".lock"))`, unknown top-level keys preserved.
4. Empty or full membership removes the key (S8).

```jsonc
{
  "version": 1,
  "membership": {
    "skills:acme-deploy": ["work"],
    "mcp:home-assistant": ["home"]
  }
}
```

Add `profiles_path=data_dir / "profiles.json"` to `AppPaths` and to the `MutationPathTracker`
path lists in `container.py` alongside `asset_tags_path`, so the audit journal sees the file
change like it sees tag changes.

`ProfileMembershipService` mirrors `AssetTagService`: `get(family, ref)`, `get_for_family(family)`,
`set(family, ref, membership)`, `set_many(items)` (one lock, one write), `delete_for_ref`.
Validation: unknown profile id → `MutationError(status=400, code="invalid_profile")`.

**Cleanup on delete.** Wherever a family deletes an asset, call `delete_for_ref`. Today only
permissions cleans its tags on delete (`permissions/mutations.py:113`); the other families leak
tag entries. Fix that gap for profiles in every family, and fix it for tags at the same call
sites — it is the same one-line change and leaving it half-done is worse than either state.

### 3.3 `ActiveProfileStore` — `<state_dir>/profile.json`

Modelled on `BootstrapDismissalStore`: `active() -> str` (absent/corrupt → `"work"`),
`set_active(profile_id)`. Add `active_profile_path=state_dir / "profile.json"` to `AppPaths`.

### 3.4 Desired state — one pure function

```python
@dataclass(frozen=True)
class DesiredBinding:
    family: str
    ref: str            # tag/profile ref
    intent_ref: str     # the ref the family's intent store uses (package_dir for skills)
    display_name: str
    harness: str        # binding target id, may be scoped ("hermes:<bot>")

def desired_bindings(container, *, active_profile: str) -> tuple[DesiredBinding, ...]
```

Enumerates recorded intent for all six families (the same six sources `BootstrapPlanner`
reads today) and keeps a binding iff the asset's membership is `()` or contains
`active_profile`. This is the *only* place membership and intent are combined. The switch
planner, the bootstrap gate, and the read-model "inactive" flag all call it; if they ever
disagree, one of them stopped calling it.

Also expose `is_active(family, ref, active_profile) -> bool` for the presenters.

### 3.5 Suspend primitives — one per family, no intent write

Add a keyword to each family's existing bulk-disable path rather than a parallel method, so the
adapter calls and error aggregation stay shared:

| Family | Existing method | Change |
|---|---|---|
| Skills | `set_skill_all_harnesses(ref, "disabled")` | add `*, record_intent: bool = True`; when `False`, skip `_record_binding` |
| Agents | `set_harnesses(slug, [])` → `_disable` | add `*, keep_ledger: bool = False` threaded to `_disable`; when `True`, call `adapter.disable` but not `ledger.forget` |
| MCP | `set_server_all_harnesses(name, "disabled")` | `record_intent` kwarg, same as skills |
| Hooks | `set_hook_all_harnesses(id, "disabled")` | same |
| Permissions | `set_permission_all_harnesses(id, "disabled")` | same |
| Slash commands | `executor.remove_tracked_outputs(records, targets)` | new `keep_records: bool` — unlink the files, do **not** drop the sync-state records |

Each mutation service then gets `suspend(ref) -> dict` that calls its path with intent
recording off and returns the same `{ok, succeeded, failed}` shape as the bulk methods.

**Verify, per family, that a suspended asset is quiet.** Recorded intent with no file on disk
must produce zero drift, zero review rows, and zero auto-repair. Verified by code read for the
three that matter most — agent reconcile skips a missing `binding_path`
(`agents/reconcile.py:99-103`), slash drift repair skips `not path.is_file()`
(`slash_commands/auto_adopt.py:138`), and config auto-adopt only promotes *unmanaged* sightings —
but the delegate must **write the test for all six** (§8) rather than trust this paragraph. The
slash-commands review resolver "surfaces orphaned tracked records" per its own comment; confirm
a record-with-missing-file is not one of those, and if it is, gate that row on `is_active`.

#### 3.5.1 The audit that comes before any code

This is the biggest risk in the plan, so it gets the first deliverable of Phase 0: a written
table, verified by reading the code, of **every subsystem that compares recorded intent with
disk**, what it does today when intent is recorded and the file is absent, and what it must do
for a *suspended* asset. Fill in every cell; "n/a" needs a one-line reason.

| Subsystem | Skills | Agents | Slash | MCP | Hooks | Permissions | Required for suspended |
|---|---|---|---|---|---|---|---|
| Inventory / list presentation (drift, review rows) | | | | | | | shows as inactive, never as drifted or needs-review |
| Reconcile-on-read / auto-repair (`*_auto_adopt`, `agents/reconcile.py`) | | | | | | | writes nothing; `_enable_defaults` must skip inactive slugs |
| Bootstrap planner | | | | | | | `skip` / `inactive-in-profile` |
| `harnessam refresh --sync-all` | | | | | | | writes nothing |
| Detail-view actions (`canEnable`, `canDelete`, …) | | | | | | | enable allowed (S5); delete allowed |
| Cross-family side effects (agent → skills, S11) | | | | | | | gated by the agent's membership |

Three of the cells are already known from this code read: agent reconcile skips a missing
`binding_path` (`agents/reconcile.py:99`), slash drift repair skips `not path.is_file()`
(`slash_commands/auto_adopt.py:138`), and config auto-adopt only promotes *unmanaged*
sightings. One is already known to need a gate: `_enable_defaults` in agent reconcile enables
an agent on configured default harnesses that lack a ledger record, and a suspended agent with
a partial ledger would qualify. The rest are unknown until the table is filled.

**What the agent ledger means after this change — unchanged.** A record still means "HAM once
bound this here, against this content". What is new is that *record + no file* now has two
readings, and the reading is decided by `is_active`: active → something removed our binding,
which is what bootstrap and reconcile exist to notice; inactive → we removed it ourselves, on
purpose. That one predicate is the whole distinction; no second marker is needed, and none
should be added to the ledger.

**The leak test is the gate for Phase 0.** `tests/integration/test_profiles_leak.py`: build a
store with one Work-only asset per family bound on every installed harness; switch to Home;
then hammer every path that can write a binding automatically — every family's list and detail
endpoint (reconcile-on-read), `refresh --sync-all`, the bootstrap plan, a create of an agent
that references a Work-only skill — and assert, on the **filesystem**, that no Work-only asset
is bound anywhere. If this test cannot be made to pass for a family with a presentation gate
and the reconcile gate above, stop and escalate (§9.5); do not start Phase 1.

### 3.6 Read-model surface

Every family's list and detail payload gains two fields next to `tags`, threaded through the
same presenter parameters `tags` uses (`skills/presenters.py:20-54` is the template):

```jsonc
"profiles": ["work"],          // [] means both — same convention as the store
"activeInProfile": false       // is_active(family, ref, active_profile)
```

Read the membership map once per family payload (`get_for_family`), exactly as tags are read
once, not per row.

### 3.7 Auto-extend on enable (S5)

In each family's single-harness `enable_*` (and `set_*_all_harnesses(..., "enabled")`), after a
successful bind: if the asset is not active in the current profile, add the active profile to
its membership and include `"membershipExtended": "work"` in the response so the UI can toast.
Do this in the mutation service, not the router, so the CLI gets it too.

### 3.8 Refactor direction for the planner

`BootstrapPlanner` is ~1200 lines because each `_plan_<family>` enumerates that family's intent
inline and then classifies it against disk. `desired_bindings` (§3.4) *is* that enumeration.
So the refactor is subtractive: each `_plan_<family>` becomes "for each `DesiredBinding` of
this family, classify against disk", and the membership gate (§4.4) falls out for free because
the planner never sees a binding that is not desired. Land this as its own commit in Phase 0
with the existing `test_bootstrap_planner.py` unchanged and green before the profile logic is
added on top — that is the proof the enumeration was extracted faithfully.

---

## 4. Backend: switching

### 4.1 Plan

```python
SwitchAction = Literal["unlink", "link", "skip", "conflict"]

@dataclass(frozen=True)
class ProfileSwitchPlan:
    from_profile: str
    to_profile: str
    unlink: tuple[BootstrapAction, ...]   # live on disk, not desired in `to`
    link:   tuple[BootstrapAction, ...]   # desired in `to`, not on disk  (from BootstrapPlanner)
    conflicts: tuple[BootstrapAction, ...]
    skipped: tuple[BootstrapAction, ...]
```

`ProfileSwitchPlanner.plan(to_profile)`:

1. `D_to = desired_bindings(active_profile=to_profile)`.
2. **Link side:** run `BootstrapPlanner` restricted to `D_to` (§4.4 makes the planner accept a
   membership predicate). Its `link` / `conflict` / `skip` carry over unchanged, including
   `harness-scope-missing`.
3. **Unlink side:** for every binding currently live on disk that HAM manages (the families'
   own inventories already know this — `has_binding`, the agent ledger + symlink check, MCP/hook/
   permission "managed" state, slash sync records with an existing file) and that is *not* in
   `D_to`, emit an `unlink` action. Reuse `BootstrapAction` with `action="unlink"` — extend the
   `Action` literal rather than inventing a second dataclass.
4. Sort like bootstrap does: `(family, ref, harness)`.

Pure with respect to mutation, like `BootstrapPlanner`. Cheap enough to run on every open of
the switch sheet.

**Idempotence test (mandatory):** plan → apply → plan again must be empty. Plan for the
*current* profile must be empty on a device whose disk matches intent.

### 4.2 Apply

`ProfileSwitchApplier.apply(plan, *, selected_keys, allow_conflicts)`:

1. Take `<state_dir>/profile-switch.lock` via `file_lock`. Never hold the agent ledger lock or
   the audit lock across this (`plan-auto-adoption.md` §2 amendment — `flock` re-entry
   deadlocks in one process).
2. **Unlink first, then link.** Order matters for renders families (a Codex agent file, a
   rendered slash command) where an unlink and a link can target the same path.
3. Unlink via the §3.5 suspend primitives; link via `BootstrapApplier.apply` (which re-checks
   disk immediately before each write). Per-action failures aggregate; one bad asset does not
   strand the rest.
4. `ActiveProfileStore.set_active(to)` **after** the apply loop, even if some actions failed —
   the device *is* now in the new profile; the failures are reported and "Reapply" (§4.3) is the
   retry path. Rationale: if the active profile were left at `from`, the UI would show Work
   while half the disk is Home, which is the worse lie.
5. `invalidation.invalidate_all()` once at the end.
6. One `MutationAuditJournal` entry per action via a `record_profile_switch(...)` helper
   modelled on `applier.py:record_bootstrap`, with `from`, `to`, `action`, `outcome`.

7. **Verify after apply.** Re-run `plan(to)`; the count of remaining `link` + `unlink` actions
   is the **pending** count. Return it. A switch with failures is therefore never reported as
   clean, and the UI never shows "Home" without "· 2 pending" next to it.

Returns per-action results in the `BootstrapApplyResult` shape, the new active profile, and
`pending`.

### 4.3 Reapply

`plan(active_profile)` + `apply` with the current profile as both `from` and `to`. This is the
repair action for a device whose disk drifted from its profile (a failed switch, a store synced
in from another machine, a harness wiped). It is the same code path, so it needs no separate
tests beyond "reapply on a clean device is a no-op".

`GET /api/profiles` carries `pending` (the reapply plan's action count) so the switcher can
show a warning dot and a **Reapply** affordance whenever disk and profile disagree. This is
derived state computed on read, like the bootstrap banner — never a flag that can go stale.

### 4.4 Gate the bootstrap planner

`BootstrapPlanner.plan()` must only plan assets active in this device's profile; otherwise the
new-device banner on a Home machine offers to link every Work asset. Add a
`membership_predicate` (default: `is_active(..., ActiveProfileStore.active())`) and emit
`skip` / `inactive-in-profile` for the rest, so the review sheet can still show them greyed if
it wants to. `BootstrapPlanner.from_container` wires the default; `ProfileSwitchPlanner` passes
its own predicate for `to_profile`.

---

## 5. API

New router `api/routers/profiles.py`, registered in `api/app.py` after `bootstrap`.

| Method | Path | Body / query | Returns |
|---|---|---|---|
| `GET` | `/api/profiles` | — | `{ profiles: [{id, label}], active, pending, counts: { work, home, both } }` |
| `GET` | `/api/profiles/switch-plan` | `?to=home` | `ProfileSwitchPlanResponse` (the §4.1 plan, DTO shape mirrors `BootstrapPlanResponse` with `unlink` added) |
| `POST` | `/api/profiles/switch` | `{ to, actions: [...], allowConflicts }` | `ProfileSwitchApplyResponse` (per-action results + `active`) |
| `POST` | `/api/profiles/reapply` | `{ actions: [...] }` | same |
| `PUT` | `/api/profiles/membership` | `{ items: [{ family, ref, profiles }] }` | `{ ok, results: [{ family, ref, profiles, error? }], implied: [...], warnings: [...] }` (S11) |

`PUT /membership` is deliberately **batch-first**: one request for one asset or a hundred,
applied under one lock with one write and aggregated per-item errors. Bulk tagging today loops
N client-side requests (`use-skills-workspace-controller.ts:484-516`); do not copy that here —
a profile change on forty assets must not be forty partial writes.

Schemas go in `api/schemas/profiles.py`; `npm run codegen:openapi` is mandatory after every
schema change and `npm run codegen:check` is a CI gate.

Per-family list/detail responses gain `profiles` and `activeInProfile` (§3.6) — that is six
schema files, and `generated.ts` must be regenerated after each.

---

## 6. CLI

New group `harnessam profile` (`cli/commands/profile.py`, added to `GROUP_NAMES` — see the
`normalize_argv` note in `cli/commands/__init__.py`; forgetting this parses
`harnessam profile show` as `serve profile show`).

```
harnessam profile show                          # active profile + counts
harnessam profile switch home --dry-run         # print the plan, change nothing
harnessam profile switch home                   # interactive confirm, then apply
harnessam profile switch home --yes [--json]    # non-interactive, for scripts
harnessam profile reapply [--yes] [--json]
harnessam profile set <family> <ref> --work|--home|--both
harnessam profile set <family> --all --work     # every asset in the family
```

The headless form is not optional: the same dotfiles bootstrap script that runs
`harnessam bootstrap --yes` on a new machine will want `harnessam profile switch work --yes`
right after it. Mirror `cli/commands/bootstrap.py` for the confirm / `--yes` / `--json` shape.

---

## 7. Frontend

### 7.1 One control, three placements

`components/profiles/ProfileMembershipControl.tsx` — a segmented control with three options
in this order: **Work · Both · Home**. "Both" sits in the middle so the control reads as a
spectrum, and it is the default so it is what an untouched asset shows. It is used unchanged in:

1. **Detail view** of every family (next to the tag editor).
2. **Matrix row** — a compact badge (`ui-status-badge`, mono caps) reading `WORK` or `HOME`
   only when membership is narrower than both; a Both row shows nothing, because Both is the
   default and default state should be quiet. Clicking the badge (or an empty affordance on
   hover for Both rows) opens a popover containing the control.
3. **Bulk action bar** — a `BulkProfilePopover` beside `BulkTagPopover`, same trigger style,
   containing the control and an **Apply** button. Applying calls `PUT /membership` once with
   every selected ref.

Rows that are **inactive in the current profile** (`activeInProfile === false`) get
`data-profile-inactive="true"`: text at `--color-text-muted`, harness cells rendered with the
existing unavailable treatment (`grayscale()` + opacity, per DESIGN.md "Harness marks"), and the
badge reads `HOME · INACTIVE`. Cells stay clickable (S5); the click enables and the toast reads
"Enabled on Claude and added to Work".

### 7.2 Profile filter

Every family page adds a `?profile=work|home|both|inactive` URL param beside `?tag=`, rendered
as a pill group in `FilterBar.pills` next to the status pills: **All · Work · Home · Both ·
Inactive here**. This is what makes batch assignment tractable: filter to *Both*, select all,
set *Work*. Counts on the pills come from the list payload, computed the way
`extractAssetTagCounts` does it.

### 7.3 Bulk coverage gap

`BulkActionBar` is mounted on Skills, MCP, Permissions, and Agents. **Hooks and Slash
Commands have row checkboxes and a select-all header (`94518d5`) but no bar.** Mount the bar on
both with `showHarnessActions={false}` and `showDestructiveAction={false}` if their existing
bulk semantics are not ready, and wire `onProfileSelected` and `onTagSelected`. Six families
must be batch-assignable or the feature has a hole exactly where the user will look.

### 7.4 The switcher

In `Sidebar.tsx`'s footer, above **Refresh**, a two-state segmented control labelled by a caps
micro-label:

```
PROFILE
┌──────────┬──────────┐
│ ● Work   │   Home   │      ← active option filled with --color-accent, like a pill-group pill
└──────────┴──────────┘
↻ Refresh
☾ Dark
⚙ Settings
```

Clicking the inactive side fetches `GET /switch-plan?to=…`. If the plan has zero `unlink` and
zero `link` and zero `conflict` actions, switch immediately (`POST /switch` with no actions)
and toast "Switched to Home — nothing to change". Otherwise open the review sheet.

When `pending > 0` the active segment shows a small `--color-warning` dot and its tooltip
reads "2 changes pending — Reapply"; clicking the *active* segment then opens the review sheet
in reapply mode. Below the sheet's title, one muted line: "Running harness sessions pick up
changes on their next start." — HAM cannot restart Claude Code or Cursor, and users will
otherwise report a switch as "not working".

### 7.5 The review sheet

Generalise `BootstrapReviewSheet` into `components/PlanReviewSheet` that takes grouped actions
and an apply callback; `BootstrapReviewSheet` becomes a thin wrapper. The profile variant:

```
Switch to Home?
Changes what is linked into your harnesses on this device. Nothing is deleted from the store.

UNLINK — 4 assets are Work-only            LINK — 3 assets are Home-only
  Skills                                     Skills
  ☑ acme-deploy        claude · codex         ☑ recipes            claude
  ☑ jira-triage        claude                Agents
  MCP servers                                ☑ home-assistant     claude · agy
  ☑ acme-db            claude · cursor       ⚠ 1 conflict — unchecked, see below
  Agents
  ☑ pr-reviewer        claude

                                   [Cancel]   [Switch to Home]
```

Two columns, unlink on the left, link on the right, each grouped by family with the existing
`FAMILY_LABELS`. All `link` and `unlink` rows are checked by default; `conflict` rows are
unchecked and listed last with their `detail` text, exactly as bootstrap does. After apply,
each row shows its result inline; failures keep the sheet open with a **Reapply** button.

Copy rule: the sheet never uses the word "delete". Unlinking removes a symlink or a config key;
the asset stays in the store. Say "unlink".

### 7.6 State and invalidation

- `features/profiles/` with `api/client.ts`, `queries.ts` (`profileKeys`, `useProfilesQuery`,
  `useSwitchPlanQuery(to)`, `useSwitchMutation`, `useSetMembershipMutation`), `types.ts` from
  `generated.ts`, and `public.ts` exporting `invalidateProfileQueries`.
- After a switch or reapply: `invalidateCapabilityQueries` (everything) — the switch touched
  every family.
- After a membership change: invalidate that family's queries plus `profileKeys.all` (counts).
- Add `invalidateProfileQueries` to `capability-registry/invalidation.ts`.

### 7.7 Overview

One line in the Overview header area: "Profile: **Work** · 6 assets inactive on this device",
linking to `?profile=inactive` on the busiest family. Nothing more; the overview is already
dense and the switcher is one glance away in the sidebar.

### 7.8 Copy

All strings go through the i18n modules (`i18n/common.ts` for shared: `profile.work`,
`profile.home`, `profile.both`, `profile.switchTo(label)`, `profile.inactiveHere`, …). No
literal strings in components, matching the rest of the app. Tokens only in CSS; the new
`styles/components/profiles.css` uses `--color-accent` for the active segment and
`--color-text-muted` for inactive rows — a raw hex in that file is a bug (DESIGN.md).

---

## 8. Testing

Follow `tests/README.md` layering. Named tests are the definition of done for the phase that
owns them.

**Unit (`tests/unit/test_profiles_*.py`):**

- `ProfileMembershipStore`: total reads on absent / truncated / non-object JSON; `[]` and full
  membership delete the key; unknown top-level keys survive a write; invalid profile id → 400.
- `ActiveProfileStore`: absent → `work`; corrupt → `work`; round-trip.
- `desired_bindings`: Work-only asset excluded at Home; Both included in both; skill
  `package_dir` ↔ `skill_ref` resolved; scoped `hermes:<bot>` targets carried through untouched.
- `ProfileSwitchPlanner` decision table: for each of six families, one asset in each of
  {work, home, both} × device in {work, home} × disk in {bound, unbound} → expected action.
- **Idempotence:** plan → apply → plan is empty; reapply on a clean device is empty.
- **Suspend keeps intent (×6):** after `suspend`, the family's intent store is byte-identical
  and disk has no binding; after the reverse switch, disk is bound again with no user input.
- **Suspended is quiet (×6):** with intent recorded and no file on disk, the family's inventory
  reports no drift, no review row, and the auto-adopt / reconcile pass writes nothing.
- **Auto-extend (S5):** enabling a Home-only asset at Work makes it `[work, home]` and the
  response carries `membershipExtended`.
- Unlink-before-link ordering on a renders family (Codex agent) where both target one path.
- **S11:** assigning a Work agent extends its Home-only skill to Both and reports `implied`;
  narrowing that skill reports a `warnings` entry naming the agent.
- **Reconcile gate:** an agent with a ledger record on Claude only, default harnesses
  `[claude, codex]`, suspended at Home — reconcile writes nothing.
- **Pending:** a switch with one injected failure returns `pending == 1`; reapply clears it.

**Integration — the leak test (`tests/integration/test_profiles_leak.py`, §3.5.1)** is the
Phase 0 gate and the single most important test in this plan.

**Integration (`tests/integration/test_profiles_routes.py`):** every endpoint in §5 against
`AppTestHarness`; batch membership with one invalid item reports that item and applies the
rest; per-family list payloads carry `profiles` and `activeInProfile`.

**Cross-device (`tests/unit/test_cross_device_arrival.py`):** extend the existing two-machine
fixture: device A at Work, device B at Home, one synced store with Work-only, Home-only and Both
assets. A's bootstrap plan contains only Work+Both; B's only Home+Both; neither device's switch
rewrites intent the other depends on.

**Frontend (beside the components):** `ProfileMembershipControl` three states and keyboard;
`BulkProfilePopover` sends one request with all selected refs; sidebar switcher opens the sheet
when the plan is non-empty and switches directly when it is empty; inactive row rendering; the
`?profile=` filter; Hooks and Slash Commands bulk bars mount.

**Pressure script:** `scripts/pressure_test_profiles.py`, in the style of
`pressure_test_asset_tags.py` / `pressure_test_agent_create.py`: drives `AppTestHarness` through
assign → switch → switch back → reapply and asserts on the **files and symlinks actually
written**, not response bodies.

---

## 9. Delegation packet

### 9.1 Branch and merge discipline

- One short-lived branch per phase off `main`: `feat/profiles-0-domain`,
  `feat/profiles-1-switch-api`, `feat/profiles-2-ui`, `feat/profiles-3-docs`. Each merges back to
  `main` when its DoD is green and is deleted; the next phase branches from the merged `main`.
  Never a long-lived `feat/profiles` umbrella (CLAUDE.md branch strategy).
- Logical commits, pushed as work lands. No merge to `main` without the orchestrator running the
  full validation suite itself — do not relay a delegate's pass counts.
- Every phase ends with a `docs/handoff.md` entry (newest on top) recording what shipped, what
  was amended in this plan, and what the next phase should know. Amendments to this document are
  marked **AMENDED** inline, as `plan-auto-adoption.md` does.

### 9.2 Validation suite (run in full at the end of every phase)

```bash
npm run typecheck
bash scripts/test_backend.sh       # coverage gate: --fail-under=80
npm test
npm run build
npm run codegen:check              # any phase that touched an API schema
ruff check harness_asset_manager tests scripts
```

### 9.3 Phases

Phases 0 → 1 → 2 are sequential on the API contract. Phase 2 may start against a stub of the
§5 schemas committed at the end of Phase 1's first commit (the DTOs land before the logic), if
the orchestrator wants parallelism. Phase 3 can run alongside Phase 2.

**Minimum viable slice.** If it turns out Work and Home are two *machines* rather than one
machine in two contexts, the switcher is rarely used and nearly all of the value is in
membership plus the bootstrap gate: on the work laptop, bootstrap links only Work assets. The
phases below are ordered so that slice ships first — Phase 0, the membership half of Phase 1,
and the membership controls of Phase 2 can be merged and used before the switch exists.

**Phase 0 — domain and suspend primitives (backend only).**
First deliverable: the §3.5.1 audit table, filled in and committed to this document.
Second: the §3.8 planner refactor, its own commit, existing tests green.
Scope: §3 in full, plus `AppPaths`, container wiring, path-tracker registration, delete-cleanup
call sites (tags and profiles).
DoD: the audit table has no empty cell; the **leak test passes**; every §8 unit test named for
the store, active-profile store, `desired_bindings`, suspend-keeps-intent ×6,
suspended-is-quiet ×6, S11, the reconcile gate, and auto-extend passes; no API or UI change; the app
behaves identically for a user with no `profiles.json`.
Files: new `application/profiles/{__init__,store,active,service,desired}.py`; edits in
`paths.py`, `application/container.py`, each family's `mutations.py` (kwarg + `suspend`),
`slash_commands/executor.py`, each family's presenter/queries for `profiles` /
`activeInProfile`.

**Phase 1 — membership API and bootstrap gate, then switch planner, applier, API, CLI.**
Land `PUT /membership`, `GET /api/profiles`, `harnessam profile set`, and the bootstrap gate
as the first merge; the switch as the second. Scope: §4, §5, §6, bootstrap gate §4.4.
DoD: planner decision table, idempotence, ordering, and cross-device tests pass; all §5 routes
covered in integration; `harnessam profile switch --dry-run` and `--yes --json` work headless;
`npm run codegen:check` clean; new-device banner on a Home device lists no Work-only asset.
Files: new `application/profiles/{planner,applier}.py`, `api/routers/profiles.py`,
`api/schemas/profiles.py`, `cli/commands/profile.py`; edits in `bootstrap/planner.py`,
`bootstrap/models.py` (`Action` literal), `api/app.py`, `cli/commands/__init__.py`, six family
schema files, `frontend/src/api/{openapi.json,generated.ts}` regenerated.

**Phase 2 — UI.**
Membership control, row badge, filter, and bulk popover on all six pages first (one merge);
the switcher, pending dot, and review sheet second. Scope: §7 in full, including the Hooks and
Slash Commands bulk bars.
DoD: every §8 frontend test passes; `npm run lint:frontend` adds no new warnings; no raw
values in the new CSS; both themes checked by eye (light-mode contrast on the inactive row and
the active segment — `--color-text-muted` on `--color-surface` must still clear 4.5:1); the
inactive-cell click path shows the auto-extend toast; screenshots of the switcher, the sheet,
a matrix with inactive rows, and the bulk popover attached to the handoff entry.
Files: new `features/profiles/**`, `components/profiles/ProfileMembershipControl.tsx`,
`components/BulkProfilePopover.tsx`, `components/PlanReviewSheet.tsx`,
`styles/components/profiles.css`; edits in `Sidebar.tsx`, `BulkActionBar.tsx`, `FilterBar`
callers on all six pages, six detail views, six matrix views, `HooksInUsePage.tsx`,
`SlashCommandsPage.tsx`, `capability-registry/{invalidation,overview}.ts`, `i18n/common.ts`,
`bootstrap/components/BootstrapReviewSheet.tsx` (now a wrapper).

**Phase 3 — docs, copy, pressure test.**
Scope: README section "Profiles" (next to the tagging paragraph at `README.md:322`),
ARCHITECTURE.md storage layout (two new files, which dir each lives in and why),
`docs/bootstrap-new-device.md` §9 marked resolved with a pointer here, S7 copy rename of
user-visible Hermes "profile" → "Bot", `scripts/pressure_test_profiles.py`, final handoff entry.
DoD: pressure script passes on a fresh `--state-dir`; `grep -rn "profile" frontend/src --include=*.tsx`
shows no user-visible Hermes usage of the word; README table of CLI commands lists `profile`.

### 9.4 Things a delegate must not do

- Change what `disable_*` records. The normal disable path keeps clearing intent; only
  `suspend` preserves it. Mixing them breaks the drift subsystem's assumptions.
- Put the active profile, or anything device-specific, in `data_dir`.
- Write to a harness directory from the planner. Planners are pure; only appliers write.
- Hold the agent ledger lock or the audit lock across a switch.
- Add a fourth button style, a raw CSS value, or a component-local string.
- Invent profile CRUD, a third profile, per-profile *harness* intent, or a "new assets default
  to the active profile" setting. All are plausible follow-ups; none are in scope, and each
  would need its own plan.
- Loop N single-item membership requests from the client. The batch endpoint exists so that
  never happens.

### 9.5 Escalate instead of guessing when

- A family's inventory shows a suspended asset as drifted or needs-review and the fix is not
  a presentation gate (§3.5 last paragraph) — the intent model may need a `suspended` marker,
  which is a design change to §1.
- `BootstrapPlanner` cannot accept a membership predicate without reshaping its per-family
  methods — that refactor is fine but should be its own commit and be called out.
- Light-theme contrast for the inactive row cannot be met with existing tokens — a new token
  is a DESIGN.md change, not a local override.
- The leak test fails for a family after the presentation and reconcile gates are in place.
  The fallback design is the rejected S4 alternative (snapshot intent into `profiles.json` and
  use the normal disable path), which removes this risk class entirely at the cost of
  multi-device coupling. That trade is the user's to make, not the delegate's.

---

## 10. Things to back up and consider before committing to this shape

None of these block the plan; each could change its emphasis, and one could replace it.

- **One machine or two?** The plan supports both, but they want different products. One
  machine in two contexts needs the switcher and the review sheet. Two machines need membership
  and the bootstrap gate, and the switcher becomes a rarely used repair tool. Decide which is
  the real case and let §9.3's ordering follow from it.
- **Is the boundary really "time", or is it "which repo"?** Most harnesses support
  project-level config (`.claude/` in a repository, `.cursor/rules`, project-scoped MCP). If Work
  assets are only wanted inside work repositories, project-scoped bindings would make the
  context follow the directory with no switching at all. HAM manages user-level state only
  today, so that is a different and larger feature — but it is the one that makes a profile
  toggle unnecessary rather than merely convenient. Worth being sure a global toggle is what is
  wanted before building it.
- **Secrets travel with the store.** Work MCP servers carry credentials in their spec, and
  `.harnessAM` syncs both profiles' assets together. Profiles change what is *bound*, not what is
  *stored*, so a store dotfiled to a personal repository still carries work secrets. This plan
  does not change that, but the word "profile" will make some users assume it does. The README
  section in Phase 3 must say so in one sentence.
- **Narrowing a permission or hook is a safety change.** A denylist that is Home-only stops
  applying at Work. That is the feature working, but it is the one family where "less bound"
  can mean "less protected". Consider a one-line warning in the membership popover for those
  two families; not built by default.
- **Automatic switching** (by hostname, network, calendar) is out of scope, but
  `harnessam profile switch <id> --yes` is designed so a cron, launchd job, or shell hook can
  do it without any further product work.

### Out of scope, recorded so they are not rediscovered

- **Per-profile harness intent.** Today intent is one set per asset; a user might want a
  skill on Claude at work but on Codex at home. The store shape here does not preclude keying
  intent by profile later, but it doubles every family's intent record and is a separate plan.
- **Profile-scoped Configs.** The Configs family (harness settings files) is not an asset with
  bindings and is untouched here. Whether a profile should also swap `settings.json` variants is
  a different feature with a different risk profile (it rewrites files HAM does not own outright).
- **A full-width banner at app start** when disk does not match the profile. The pending dot
  on the switcher (§7.4) covers the need with less chrome; promote it to a banner only if users
  miss the dot.

---

## 11. The no-development alternative, and why it is worth running first

Everything the switch does can be approximated today with existing surfaces, and doing so for
a couple of weeks would answer §10's first two questions with evidence instead of guesses.

**Pattern: tags plus a script.** Tag assets `work` or `home` in the UI (untagged means both;
Skills, MCP, and Permissions already have bulk tagging, the other three families tag one asset
at a time). A shell script `ham-profile` does the switch through the CLI:

1. `harnessam <family> list --json` for each family; partition by tag.
2. For every asset tagged only with the *outgoing* profile, record its currently enabled
   harnesses into a file the script owns (`~/.harnessam/profile-intent.json`), then disable it on
   each with the family's existing `--disable` command.
3. For every asset tagged only with the *incoming* profile, enable it on the harnesses the script
   recorded last time (or on the auto-adopt defaults the first time).
4. Write the active profile into the same file.

This is the rejected S4 alternative in shell form, and for a script that is the *right* choice:
it uses the normal disable path, so nothing in HAM is ever in the unfamiliar "intent recorded,
file absent" state, and the entire §3.5.1 risk class does not exist. What it lacks is the
preview, the atomicity, the pending indicator, the S11 agent-to-skill rule, and bulk assignment
on Hooks, Slash Commands, and Agents. It also cannot gate the bootstrap banner on a second
machine.

**Pattern: symlink-swap the harness directories.** For the placement families only, make
`~/.claude/skills`, `~/.claude/agents`, `~/.claude/commands` (and the equivalents for each
harness) symlinks into `~/.harness-profiles/<profile>/…`, and switch by re-pointing the symlinks.
Instant, zero product code, and HAM keeps working because it scans through the link. But an
asset wanted in both profiles must be enabled twice, once per directory set, so "both" is not
canonical — and MCP servers, hooks, and permissions live inside each harness's own settings file
and cannot be split this way. It solves half the problem well and the other half not at all.

**Recommendation.** Run the tags-plus-script pattern for two weeks before starting Phase 0. If
the script is invoked daily, the one-machine case is real and the full plan is justified. If it
is invoked once per machine and forgotten, ship the minimum viable slice (§9.3) and stop. If
what actually gets tagged is "this repo's stuff", back up to §10's second bullet before building
anything.
