# Plan — Attaching Skills to Agents from the Skills page

**Status: unbuilt.** Written 2026-09-16 from a code read of `main` at `4c4a79f`.

**Goal:** from the Skills family page, select many skills at once and attach them to (or detach
them from) one or more adopted agents in a single action, and filter the Skills matrix down to
the skills a given agent carries. The relation stays many-to-many and keeps exactly one source
of truth.

This document is written to be handed to a delegate. §8 is the delegation packet: phases, branch
discipline, definition of done, and validation. Everything before it is the design the delegate
must follow. Decisions marked **Settled** in §2 are not to be re-litigated; if one looks wrong,
stop and escalate rather than build around it.

Read first: `docs/profiles-plan.md` §2 (S1 in particular — it settles the same tag question this
plan faced) and `docs/adding-a-family.md` for the family-page conventions this reuses.

---

## 1. The model in one paragraph

**The agent↔skill edge already exists and already has exactly one home: the `skills:` list in
the agent's own frontmatter.** It is parsed at `agents/parser.py:72`, carried on
`AgentDefinition.skills` (`agents/model.py:221`), and rendered back at `agents/parser.py:127`
and `:195`. It is a field the harness itself reads — not HAM bookkeeping. This plan therefore
adds **no new store and no new persisted fact**. It adds two things on top of what is already
written to disk:

1. A **derived reverse index** — `skill slug → [agents]` — computed from the agent store at read
   time and attached to the Skills page payload.
2. A **bulk write path** from the Skills page that funnels into the same agent mutation the
   agent detail editor already uses.

Nothing about how the relation is persisted changes. Delete the whole feature and the data is
still correct.

### What already exists (do not rebuild)

| Piece | Where | State |
|---|---|---|
| `skills:` frontmatter parse/render | `agents/parser.py:72`, `:127`, `:195` | Shipped |
| Slug validation against the managed skills inventory | `agents/mutations.py:278` `validate_skills` | Shipped |
| Auto-enable attached skills on the agent's harnesses | `agents/mutations.py:310` `auto_enable_skills_for_agent` | Shipped |
| Agent-side editor, one agent at a time | `frontend/.../detail/AgentSkillsFieldEditor.tsx` | Shipped |
| Skill-tag → bulk-attach shortcut, agent side | `deriveSkillTagOptions` in the same file | Shipped |
| Free-form skill tags + bulk tagging | `application/asset_tags/`, `components/BulkTagPopover.tsx` | Shipped |
| Skills page knows anything about agents | — | **Nothing. This is the gap.** |

---

## 2. Settled decisions

Each was weighed against a named alternative so a delegate does not rediscover it and think
it is new.

**S1 — Agents are not tags.** The original framing was "make each adopted agent a tag on the
Skills page". Rejected. An `agent:code-reviewer` entry in `asset-tags.json` would be a *second*
representation of a fact that already lives in the agent file, and the two drift the moment
anyone edits the agent through `AgentDetailContent`, hand-edits the file, or adopts an agent
that already carries `skills:`. Worse, tags are free-form and inert while this relation has
side effects on harness files (S5): a typo'd `agent:reviewr` would be a silent no-op, and
clearing a tag would silently unbind skills from disk. This is the same argument
`docs/profiles-plan.md` S1 already settled for profile membership, in the same store, for the
same reasons. Tags stay what they are: inert labels.

**S2 — The reverse index is derived, never stored.** `skill slug → [agents]` is computed on
each Skills page read by inverting the agent store's `skills:` lists. There is no
`skill-agents.json`, no migration, and no way for the index to disagree with the agent files.
The alternative — caching the inversion — buys nothing at this store size (§3.1) and
reintroduces exactly the drift S1 exists to prevent.

**S3 — Managed (adopted) agents only, in v1.** The reverse index and the bulk action cover
agents in HAM's own store (`AgentStore.scan()`), which is what "adopted by HarnessAM" means.
Unmanaged agents — files discovered in harness directories — are excluded because (a) reading
them means walking every installed harness's agent directory on every `GET /api/skills`, and
(b) `update_unmanaged` refuses rendered adapters (Codex TOML) outright, so a chunk of them
could not be written to anyway. A later version can add them; nothing here forecloses it.

**S4 — The read path must not reconcile.** `SkillsQueryService.list_skills` must reach agents
through a read-only seam. `AgentInventoryService.build()` runs the agent reconcile, which can
write. This is the exact mirror of a bug already fixed in the other direction — see the comment
at `agents/inventory.py:59`: *"Deliberately the read-only lookup, not `SkillsQueryService.inventory()`:
that one runs the skills reconcile, which can auto-adopt, so resolving a display name made
`GET /api/agents` able to write into the skills store."* Do not let `GET /api/skills` acquire
the power to write into the agents store. Use `AgentStore.scan()` (`agents/store.py:54`), which
is a pure read.

