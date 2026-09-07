# Plan: Hermes Bot Integration

> **Status: IMPLEMENTED.** Phases 0-5 are complete and merged. This document records
> the agreed goal, architecture, and implementation plan for promoting Hermes from a
> best-effort harness target to a supported Bot/Profile integration. Every question
> Phase 0 was asked to settle is answered under "Phase 0 findings" below, and every
> open decision is closed.
>
> User-facing documentation lives in `README.md` under **Hermes Bots (Profiles)**;
> the internal shape is in `ARCHITECTURE.md`. Deviations from this plan that were
> decided during implementation are recorded inline, each with its reason.
>
> **Support tier is unchanged.** `hermes` remains `best_effort`. Promoting it to
> `core` is a separate product decision that changes what blocks a release, and this
> work does not propose it — see "Support tier is a separate decision" below.

> **Grounded against:** Hermes Agent v0.21.0 (2026.8.31), installed at
> `/usr/local/lib/hermes-agent`, and HAM at commit `33b4e64`. Claims about Hermes
> behavior below cite the file that establishes them, so a future reader can
> re-verify them against a newer Hermes rather than trusting this document.
> Anything not yet verified is marked **UNVERIFIED** and is Phase 0's job.

## Goal

Represent each Harness Asset Manager agent as a native Hermes Profile/Bot.
The Bot should have its own identity, model/provider configuration, sessions,
configuration, and precisely the skills selected for that agent.

A Bot's skills must remain connected to HAM's canonical skill store, while the
Hermes default profile remains unaffected unless a skill is explicitly enabled
there.

## Decisions

1. **Hermes Profile is the Bot primitive.** HAM creates and maintains one Hermes
   profile per HAM agent slug. Hermes Bot Mode then discovers and runs that
   profile natively.

   Verified: profiles are real and a profile *is* a complete `HERMES_HOME`
   containing `config.yaml`, `SOUL.md`, `.env`, `skills/`, and `sessions/`.
   Discovery is a plain directory scan of `<root>/profiles/` filtered by the
   profile-id regex (`hermes_cli/profiles.py::_iter_named_profile_dirs`), not a
   registry — so a correctly-shaped directory HAM creates is visible to
   `hermes profile list` without registering anything.

2. **Per-Bot skill bindings, shared content.** Each Bot has an independent
   enabled-skill set, but linked Bots use the same canonical HAM package. This
   is a per-Bot selection/binding, not a separate content revision.

3. **Keep the `harnessam` category.** HAM-managed Bot skills use:

   ```text
   <hermes-root>/profiles/<bot>/skills/harnessam/<skill>
       -> $HAM_DATA_DIR/skills/<skill>
   ```

   The category is a HAM namespace and collision boundary. It is not required
   by Hermes itself, but retaining it is useful for ownership, discovery, and
   migration of the existing Hermes adapter behavior.

   Note the root: **not** `$HERMES_HOME`. See "The `HERMES_HOME` trap" below.

4. **No shared `external_dirs` for Bot bindings.** HAM-linked skills are local
   to the Bot profile from Hermes' perspective. Do not expose the HAM store as
   a shared Hermes `skills.external_dirs` root.

   Verified: `external_dirs` is a real config key, and entries under it are
   read-only to both skill creation and the curator
   (`agent/skill_utils.py`, `tools/skill_usage.py:256,316`,
   `tools/skill_manager_guards.py:180`). That read-only property is exactly why
   it cannot host Bot-created skills — but it is also the protection we give up
   by not using it. See "Curator interaction" below, which is the cost side of
   this decision.

5. **Bot-created skills are profile-local.** Configure each managed Bot's
   `skills.create_dir` as its own:

   ```text
   <hermes-root>/profiles/<bot>/skills/harnessam
   ```

   Verified: `skills.create_dir` is a real key honored by the skill-creation
   path (`agent/skill_utils.py::get_skill_create_dir`,
   `tools/skill_manager_tool.py:185`).

   This keeps newly created skills attributable to the Bot and makes them
   discoverable by HAM for adoption.