**S5 — The bulk write goes through the existing agent update path, not a new one.** Attaching a
skill to an agent must keep firing `validate_skills` and `auto_enable_skills_for_agent`, and must
keep landing in the mutation audit journal via the `AuditedMutationService` wrapper
(`container.py:617`). A second "write `skills:` directly" path would diverge from the agent
detail editor the first time either side changes. The new endpoint composes; it does not
reimplement.

**S6 — Attach is additive; detach is explicit and separate.** Applying agents to a selection
*adds* those agents to each selected skill and leaves every other attachment alone — mirroring
how `onMultiSelectTag` adds tags rather than replacing them. Removing is a distinct "Detach"
action in the same popover. The alternative — "set" semantics, where the popover's contents
become the complete agent list for every selected skill — is a foot-gun on a multi-row selection
where the rows start with different attachments.

**S7 — The bulk action previews its disk writes before applying.** Unlike bulk tagging, this
writes harness files: attaching 12 skills to an agent enabled on 3 harnesses creates up to 36
skill bindings via `auto_enable_skills_for_agent`. The user must see the count, and which
harnesses, before it happens. Reuse `ConfirmActionDialog`; it must state agent count, skill
count, and the number of new bindings the attach will create. Silent fire-and-forget, the way
`onTagSelected` works today, is not acceptable for a mutation with this blast radius.

**S8 — Only managed skills can be attached.** `validate_skills` (`agents/mutations.py:278`)
rejects any slug that is not `kind == "managed"` in the skills inventory, with
`code="invalid_skill"`. The UI must respect that up front: unmanaged rows in the selection are
skipped with a stated reason, not silently dropped and not allowed to fail the whole batch. The
Skills page already tracks this split — `multiSelectedRefs` versus `selectedUntrackedRefs` in
`SkillsWorkspacePage.tsx` — so the gate already exists; wire the new action to the managed set
only, the way `onTagSelected` is gated on `selectedManagedCount > 0` today.

**S9 — The agent filter is its own control, not a row in the tag filter bar.** Agent chips do
not go into `SkillTagFilterBar`. That bar is the tag vocabulary; mixing a second, differently
behaved facet into it is how the page stops teaching what a tag is. Add a sibling control with
its own URL param (`?agent=`, repeatable, OR within agents — matching how `?tag=` already works
at `SkillsWorkspacePage.tsx:99`).

**S10 — Partial failure reports; it never aborts mid-way.** One agent failing to write (a parse
error, a Hermes profile failure) must not roll back the others or abandon the remaining work.
The endpoint returns per-agent and per-binding outcomes, and the UI surfaces them the way
`formatMultiSkillFailureMessage` already does for bulk harness toggles. There is no transaction
across agent files and there will not be one.

**S11 — Naming: "Agents", never "tag".** The bulk control is labelled **Attach to agents**, the
row affordance is an **Agents** chip group, and the filter is **Agent**. "Tag" is already on the
same page meaning "inert label"; reusing the word for something that writes harness files would
make the page teach the wrong thing.

---

## 3. Backend design

### 3.1 The reverse index

New, small, and pure — put it next to the agents application code since it is derived from agent
data:

```python
# harness_asset_manager/application/agents/attachments.py

def skill_attachments(store: AgentStore) -> dict[str, tuple[AgentAttachment, ...]]:
    """slug -> the managed agents whose `skills:` list names it.

    A read-only inversion of the agent store. Deliberately takes the store and
    not AgentInventoryService: build() runs the agent reconcile, which writes,
    and this is called from GET /api/skills (see S4).
    """
```

`AgentAttachment` is a frozen dataclass of `(ref, name)` — `ref` being the store slug, `name`
the display name — which is all the chip and the filter need. `AgentStore.scan()` returns
`(agents, issues)`; ignore the issues here (the agents page reports them) and skip any agent that
failed to parse.

Cost: one directory listing plus one frontmatter parse per managed agent, on a store of tens of
agents. That is the same order as the tag load `list_skills` already does. Do not add a cache in
v1; if it ever shows up in a profile, the fix is to memoise per-request, not to persist.

### 3.2 Wiring — mind the container ordering

`skills_queries` is constructed at `container.py:281`, long before `agents_store` exists at
`:485`. Do **not** reorder the container to inject the store. Follow the precedent already set
for exactly this problem — `skills_queries.set_reconcile(...)` at `container.py:518` — and add a
late setter:

```python
skills_queries.set_agent_attachments(lambda: skill_attachments(agents_store))
```

called after `agents_store` is built. `SkillsQueryService` holds an optional callable and
degrades to `{}` when it is absent or raises, the same best-effort contract
`agents/inventory.py:59` uses in the other direction: an unreadable agent store must cost the
Skills page its chips, never its rows.

### 3.3 Payload shape

`skills_page_payload` (`skills/presenters.py:20`) already takes a `tags` map keyed by
`entry.skill_ref` and hands each row its slice. Add an `attachments` map the same way, and have
`row_payload` (`presenters.py:88`) emit:

```jsonc
"agents": [{ "ref": "code-reviewer", "name": "Code Reviewer" }]
```

Do the same in `skill_detail_payload` so the detail sheet can show and edit attachments for one
skill. Both default to `[]`, so the field is additive and no existing consumer breaks.

### 3.4 The bulk endpoint

One new route on the **skills** router — the Skills page is the caller, and the skills router is
where its other bulk verbs live:

```
POST /api/skills/attach-agents
{ "skillRefs": [...], "agentRefs": [...], "mode": "attach" | "detach", "dryRun": false }
```

Behaviour:

1. Normalise `skillRefs` to bare slugs (strip the `shared:` prefix, as `validate_skills` does)
   and run them through `validate_skills` **once** — a single 400 naming every unmanaged slug
   beats N failures.
2. For each agent ref: read the current `skills:` tuple, compute the union (attach) or
   difference (detach), preserving existing order and appending new slugs — then write through
   the same `agents_store.update(ref, skills=...)` call `PUT /api/agents/{ref}` uses
   (`api/routers/agents.py:274`), so the audited wrapper and `ensure_profile` still run.
3. Skip agents whose list is unchanged — no write, no audit entry, no Hermes profile churn.
4. Fire `auto_enable_skills_for_agent` per changed agent, exactly as `update_agent` does at
   `agents.py:318`, and collect the auto-enabled and failed pairs.
5. `container.invalidation.invalidate_all()` once at the end, not per agent.

Response carries `changed` (agent refs actually written), `skipped` (ref + reason), `autoEnabled`
(skillRef + harness pairs) and `failed` (skillRef + harness + error) — the same vocabulary
`AutoEnabledSkillResponse` / `AutoEnableFailureResponse` already use, so the frontend types are
mostly free.

**`dryRun: true` performs no writes** and returns only what *would* change — the `changed` list
and the projected `autoEnabled` pairs. That is what feeds the confirm dialog in S7. Compute it
by running steps 2 and 4 in "would" mode: for each candidate agent, the harnesses where it is
enabled (`adapter.is_enabled`) crossed with attached slugs that lack a binding
(`adapter.has_binding`) — the same two predicates `auto_enable_skills_for_agent` already
consults. Extract that projection into a helper so the preview and the apply cannot disagree;
a preview computed by a second, parallel implementation is worse than no preview.

Detach does **not** unbind skills from harnesses. Removing a skill from an agent's list says
nothing about whether the user still wants that skill installed — and `auto_enable` has no
inverse today. State this in the UI copy: *"Detaching leaves the skill installed on its
harnesses."*

---

## 4. Frontend design

### 4.1 Row chips

`SkillListRow` gains `agents: AgentAttachmentDto[]`. Render them in the row's existing chip area
next to the tag chips, visually distinct (an agent glyph, not the tag glyph) so S11's distinction
is legible at a glance. Clicking a chip toggles that agent into the `?agent=` filter, mirroring
what tag chips already do.

### 4.2 The agent filter

Add `agents?: string[] | null` to `SkillFilters` in `features/skills/model/selectors.ts` and a
`matchesAgents` predicate beside `matchesTags` (`selectors.ts:94`) — OR within agents, AND against
the other facets, same as tags. Drive it from a repeatable `?agent=` search param in
`SkillsWorkspacePage.tsx`, copying the `toggleTagFilter` / `clearTagFilters` pair at `:103` and
`:127`, and add `params.delete("agent")` to `clearFilters` (`:275`) and to the
`hasActiveFilters` test at `:162`. Options come from the union of `row.agents` across the
dataset — a `extractSkillAgentCounts` selector alongside `extractSkillTagCounts`.

### 4.3 The bulk control

A new `BulkAgentPopover` under `frontend/src/components/`, modelled on `BulkTagPopover.tsx` but
**not** a copy-paste of it — it is a fixed-vocabulary multi-select over known agents, so it has
no free-text commit, no 64-char rule, and no "create new" path. It offers Attach and Detach
(S6). Wire it into `BulkActionBar` the way `onTagSelected` is wired, add `"attach-agents"` to the
`MultiSelectAction` union, and gate it on `selectedManagedCount > 0` (S8).

### 4.4 Confirm