6. **Two-way adoption is required.** A physical skill created by a Hermes Bot
   can be scanned, offered for adoption, copied into HAM's canonical store, and
   replaced by the canonical symlink.

7. **Provider/model configuration is in scope.** Each Bot may have its own
   Hermes `model.provider` and `model.default` configuration.

8. **External CLI backends are deferred.** Do not implement a Claude Code CLI
   or generic external CLI provider in this work. Hermes' existing native
   provider support is sufficient for the first integration. Existing Codex
   app-server support may be recognized later, but its separate Codex skill
   home is not part of this initial scope.

9. **HAM provisions profiles by writing the directory, not by executing
   `hermes`.** See "Profile provisioning" — this was the plan's largest
   unstated decision and it is now decided.

## Profile provisioning: HAM writes the directory

This is the highest-risk decision in the integration, so it is stated
explicitly rather than left implicit in "HAM creates or locates the profile".

**Constraint:** HAM has never executed a harness CLI. Every existing adapter is
pure filesystem manipulation; `shutil.which` appears only as an install probe
(`harness/kernel.py:107`, `application/skills/adapters.py:256`,
`application/agents/targets.py:51`). Shelling out to `hermes profile create`
would be a first-of-its-kind architectural precedent, and that command has side
effects well beyond creating a directory: it writes a **wrapper script named
after the profile onto `PATH`** (`create_wrapper_script`), registers a gateway
service (`_maybe_register_gateway_service`), and seeds skills in a subprocess.

**Decision:** HAM creates the profile directory itself, consistent with every
other HAM binding. This keeps provisioning idempotent, offline, testable against
a fake home, and free of PATH side effects.

**Cost:** HAM must replicate what `create_profile` does. Each of these is
non-obvious and each has a stated reason in Hermes' own source, so none may be
skipped:

| Behavior | Why it exists | Source |
|---|---|---|
| Name canonicalization + validation | Directory name *is* the profile id | `normalize_profile_name`, `validate_profile_name` |
| Seed empty `.env` at mode `0o600` | Without it "the profile silently inherited shell API keys — read by users as 'the new profile reads the root .env'" | `create_profile` |
| Seed `SOUL.md` | Bot identity; ours is written from the HAM agent anyway | `hermes_cli/default_soul.py` |
| Write a *current-schema* `config.yaml` | A v0 config makes Hermes' desktop/status warn the profile is outdated | `_migrate_profile_config_if_outdated` |
| Respect `.deleted` tombstones | A profile the user deleted must not silently resurrect | `named_profile_is_deleted` |

**Explicitly not replicated:** the PATH wrapper script and the gateway service
registration. HAM-managed Bots are addressed as `hermes -p <name>`; HAM must not
install commands onto the user's `PATH`. This is a deliberate divergence from
`hermes profile create` and should be stated in the UI.

**Phase 0 must confirm** that a HAM-written profile directory is fully
functional — `hermes profile list` shows it, `hermes -p <name> chat` runs, and
`hermes profile delete` removes it cleanly.

## The `HERMES_HOME` trap

`HERMES_HOME` names the **profile** home, not the Hermes root. From
`hermes_constants.py:147`: *"Root Hermes dir for profile-level ops: `<root>`
when `HERMES_HOME=<root>/profiles/<name>`"*. The default profile's home is
`~/.hermes` itself; named profiles live at `~/.hermes/profiles/<name>`.

HAM's `_hermes_home()` (`harness/catalog.py:29-33`) reads `HERMES_HOME`
straight through. Under any shell where it is exported — which is what
`hermes -p <name>` does — building `$HERMES_HOME/profiles/<slug>` yields
`~/.hermes/profiles/coder/profiles/<slug>`.

**Required:** a `_hermes_root()` resolver, distinct from `_hermes_home()`,
mirroring Hermes' own root derivation: when `HERMES_HOME` ends in
`profiles/<name>`, the root is two levels up; otherwise the root is
`HERMES_HOME` itself. Hermes guards this with marker-file heuristics so an
arbitrary path containing a `profiles` segment is not mistaken for a root
(`hermes_constants.py:159-204`) — HAM should mirror that, not just the string
manipulation.