On Apply, call the endpoint with `dryRun: true`, then open `ConfirmActionDialog` stating: how
many agents will change, how many skills are being attached, and how many new harness bindings
that creates — naming the harnesses. Confirm re-issues the call with `dryRun: false`. If the dry
run projects zero new bindings, say so plainly ("no new harness bindings") rather than hiding
the dialog; the user asked for a write and should see it acknowledged.

Failures from the real call surface through the existing `setActionErrorMessage` channel, using
a `formatAttachFailureMessage` in the same shape as `formatMultiSkillFailureMessage`
(`use-skills-workspace-controller.ts:613`).

---

## 5. Phases

Each phase is one commit or a small series, and each ends green on `npm run validate`.

**Phase 1 — Reverse index (backend, read-only).** `attachments.py`, the late setter on
`SkillsQueryService`, the container wiring, `agents` on the row and detail payloads. Regenerate
the OpenAPI types (`npm run codegen:openapi`). No UI. Ends with the field visible in
`GET /api/skills` and a unit test proving `GET /api/skills` does not write to the agents store.

**Phase 2 — Read-only UI.** Row chips, the `?agent=` filter, the filter control, selectors and
their tests. The page becomes useful on its own here — a user can already answer "which skills
does this agent have?" — which makes this a safe place to stop if the rest slips.

**Phase 3 — The bulk endpoint.** `POST /api/skills/attach-agents` including `dryRun`, the shared
projection helper, and integration tests. No UI.

**Phase 4 — The bulk UI.** `BulkAgentPopover`, `BulkActionBar` wiring, the confirm dialog, the
controller handler, failure formatting.

**Phase 5 — Docs.** README (Skills page section and Agents page section), `ARCHITECTURE.md` (the
derived-index seam and why it bypasses `AgentInventoryService`), and a line in this plan's status
header marking it built.

---

## 6. Definition of Done

- A user can select N managed skills on the Skills page, attach them to M adopted agents in one
  action, see a preview of the harness bindings that creates, confirm, and see the result.
- Detach works and is clearly described as not unbinding from harnesses.
- The Skills matrix filters by agent, from both the filter control and a row chip.
- Attaching from the Skills page and attaching from `AgentSkillsFieldEditor` produce byte-identical
  agent files. **Test this directly** — it is the single claim the whole design rests on.
- `GET /api/skills` performs no writes. Proven by a test that snapshots agent-file mtimes and
  the audit journal across a list request (S4).
- Unmanaged skills in a selection are skipped with a stated reason; the batch still completes.
- One agent failing does not prevent the others from being written (S10).
- Mutation audit entries appear for bulk attaches, same shape as a single-agent update.
- `npm run codegen:check` is clean — the committed OpenAPI artifacts match the code.
- New tests: `tests/unit/test_agent_skill_attachments.py` (the inversion, empty/malformed
  stores, the no-write guarantee), `tests/integration/test_skills_attach_agents_routes.py`
  (attach, detach, dry-run-matches-apply, partial failure, unmanaged rejection), plus frontend
  tests beside `selectors.ts`, `BulkAgentPopover.tsx`, and `SkillsWorkspacePage.tsx`.
- **A pressure test**, in the style of `frontend/src/test/family_tag_star_ui_pressure.test.tsx`:
  a large multi-select spanning managed and unmanaged skills, several agents, at least one
  failing agent, asserting the reported counts match what was actually written.

---

## 7. Validation

Run the whole suite, as `CLAUDE.md` requires — and do not skip `lint:backend`:

```bash
npm run validate
```

Then, on this device, against the real store: attach a skill to an agent from the Skills page,
confirm the agent file's `skills:` list changed as expected, open the agent detail and confirm
the editor agrees, and confirm the skill appears bound on the agent's harnesses.

---

## 8. Delegation packet

- **Branch:** short-lived, off `main`, per `CLAUDE.md`. Logical commits, one per phase. Push.
  **No merge to `main` without review.**
- **Do not** add a new store, a new JSON sidecar, or a reserved tag prefix. If the design seems
  to require one, stop and escalate — that is S1 failing, and it is the owner's call.
- **Do not** reach for `AgentInventoryService` from the skills read path (S4). If the read-only
  seam turns out to be insufficient, escalate rather than accepting a reconcile on read.
- **Report honestly:** the DoD is checked by re-running the suite independently, not by relaying
  counts.

---

## 9. Out of scope

- Unmanaged agents (S3).
- Detach unbinding skills from harnesses — no inverse of `auto_enable` exists, and inventing one
  here would be a separate design (§3.4).
- Per-harness attachment ("this skill on this agent, but only on Codex"). The `skills:` field has
  no such axis and `docs/profiles-plan.md` S10 already rejected the equivalent idea for profiles.
- Attaching skills to agents from the *Agents* page in bulk. The agent-side single editor already
  exists and the reverse bulk direction is what was missing.
- Any change to what tags are or how they are stored.