`_hermes_home()` keeps its current meaning and continues to serve the existing
default-profile bindings.

## Slug to profile-name mapping

HAM slugs and Hermes profile ids are **not** the same alphabet, and the gap is
silent today.

- HAM: `_SLUG_SAFE = [^a-z0-9._-]+` replaced with `-`, then stripped of `-.`
  (`application/agents/store.py:19-23`). Dots are legal; there is no length cap.
- Hermes: `^[a-z0-9][a-z0-9_-]{0,63}$` (`hermes_cli/profiles.py:24`). No dots,
  must start alphanumeric, 64 characters max.
- Hermes additionally reserves `{hermes, default, test, tmp, root, sudo}` and
  rejects them outright (`_RESERVED_NAMES`), and additionally blocks its own
  subcommand names as profile names or aliases (`_HERMES_SUBCOMMANDS` — `chat`,
  `config`, `skills`, `update`, …).

Concrete failures: a HAM agent slugged `my.agent`, `_helper`, `test`, or one
over 64 characters cannot become a profile.

**Required:** a `hermes_profile_name(slug)` mapping function, following the
existing precedent of `codex_agent_name(slug)`
(`application/agents/adapters.py:144`), which already exists for exactly this
class of problem. It must map dots to hyphens, prefix or trim to satisfy the
regex, truncate to 64, and **refuse** rather than silently rewrite when the
result would be reserved or would collide with an already-mapped slug.
Collisions must surface as a user-visible error at enable time, not as a
silently shared profile.

Since HAM's `slugify` already lowercases, case collisions are not a concern.

## Desired filesystem layout

```text
$HAM_DATA_DIR/
  agents/<slug>.md
  skills/<skill-a>/SKILL.md
  skills/<skill-b>/SKILL.md
  skills/manifest.json

<hermes-root>/                    # ~/.hermes by default; see "The HERMES_HOME trap"
  config.yaml                     # default profile; unchanged by default
  skills/                         # default profile's skills; unchanged by default
  profiles/
    <profile-name>/               # == hermes_profile_name(<slug>)
      config.yaml
      .env                        # seeded empty, 0o600
      SOUL.md
      .no-bundled-skills
      skills/
        harnessam/
          <skill-a> -> $HAM_DATA_DIR/skills/<skill-a>
          <skill-b> -> $HAM_DATA_DIR/skills/<skill-b>
      sessions/ ...
      memory/ ...
```

The default Hermes profile must not receive a skill link merely because a HAM
Bot uses that skill.

## Runtime behavior

### Create/enable

1. HAM maps the agent slug to a profile name and validates it.
2. HAM creates or locates the profile directory (see "Profile provisioning").
3. HAM writes the Bot identity (`SOUL.md`) from the HAM agent definition.
4. HAM writes the profile's provider/model settings and Bot metadata where
   Hermes supports them.
5. HAM creates the profile-local `skills/harnessam/` directory.
6. HAM creates one symlink for every selected HAM skill.
7. HAM records each profile-specific binding in the agent binding ledger
   (`application/agents/ledger.py`) and the skill store manifest.

Profile creation writes the `.no-bundled-skills` marker so the Bot's local skill
set is intentional rather than inherited by accident. Existing non-HAM profile
skills must not be overwritten.

**`.no-bundled-skills` does not mean zero skills.** It means *essential skills
only*: `tools/skills_sync.py:367-369` prints "seeding essential skills only",
and Hermes' own test asserts that "a profile with `.no-bundled-skills` still
gets the hermes-agent skill"
(`tests/agent/test_phantom_tool_references.py:120`). Both the spec and the
matching test must be written against "essential set only", not "empty".

### Update

When the HAM agent prompt, provider/model settings, or skill selection changes:

- update `SOUL.md` and supported profile config fields;
- add links for newly selected skills;
- remove only HAM-owned links for deselected skills;
- leave physical, user-owned skill directories untouched;
- report conflicts instead of overwriting them.

### Disable/delete

Disabling the Hermes target removes only that Bot's HAM-managed skill links.
The canonical HAM agent and skill packages remain intact.

Deleting an agent must not implicitly destroy Hermes sessions, memory, or other
profile state unless the profile is explicitly marked as HAM-owned and the user
confirms destructive cleanup. The initial implementation should prefer
orphan-safe detachment.

## Curator interaction (the cost of Decision 4)

Decision 4 keeps HAM skills out of `external_dirs` — which is precisely the
mechanism that marks skills read-only to Hermes. Profile-local symlinks are
therefore **writable from Hermes' side by construction**, and Hermes runs
autonomous skill maintenance: `agent/curator.py::apply_automatic_transitions`
moves skills between active/stale/archived on an inactivity clock, and
`agent/background_review.py` prunes.

What is established:

- **Agent-facing delete is safe.** `tools/skill_manager_guards.py::_validate_delete_target`
  refuses to `rmtree` a skill directory that is a symlink or junction:
  *"Remove the link target manually if intended."* HAM's canonical packages are
  protected on this path.
- **Bundled-skill cleanup is safe.** `skills_sync` only cleans names tracked in
  Hermes' own `.bundled_manifest`; HAM skills are never in it
  (`tools/skills_sync.py:403`).

**Settled in Phase 0 (see finding 4): the canonical package is safe.**
`archive_skill` relocates via `Path.rename`, which moves the *symlink*, never the
target; and `apply_automatic_transitions` only iterates curator-managed skills
(`created_by: agent`), which a HAM binding never is. The residual failure is a
*detached binding* — a foreground `hermes skills archive` inside a Bot moves HAM's
link into `skills/.archive/` — which reconcile must treat as re-bindable rather than
as a missing package. Decision 4 stands as written.

The existing note that "edits through a Bot's symlink intentionally update the
canonical package" covers the *interactive* case only. It is not a statement
about autonomous mutation, and must not be read as one.

## Two-way skill adoption

### Scan

The Hermes skills adapter must discover both:

- the default Hermes skill root, where applicable; and
- every managed profile's `skills/` tree.

For each profile, the adapter should identify:

- a symlink resolving into HAM's canonical skill store as a managed binding;
- a physical, valid skill package as an unmanaged adoption candidate;
- bundled/official Hermes skills according to the existing Hermes exclusion
  policy (`_hermes_scan_policy`, which already reads `.bundled_manifest` and the
  hub lock — `application/skills/adapters.py:548-627`).

Managed status must be determined by the symlink target and recorded binding,
not only by the directory name. The `harnessam` category remains the normal
location and legacy categorized links must remain recognizable during migration.

### Adopt

For a physical Bot skill:

1. validate and parse the package;
2. ingest a copy into HAM's canonical skill store and manifest;
3. replace the Bot's physical package with a symlink to the canonical package;
4. record a binding for that specific Bot profile;
5. preserve the Bot's visibility of the skill without restarting Hermes where
   Hermes' normal skill refresh permits it.

Adoption must never silently replace an existing canonical package with the
same directory name. It should offer an explicit update/merge path or report a
conflict.

**Automatic adoption is not an open question.** `SkillsAutoAdoptService` already
exists (`application/skills/auto_adopt.py`) with an `is_enabled` gate, a
mutation-audit journal, and a rule that adopts only genuinely new unmanaged
directories while leaving differing copies of the same skill for manual review.
The work here is to extend that service's roots to managed profile skill trees
and confirm its fingerprint rule behaves when the same skill exists in two Bot
profiles — not to design a new opt-in mode.

### Binding identity

The current harness-level binding identity (`hermes`) is not sufficient for
multiple independent Bots. Binding records must distinguish targets:

```text
<harness>            # harness-wide — every value that exists today
<harness>:<scope>    # a narrower target within it, e.g. hermes:coder
```

**Decided:** `<harness>:<scope>`, not the `hermes-profile:<name>` this document
first floated. The family is then everything before the first `:`, which makes each
consumer fix a one-line derivation rather than a suffix-stripping special case, and
it generalises to any future scoped harness. `:` occurs in neither a HAM harness id
nor a Hermes profile id (`^[a-z0-9][a-z0-9_-]{0,63}$`), so the split is unambiguous,
and every stored value today parses as scope `None` and round-trips byte-identically
— no migration. What a scope *means* is the harness's business; for Hermes it is a
profile name.

A canonical package may therefore be bound to any number of Hermes profiles,
and disabling one profile cannot affect another. The read model should expose
both the harness family (`hermes`) and the profile-specific target.

**This ripples further than the manifest.** Persistence itself is permissive —
`enabled_harnesses` is a free-form `tuple[str, ...]` normalized only for sort
and de-duplication (`application/skills/manifest.py:10-20`), so a
`hermes:<profile>` value round-trips without a schema migration. But three
consumers assume a catalog harness id:

1. **Frontend logo mapping.** `getHarnessPresentation` looks up a closed
   `HarnessLogoKey` union and returns `null` for anything unknown
   (`frontend/src/components/harness/harnessPresentation.ts:9,47`). Profile
   targets need to resolve to the `hermes` logo via the family, not the target.
2. **Matrix columns.** `application/skills/presenters.py:158-159` filters columns by
   exact `column.harness in linked_harnesses`. Per-profile targets will not match
   a `hermes` column and will render as unbound.
3. **Cross-device arrival.** `manifest.py:33-41` documents recorded intent as
   the one fact the filesystem cannot carry across machines, so a synced store
   can *propose rebuilding* bindings on a new device. A `hermes:coder`
   binding has no meaning on a device without that profile. The proposal path
   (`tests/unit/test_cross_device_arrival.py`) needs a defined behavior:
   surface it as "profile missing — create it?" rather than dropping the intent
   or erroring, and never let one unappliable scoped item fail the whole plan.

The same `normalize_enabled_harnesses` helper is imported by the permissions and
hooks stores (`application/permissions/store.py:11`). Those families are not
changing here, but the shared helper means any tightening of the format is a
cross-family change, not a skills-local one.

Edits through a Bot's symlink intentionally update the canonical HAM package,
matching the existing shared-symlink behavior for other harnesses. Materialize
or copy semantics can remain an explicit future escape hatch for independent
content.

## Provider and model specification

Each Bot may persist Hermes-native model routing in its profile config. Hermes
accepts either `default` or `model` as the key name, and its own example uses
the provider-prefixed form:

```yaml
model:
  provider: anthropic
  default: "anthropic/claude-opus-4.6"    # form used by cli-config.yaml.example
```

**HAM writes whatever the user selects and hardcodes no model IDs.** The IDs
above are quoted from Hermes' shipped example purely to fix the *format*
question; they are not a recommendation and must not be baked into HAM.

**Decided: HAM writes the bare id in `model.default`, with the provider in its own
`model.provider` key.** The live install's own working default profile is exactly
that shape:

```yaml
model:
  provider: openai-codex
  base_url: https://chatgpt.com/backend-api/codex
  default: gpt-5.6-luna
```

`model.default` is Hermes' canonical key — `hermes_cli/config.py::
_normalize_root_model_keys` migrates `model.model` and `model.name` onto it at the
single load/save chokepoint, with precedence `default > model > name`. A slash in the
id is not a provider prefix Hermes parses; it is simply part of ids that natively
contain one (OpenRouter). So HAM must never synthesise `<provider>/<id>` — it writes
the two fields the user chose, separately.

Provider availability and credentials remain Hermes concerns; HAM should report
configuration failures without rolling back the created HAM agent.

Actual execution through the Claude Code CLI, a generic CLI backend, or a
separate Codex CLI skill/config home is explicitly deferred. The integration
must not claim that a Bot's Hermes profile skills automatically become skills
for a Codex app-server subprocess.

### Config writer ownership

Two writers now touch Hermes YAML and the boundary must be explicit:

- the existing `configs` binding owns the **default profile's**
  `~/.hermes/config.yaml` at `subtree_path=()`, excluding `mcp_servers`;
- the new profile adapter owns **`<root>/profiles/<name>/config.yaml`** and
  writes only the `model` subtree there.

Comment loss is not a risk on this path: HAM uses `ruamel.yaml` and
`tests/unit/test_config_document_round_trip.py` pins verbatim
load-dump identity precisely so a whole-document read-modify-write cannot
destroy user comments or formatting. Reuse `config_document` rather than
introducing a second YAML path.

## Implementation plan

### Phase 0 — Verify against the installed Hermes (new; blocks everything)

The catalog's own `support_note` records that HAM's Hermes adapters *"have never
run against a real Hermes install"* (`harness/catalog.py`, slash-commands
binding), and RECOMMENDATIONS.md §1.3 flags the same. A real install is
available. Settle empirically, against a throwaway profile, before committing to
Phases 1-3:

- a HAM-written profile directory is listed by `hermes profile list`, runs under
  `hermes -p <name>`, and deletes cleanly;
- what a minimal current-schema `config.yaml` must contain to avoid the
  "outdated profile" warning;
- the actual essential-skill set seeded under `.no-bundled-skills`;
- **whether the curator, `background_review`, or `skills_hub` can archive,
  move, or replace a skill that is a symlink** (the data-loss question);
- whether Hermes picks up a new symlink under `skills/harnessam/` without a
  restart, which Adopt step 5 assumes.

Record the answers in this document. Phase 3's design depends on the curator
answer; do not start it before that is known.

#### Phase 0 findings — verified 2026-09-06 against the installed Hermes v0.21.0

Method: a HAM-shaped profile directory (`~/.hermes/profiles/hamprobe`) was written
by hand — no `hermes` CLI involved — exercised with the real CLI, then deleted.
Reproduce by re-running the steps below; the probe left no residue.

1. **A hand-written profile directory is fully functional.** `hermes profile list`
   showed `hamprobe` immediately, with no registration step. `hermes -p hamprobe
   doctor` and `hermes -p hamprobe skills list` both ran against it. `hermes profile
   delete hamprobe -y` removed it cleanly. Provisioning by writing the directory is
   confirmed viable; Decision 9 stands.

2. **Minimal current-schema `config.yaml` is one key: `_config_version`.** With
   `_config_version: 15`, `hermes doctor` reported *"⚠ Config version outdated
   (v15 → v40) (new settings available)"*; with `_config_version: 40` it reported
   *"✓ Config version up to date (v40)"*. Nothing else is required — the rest of the
   schema deep-merges from `DEFAULT_CONFIG`.

   **HAM must not hardcode `40`.** Read the version the local install considers
   current from the default profile's `~/.hermes/config.yaml` `_config_version` and
   mirror it; omit the key when that file is absent or carries no version. A
   hardcoded constant would start warning on the next Hermes schema bump.

3. **The essential set under `.no-bundled-skills` is exactly `{hermes-agent}`.**
   `tools.skills_sync.ESSENTIAL_SKILLS == {"hermes-agent"}`. Specs and tests must say
   "essential set only", never "empty" — but note HAM does not seed it: seeding is
   `seed_profile_skills()`'s job and runs on Hermes' own schedule (`hermes update`).
   A HAM-created profile simply starts with no bundled skills at all, which is the
   intended state.

4. **The data-loss question resolves in our favour: archiving moves the *link*.**
   `tools.skill_usage.archive_skill()` was called directly against a profile-local
   `skills/harnessam/probe-skill -> /tmp/hamcanon/skills/probe-skill`. Result:

   ```text
   archive: (True, 'archived to .../skills/.archive/probe-skill')
   .../skills/.archive/probe-skill -> /tmp/hamcanon/skills/probe-skill   # still a symlink
   /tmp/hamcanon/skills/probe-skill/SKILL.md                             # intact
   ```

   `_relocate()` uses `Path.rename`, which relocates the symlink itself, so a
   canonical HAM package can never be moved, rewritten, or destroyed through a Bot's
   link. The same holds for `hermes profile delete`, whose `rmtree` unlinked the
   symlink and left the target untouched.

   **Autonomous archiving cannot even reach HAM links.** `apply_automatic_transitions`
   iterates `curated_report()`, which is built from curator-managed provenance
   (`created_by: agent`) plus pinned skills. On the probe profile it returned `[]`
   for a linked skill. HAM bindings carry no `.usage.json` provenance record, so the
   curator never considers them.

   **The hub paths cannot reach a link either.** `hermes_cli/skills_hub.py`'s
   `rmtree` calls at `:500` and `:711` operate on the *quarantine* directory, never
   on an installed skill. The rmtree-replace inside `install_from_quarantine` is
   gated by `_resolve_lock_install_path`, which walks the install path
   component-by-component and **refuses any symlink or junction redirect** —
   *"Unsafe install path"* — precisely so a lock entry cannot point through a link.
   `do_update`'s destructive replace applies only to hub-installed skills tracked in
   the hub lock, which a HAM binding never is. `agent/background_review.py` contains
   no `rmtree` at all. All three paths the plan listed as UNVERIFIED are closed.

   **Residual risk is binding detachment, not data loss.** A foreground
   `hermes skills archive <name>` inside a Bot moves HAM's link into
   `skills/.archive/`. HAM's reconcile must therefore treat "link recorded but
   missing from the managed category" as a re-bindable state, not an error — and
   must not conclude the canonical package is gone. Open decision 5 (excluding
   HAM profiles from the curator) is **closed: not needed.**

5. **A new symlink is picked up with no restart and no registration.** Dropping
   `skills/harnessam/probe-skill -> <canonical>` made `hermes -p hamprobe skills list`
   report it as `category=harnessam, source=local, trust=local, status=enabled` on the
   very next invocation. Adopt step 5's assumption holds.

6. **The default profile stayed untouched throughout.** No `probe-skill` entry ever
   appeared under `~/.hermes/skills/`.

7. **`hermes profile delete` writes a `profiles/.deleted/<name>` tombstone** (a file,
   not a directory) beside the profile dir, and `create_profile` refuses to resurrect
   over it unless the leftover is an identity-free empty shell. HAM must honour the
   same rule — see the provisioning table.

### Phase 1 — Hermes profile adapter

- Add a supported Hermes Bot/Profile adapter separate from the legacy
  `~/.hermes/agents/*.md` convention.
- Add `_hermes_root()` and `hermes_profile_name(slug)` (see above).
- Create/update profile identity and supported configuration fields, replicating
  the provisioning table.
- Retain best-effort, non-transactional behavior: HAM resource creation is not
  rolled back if profile binding fails.

### Phase 2 — Per-profile skill bindings

- Add profile-aware Hermes skill roots to the catalog/adapter.
- Keep `layout="categorized"` and use `harnessam` as the managed category.
- Create/remove profile-local symlinks safely.
- Preserve legacy global Hermes skill bindings during migration.
- Add target-aware manifest/ledger binding records, plus the three consumer
  fixes listed under "Binding identity".

### Phase 3 — Two-way discovery and adoption

- Scan all managed profile skill roots.
- Classify canonical symlinks versus physical unmanaged packages.
- Surface Bot-created packages in HAM's adoption UI/API.
- Extend `SkillsAutoAdoptService` to profile roots rather than adding a parallel
  mechanism.
- Add conflict, stale-link, broken-link, and duplicate-name handling.

### Phase 4 — Provider/model configuration

- Add provider/model fields to the Hermes Bot create/edit flow.
- Write them into the profile's `config.yaml` via `config_document`.
- Decide and document bare vs. provider-prefixed model ids.
- Validate that the resulting profile can be launched by Hermes.
- Keep external CLI backend work out of this phase.

### Phase 5 — UI and documentation

- Show Hermes Profiles as a supported target rather than a conventional
  Markdown-only harness.
- Display each Bot's skill bindings independently.
- Show adoption candidates with their originating Bot profile.
- Explain shared canonical content and the consequences of editing through a
  symlink.
- Document provider/model settings and the deferred CLI limitation.
- State that HAM-managed Bots do not install `PATH` wrapper scripts and are
  addressed as `hermes -p <name>`.

**Support tier is a separate decision.** "Supported target" above is UI
language. Promoting `hermes` from `best_effort` to `core` is a product decision
that changes what blocks a release: `EXPECTED_CORE` is pinned to
`{claude, codex, agy, cursor}` in `tests/unit/test_harness_support_tiers.py`,
and promotion requires either all six families bound or a declared
`KNOWN_CORE_GAPS` entry. This plan does **not** propose that promotion; if it is
wanted, raise it explicitly.

## Validation requirements

Add coverage for:

- slug-to-profile-name mapping, including dots, over-length, reserved names, and
  refusal on collision;
- `_hermes_root()` derivation when `HERMES_HOME` points at a named profile;
- profile creation seeding `.env` (0o600), `SOUL.md`, and a current-schema
  `config.yaml`;
- profile creation seeding **only the essential skill set** under
  `.no-bundled-skills` (not an empty skills tree);
- refusal to resurrect a profile carrying a `.deleted` tombstone;
- profile-local `harnessam` symlink creation;
- default Hermes profile remaining unchanged;
- two Bots sharing one canonical package independently;
- disabling one Bot preserving the other Bot's link;
- physical Bot skill discovery;
- adoption replacing the physical directory with a canonical symlink;
- adoption conflict and rollback behavior;
- broken/stale link detection;
- profile-specific provider/model persistence, including comment preservation on
  an existing `config.yaml`;
- a `hermes:<profile>` binding rendering the Hermes logo and matrix column
  correctly in the frontend;
- cross-device arrival of a `hermes:<profile>` binding for a profile that
  does not exist locally;
- non-rollback behavior when a Hermes profile operation fails.

Run the full project validation suite before landing implementation:

```bash
npm run typecheck
bash scripts/test_backend.sh
npm test
npm run build
```

## Open decisions before implementation

1. ~~Exact profile ownership marker and orphan cleanup UX~~ — **closed: there is no
   marker and there is no cleanup.** HAM records the binding in its own agent
   binding ledger and never destructively deletes a Hermes profile; disabling a Bot
   *detaches* (removes the HAM-owned links and stops updating `SOUL.md`) and leaves
   sessions, memory, and the directory intact. Writing an ownership file into
   someone else's home would buy only a destructive-delete path we have decided not
   to offer. Deleting a profile stays `hermes profile delete`'s job.
2. ~~The final manifest schema for profile-specific binding targets~~ —
   **closed: `<harness>:<scope>`**, see "Binding identity". No migration; existing
   values round-trip byte-identically.
3. ~~Whether the Hermes main profile should continue supporting legacy HAM skill
   links alongside the new per-profile model~~ — **closed: yes, permanently, and it
   is not a migration.** The default profile is a legitimate Hermes home; its
   `~/.hermes/skills/harnessam/` links stay exactly as they are and remain
   addressable as the unscoped `hermes` target. Per-profile targets are purely
   additive, so nothing has to move and no user's existing bindings change.
4. ~~Bare vs. provider-prefixed model ids in `model.default`~~ — **closed: bare id
   plus a separate `model.provider`**, matching the live install. See "Provider and
   model specification".
5. ~~Whether HAM-managed profiles should be excluded from Hermes' curator~~ —
   **closed by Phase 0 finding 4:** archiving relocates the symlink, and the
   autonomous curator never sees HAM links at all. No exclusion mechanism is
   needed; reconcile must merely tolerate a detached link.

### Resolved since the first draft

- **How profiles are provisioned** — HAM writes the directory; it does not
  execute the `hermes` CLI. See "Profile provisioning".
- **Explicit vs. automatic adoption** — already answered by the existing
  `SkillsAutoAdoptService`; the work is extending its roots, not choosing a
  model.

### Known-vestigial, confirm before spending effort on migration

The legacy `~/.hermes/agents/*.md` convention has no native Hermes loader — the
catalog says so in a comment, and the directory does not exist on a real v0.21.0
install. Migration concern for it is likely smaller than open decision 3
implies; confirm before designing a migration path for it.
