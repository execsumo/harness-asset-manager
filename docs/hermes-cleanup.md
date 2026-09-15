# Hermes Skills and Dotfiles Cleanup Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Make Hermes Skills a first-class, core Harness Asset Manager capability while keeping HAM’s shared store and per-harness binding model intact, so native Hermes Skills and HAM-enabled Skills are visible and usable through the same Hermes UI and runtime paths.

**Architecture:** HAM remains the owner of canonical managed Skill packages, manifest metadata, and binding intent. Enabling a managed Skill for Hermes materializes a directory symlink at Hermes’s normal profile-local Skills root, under the existing `harnessam` category; Hermes must treat that path as an ordinary local Skill for discovery, prompt loading, viewing, editing, and UI/API access. Dotfiles persist the canonical store and portable intent, not machine-specific generated binding links.

**Tech Stack:** Python 3.11+ / FastAPI / unittest and pytest in HAM; Hermes Agent Python tooling / FastAPI dashboard routes; React/Vite HAM UI; JSON/YAML manifests; filesystem directory symlinks; `npm` and the repository validation suite.

---

## 1. Decision summary

This is the product contract. Do not substitute a different integration during implementation.

### 1.1 Canonical ownership

The canonical managed Skill package lives in HAM’s resolved Skill store:

```text
$HAM_DATA/skills/<package-dir>/SKILL.md
```

With the current Linux defaults this is `~/.harnessam/skills/<package-dir>`. `resolve_app_paths()` remains the source of truth; do not hard-code `~/.local/share/harnessam` into new code or documentation. A dotfiles checkout may own `~/.harnessam` by symlink, but the application must continue to resolve its path from `HOME`, XDG variables, and HAM’s existing migration rules.

`skills-manifest.json` is the canonical persisted record for managed Skill metadata and per-harness binding intent. The `enabledHarnesses` field is intent, not a second filesystem truth. Live enablement remains derived from the binding that exists on the current machine.

### 1.2 Hermes materialization

For the default Hermes profile, a managed Skill enabled for Hermes is exposed as:

```text
$HERMES_HOME/skills/harnessam/<package-dir>
    -> $HAM_DATA/skills/<package-dir>
```

For a named Hermes profile, use the existing HAM resolver and profile scope:

```text
$HERMES_HOME/profiles/<profile>/skills/harnessam/<package-dir>
    -> $HAM_DATA/skills/<package-dir>
```

The exact path must come from `harness_asset_manager/harness/catalog.py` and `harness_asset_manager/application/skills/adapters.py`, not from a new hard-coded path. The `harnessam` category is an implementation detail for collision avoidance and provenance; Hermes must not require a special runtime mode to load it.

Native Hermes Skills remain in their normal Hermes-owned roots and categories. HAM does not point Hermes at the entire HAM store and does not silently adopt every native Skill. A user can explicitly adopt a native Skill into HAM; after adoption the canonical copy and explicit bindings are managed by HAM.

### 1.3 Configuration that is deliberately *not* used

Hermes supports both of these settings:

```yaml
skills:
  create_dir: ...
  external_dirs: ...
```

They are real Hermes features. They are not the HAM integration:

- `skills.create_dir` controls where Hermes-created Skills are written and also adds an existing configured directory to Hermes discovery. Pointing it at HAM’s store would let Hermes write packages without HAM manifest entries or binding intent.
- `skills.external_dirs` adds broad discovery roots. Pointing it at HAM’s store would expose every package in the store, including packages not enabled for Hermes, and would bypass HAM’s per-harness selection.

Leave both unset for the recommended setup unless a user independently needs those Hermes features for a separate directory. Add a regression test or documentation check so future work does not reintroduce this workaround as the default.

### 1.4 Ownership of lifecycle operations

The following must be indistinguishable from a native Hermes Skill from the Hermes user’s point of view:

- appears in the Skills list and Hermes Web UI;
- participates in normal prompt loading and Skill invocation;
- opens through `skill_view()` and the dashboard detail/content endpoint;
- can edit `SKILL.md` and supported package files through the normal Hermes editor/tool path, with writes reaching the canonical HAM package;
- respects Hermes’s normal disabled/enable toggle and profile scoping;
- preserves `references/`, `templates/`, `assets/`, and `scripts/` behavior.

HAM remains the owner of package adoption, source updates, binding/unbinding, and destructive deletion. Hermes must not recursively delete a HAM canonical package through a directory symlink. If Hermes’s native delete path encounters a HAM-managed binding, it must either:

1. remove only the binding and report that the canonical package remains HAM-managed, while synchronizing HAM intent through an explicit supported integration; or
2. refuse with a precise message directing the user to `harnessam skills disable/delete`.

Do not silently call `shutil.rmtree()` on a symlink target. The first implementation may keep deletion HAM-owned; “seamless” applies to runtime and non-destructive Skill use/editing, not to giving two stores destructive authority over one package.

---

## 2. Current state and verified gaps

The plan is based on the current HAM and Hermes source, not on an assumed `create_dir` API.

### 2.1 HAM already has the right binding shape

The existing HAM path is substantially correct:

- `harness_asset_manager/harness/catalog.py` declares Hermes with a categorized `FileTreeBindingProfile`, default category `harnessam`, dynamic profile roots, and a scoped profile resolver.
- `harness_asset_manager/application/skills/adapters.py` scans the Hermes roots and creates/removes directory bindings.
- `harness_asset_manager/application/skills/manifest.py` stores `enabledHarnesses` as normalized, sorted, deduplicated intent and tolerates old/malformed manifests.
- `harness_asset_manager/application/skills/store.py` records binding intent without making an enable operation fail merely because a best-effort manifest write failed.
- `harness_asset_manager/application/skills/mutations.py` already exposes enable/disable operations and calls the adapter plus manifest recording path.
- `harness_asset_manager/harness/kernel.py` already resolves enabled harnesses per family; the support tier currently controls release commitment, not whether a user can toggle a supported binding.

The live smoke path already succeeds:

```text
harnessam skills enable shared:<skill> --harness hermes --json
~/.hermes/skills/harnessam/<skill> -> HAM store package
hermes skills list -> category harnessam, enabled
harnessam skills disable shared:<skill> --harness hermes --json
binding disappears without deleting the HAM package
```

Do not replace this with manually maintained Hermes links or a second HAM-specific Hermes directory.

### 2.2 The support-tier model is too coarse

`HarnessDefinition.support_tier` is currently harness-wide. Hermes is `best_effort` because slash-command and other Hermes areas are not fully verified. Changing the whole Hermes definition to `core` would falsely claim that those unrelated areas meet the core release contract.

The required model change is family-scoped commitment:

```python
@dataclass(frozen=True)
class HarnessDefinition:
    # Existing field retained for compatibility and as the default for all families.
    support_tier: SupportTier = "best_effort"
    family_support_tiers: Mapping[FamilyKey, SupportTier] = field(default_factory=dict)

    def support_tier_for(self, family: FamilyKey) -> SupportTier:
        return self.family_support_tiers.get(family, self.support_tier)

    def is_core_for(self, family: FamilyKey) -> bool:
        return self.support_tier_for(family) == "core"
```

Set only this Hermes family override:

```python
support_tier="best_effort",
family_support_tiers={"skills": "core"},
```

Existing fully core harnesses can keep `support_tier="core"`, which makes all of their currently declared families core by default. Hermes slash commands, config bindings, agents, MCP, and future families remain best-effort unless separately promoted with their own evidence and decision.

### 2.3 Hermes has one symlink-blind management path

The live Hermes source has two relevant behaviors:

- `agent.skill_utils.iter_skill_index_files()` walks with `os.walk(..., followlinks=True)` and is used by normal discovery, prompt construction, and `tools.skills_tool`; this is why HAM links already appear and function at runtime.
- `tools/skill_manager_tool.py::_iter_skill_dirs()` uses `root.rglob("SKILL.md")`, which does not descend into a directory symlink. Its `_find_skill()` also resolves a candidate before matching a categorized relative name, which loses the lexical `harnessam/<skill>` path when the package directory itself is a symlink.

The Hermes dashboard routes expose this gap directly:

- `hermes_cli/web_routers/skills.py::get_skills()` uses `_find_all_skills()` and can list HAM links.
- `get_skill_content()` and `update_skill_content()` use `tools.skill_manager_tool._find_skill()` / `_edit_skill()`, so a HAM-linked Skill cannot reliably open or edit from the UI.

This is the focused Hermes interoperability fix required for identical Skill behavior. It is not a request to make slash commands, MCP, agents, or Hermes profiles generally HAM-managed.

### 2.4 Dotfiles currently persist the wrong mix of state

The current dotfiles setup has these problems to clean up:

- `.harnessam/skills-manifest.json` exists locally but `.harnessam/.gitignore` ignores it. Cross-device copies therefore lose the per-harness binding intent that is needed to recreate Hermes links.
- `.hermes/skills/harnessam/*` links are generated machine-local bindings and should not be treated as portable source. Absolute link targets copied between devices will point at the old user/home/store.
- Old/manual `.hermes/skills/devops/*` links and new HAM-generated `.hermes/skills/harnessam/*` links can coexist during migration, creating duplicate names and ambiguous ownership.
- The repository has historical absolute links into both `/home/herwin/.local/share/harnessam` and `/home/herwin/.harnessam`; new HAM-generated links must resolve the current machine’s canonical store and old generated links must be removed or regenerated, never hand-edited one by one without identifying their generator.
- There are two apparent skill trees in the broader dotfiles history (`.harnessam/skills` and `.harnessam/harnessam/skills`). The cleanup must classify each tree as canonical content, generated binding, or stale duplicate before deleting anything.

The cleanup must not commit credentials, `.env` files, auth/session state, runtime databases, API tokens, certificate files, or private keys.

---

## 3. Implementation phases

The phases are ordered so a failed interoperability test cannot be hidden by a dotfiles migration.

### Phase 0 — Freeze the contract with tests

#### Task 0.1: Add family-scoped support commitments

**Objective:** Let Hermes Skills become core without promoting unrelated Hermes families.

**Files:**

- Modify: `harness_asset_manager/harness/contracts.py`
- Modify: `harness_asset_manager/harness/catalog.py`
- Modify: `harness_asset_manager/harness/kernel.py` only if a family-specific catalog query is needed by release gates
- Test: `tests/unit/test_harness_support_tiers.py`
- Test: `tests/unit/test_harness_catalog.py`

**Steps:**

1. Add `family_support_tiers`, `support_tier_for(family)`, and `is_core_for(family)` as shown in §2.2. Keep the existing `support_tier` and `is_core` behavior for callers that ask about the whole harness.
2. Add a family-aware catalog helper, preferably `core_harness_ids(family: FamilyKey | None = None)`. With no family it must preserve the existing overall core set; with `family="skills"` it must include Hermes.
3. Set Hermes’s `family_support_tiers` to `{"skills": "core"}` and leave its overall `support_tier` as `"best_effort"`.
4. Replace the single pinned core set test with an explicit map, for example:

```python
EXPECTED_CORE_BY_FAMILY = {
    "skills": {"claude", "codex", "agy", "cursor", "hermes"},
    "mcp": {"claude", "codex", "agy", "cursor"},
    "slash_commands": {"claude", "codex", "agy", "cursor"},
    "hooks": {"claude", "codex", "agy", "cursor"},
    "permissions": {"claude", "codex", "agy", "cursor"},
    "agents": {"claude", "codex", "agy", "cursor"},
}
```

   Derive the non-skills rows from the existing expected core policy if the test suite already has a single source for them; do not duplicate a policy table unnecessarily.
5. Add assertions that Hermes is core for `skills` and not core for `slash_commands` (and that `core_harness_ids()` without a family does not silently promote Hermes).
6. Run the focused support/catalog tests and record the result before continuing.

**Expected result:** The release/coverage ratchet can gate Hermes Skills independently while Hermes slash-command support still reports its existing provisional/best-effort status.

#### Task 0.2: Pin the HAM Hermes binding contract

**Objective:** Make the existing materialization shape and profile behavior non-regressible.

**Files:**

- Test: `tests/unit/test_skills_adapters.py`
- Test: `tests/unit/test_skill_binding_intent.py`
- Test: `tests/unit/test_paths.py`
- Test: `tests/integration/test_skills_mutations.py`
- Modify: `tests/support/fake_home.py` if the fixture lacks a named Hermes profile root

**Steps:**

1. Add a fake-home test that seeds one native Hermes Skill in the profile-local root and one managed package in the HAM store.
2. Enable the managed package for Hermes and assert the binding is a directory symlink, points to the current fake machine’s store, and contains the entire package—not only `SKILL.md`.
3. Assert disabling removes only the HAM binding and leaves the canonical store package and native Hermes Skill untouched.
4. Repeat the enable/disable cycle and assert idempotence, normalized manifest intent, and no duplicate binding path.
5. Add a named-profile case using the existing `hermes:<profile>` target syntax/resolvers. Assert the link is created only in that profile and does not appear in the default profile or another profile.
6. Assert all persisted paths remain portable metadata; no foreign machine root is written into `skills-manifest.json`.

**Expected result:** HAM’s actual adapter is the only supported path to materialize a managed Hermes Skill, and profile scope is proven before UI work begins.

### Phase 1 — Fix Hermes interoperability at the common discovery boundary

This phase belongs in the Hermes Agent repository, not in a HAM-specific fork of the directory layout. Use the Hermes source checkout that is installed/tested locally only as a verification target; publish the change through the normal Hermes repository/contribution process before declaring the HAM feature complete.

#### Task 1.1: Make skill-manager lookup use the canonical iterator

**Objective:** Make `skill_manage` and the dashboard editor find the same symlink-backed Skills that normal Hermes discovery already finds.

**Files in the Hermes repository:**

- Modify: `agent/skill_utils.py` only if the iterator needs a small shared helper or its contract needs an explicit test
- Modify: `tools/skill_manager_tool.py`
- Test: `tests/tools/test_skill_manager_tool.py`
- Test: `tests/agent/test_skill_utils.py`
- Test: `tests/hermes_cli/test_web_server_skill_editor.py`

**Implementation shape:**

1. Replace the raw traversal in `_iter_skill_dirs()` with the existing canonical iterator:

```python
def _iter_skill_dirs(root: Path):
    from agent.skill_utils import iter_skill_index_files

    for skill_md in iter_skill_index_files(root, "SKILL.md"):
        yield skill_md.parent
```

   Preserve the existing exclusion behavior; the canonical iterator is the shared exclusion/symlink-following chokepoint.
2. Change categorized matching in `_find_skill()` to compare the candidate’s **lexical** path to the active local root before resolving the candidate. The relevant invariant is:

```python
local_root = _skills_dir()
...
try:
    relative = skill_dir.relative_to(local_root)
except ValueError:
    relative = None
if relative is not None and relative.as_posix() == name:
    return {"path": skill_dir}
```

   Do not use `skill_dir.resolve()` for this category comparison; resolving a child directory symlink destroys the `harnessam/<skill>` lexical identity. Continue using resolved paths for security/collision checks where appropriate.
3. Preserve bare-name lookup and external-directory rules. A categorized `category/name` form remains local-root scoped; a bare name may match a supported external root according to existing precedence.
4. Add tests for both a native category directory and a category child that is a directory symlink. Test bare and categorized identifiers.
5. Test that the returned path is the lexical Hermes path, while reading `SKILL.md` reaches the canonical target.

**Expected result:** `_find_skill("harnessam/example")`, `_find_skill("example")`, `skill_view`, `skill_manage(action="patch")`, and the web editor all resolve a HAM directory binding without following or flattening the link during lookup.

#### Task 1.2: Define safe HAM-linked delete behavior

**Objective:** Prevent a native Hermes delete operation from recursively deleting HAM’s canonical store while giving users an actionable outcome.

**Files in the Hermes repository:**

- Modify: `tools/skill_manager_tool.py` and/or `tools/skill_manager_guards.py`
- Test: `tests/tools/test_skill_manager_tool.py`
- Test: `tests/hermes_cli/test_web_server_skill_editor.py` if the UI exposes deletion

**Steps:**

1. Add a regression test with `local_root/category/name` as a directory symlink to an outside canonical package.
2. Prove `_delete_skill()` never calls recursive deletion on that symlink and never removes files from the target package.
3. Choose one explicit behavior and document it in the Hermes error/result contract:
   - refuse with `Skill '<name>' is managed externally/by HAM; use Harness Asset Manager to unbind or delete it`; or
   - unlink only the binding and call a documented HAM integration to clear binding intent.
4. Do not infer HAM ownership from a fragile absolute path string alone. If ownership detection is needed, use an explicit marker/adapter contract or the existing category plus a safe target classification, and test false positives for ordinary user symlinks.
5. Keep the first release conservative: a precise refusal is better than a silent deletion or a new cross-process HAM protocol that is not needed for Skill execution.

**Expected result:** HAM-managed packages are protected from destructive Hermes operations, and the behavior is visible rather than a low-level `rmtree` error.

#### Task 1.3: Verify the Hermes UI/API parity

**Objective:** Prove that native and HAM-enabled Skills take the same Hermes UI and runtime paths.

**Files in the Hermes repository:**

- Test: `tests/hermes_cli/test_web_server_skill_editor.py`
- Test: `tests/hermes_cli/test_web_server_skills_profiles.py`
- Test: `tests/tools/test_skills_tool.py`
- Test: `tests/agent/test_skill_utils.py`

**Steps:**

1. Build an isolated Hermes home containing:
   - a native Skill at `skills/native-category/native-skill/SKILL.md`;
   - a directory symlink at `skills/harnessam/managed-skill` pointing to a separate canonical package with `SKILL.md`, `references/example.md`, and `scripts/example.py`.
2. Assert `_find_all_skills()` returns both, with ordinary category values and no HAM-only code path.
3. Assert `/api/skills` returns both and marks both enabled under the same response shape.
4. Assert `GET /api/skills/content?name=harnessam/managed-skill` returns 200 and the canonical `SKILL.md` content.
5. Assert the dashboard update path changes the canonical target content, clears/reloads the normal Skill prompt cache, and does not replace the directory symlink with a regular directory.
6. Assert `skill_view` can load the linked supporting file using the same `file_path` contract as a native Skill.
7. Assert profile-scoped requests see only the active profile’s native and HAM bindings.
8. Assert Hermes’s normal disabled list still disables either kind by declared Skill name without changing HAM’s `enabledHarnesses` intent.

**Expected result:** The Hermes UI and runtime cannot distinguish a HAM-linked Skill from a native local Skill for read/use/edit flows.

### Phase 2 — Make HAM’s core Skill commitment observable in HAM UI/API

The current HAM Skills matrix already exposes the Hermes column and enable/disable mutations. Do not add a second Hermes-only matrix. Change only what is needed to expose the family-scoped commitment and clarify ownership.

#### Task 2.1: Keep support metadata family-scoped in API contracts

**Objective:** Prevent the UI from labeling all Hermes capabilities core when only Skills are core.

**Files:**

- Inspect/modify: `harness_asset_manager/api/routers/harnesses.py` or the current harness/settings router that serializes catalog definitions
- Inspect/modify: `harness_asset_manager/api/schemas/*`
- Inspect/modify: `frontend/src/api/generated.ts` through the existing OpenAPI codegen command, not hand edits
- Test: related Python route tests
- Test: `frontend/src/app/capability-registry/overview.test.ts` and settings tests if affected

**Steps:**

1. Search the current API payloads before editing. If support tiers are not exposed, keep them internal and do not create UI state solely for this feature.
2. If the Settings/capability API exposes a tier, return `supportTierByFamily` (or an equivalently explicit shape) rather than a single Hermes tier. Preserve old response fields only when compatibility requires them.
3. Ensure the Skills matrix continues to include Hermes whenever Hermes is enabled for the `skills` family and that unrelated matrices retain their existing state.
4. Regenerate OpenAPI TypeScript types with `npm run codegen:openapi` and verify no unrelated schema churn.
5. Add a test that Hermes Skills is core while Hermes slash commands remains provisional/best-effort in any surface that displays the distinction.

**Expected result:** HAM’s UI tells the truth about the narrow commitment and continues to use the same generic Skills matrix for all harnesses.

#### Task 2.2: Clarify managed/native provenance without changing runtime semantics

**Objective:** Let users understand ownership without creating a separate runtime experience.

**Files:**

- Inspect/modify: `harness_asset_manager/application/skills/presenters.py`
- Inspect/modify: `harness_asset_manager/application/skills/queries.py`
- Inspect/modify: `harness_asset_manager/api/schemas/skills.py`
- Inspect/modify: `frontend/src/features/skills/api/types.ts`
- Inspect/modify: `frontend/src/features/skills/api/mappers.ts`
- Inspect/modify: the existing Skill detail/matrix components under `frontend/src/features/skills/`
- Test: `tests/integration/test_skills_mutations.py`
- Test: existing frontend Skills component tests; add focused tests only if the payload changes

**Steps:**

1. Preserve the existing state vocabulary (`enabled`, `disabled`, `empty`, conflict/error states) and generic harness cell behavior.
2. If a source/ownership label is needed, add a non-authoritative field such as `ownership: "ham" | "native"` or use existing `sourceKind`/location data. Do not make the frontend infer ownership from path strings.
3. Render HAM ownership as an explanation and link to HAM’s enable/disable lifecycle, not as a different “kind” of Skill.
4. Verify native unmanaged Hermes Skills remain adoption candidates and are never silently marked managed merely because they are visible in the Hermes root.

**Expected result:** The HAM UI can explain why a Skill is linked while Hermes still experiences it as an ordinary Skill.

### Phase 3 — Persist intent and rebuild bindings portably

This phase is required for a reproducible dotfiles setup across devices. It is deliberately limited to Skills first; do not pull slash commands or config-merge families into this work.

#### Task 3.1: Track the actual Skills manifest

**Objective:** Make per-harness Skill intent survive dotfiles sync without committing runtime state or secrets.

**Files:**

- Modify in the dotfiles repository: `.harnessam/.gitignore`
- Track in the dotfiles repository: `.harnessam/skills-manifest.json`
- Inspect/migrate: `.harnessam/skills/**`
- Inspect/remove/regenerate: `.hermes/skills/devops/**`, `.hermes/skills/harnessam/**`
- Do not track: `.hermes/skills/.curator_*`, runtime databases, auth, `.env`, logs, caches, or generated machine-local state

**Steps:**

1. Before staging, audit every manifest field and every tracked Skill file for secrets. Keep only metadata already owned by HAM; never retain API-key values, tokens, passwords, connection strings, certificate files, or private keys.
2. Remove `skills-manifest.json` from the ignore rule after confirming it is safe to persist. If a future manifest field can contain sensitive material, add explicit serialization/ignore separation rather than ignoring the entire intent file again.
3. Identify the one canonical content tree. Prefer `.harnessam/skills/<package-dir>` as the dotfiles-owned HAM package tree because it matches the catalog/store model. Do not retain a duplicate `.harnessam/harnessam/skills` tree unless code proves it is a distinct, intentional store.
4. Remove old/manual Hermes links for the same package names and regenerate them with HAM. Do not edit absolute link targets manually in bulk.
5. Keep generated `.hermes/skills/harnessam/<package>` bindings out of the portable source set, or explicitly ignore that generated subtree if the dotfiles repository currently captures it. Document that bootstrap recreates it.
6. Verify `git status`, `git diff --check`, and `git ls-files -s` show only intended canonical files and no stale absolute symlinks.

**Expected result:** Dotfiles carries canonical HAM Skill content plus binding intent; a checkout never carries another machine’s generated Hermes binding targets.

#### Task 3.2: Add a Skills-only bootstrap planner/applier

**Objective:** Recreate recorded HAM-to-Hermes Skill bindings on a new device without silently deleting local choices or overwriting conflicts.

**Files:**

- Inspect/extend: `harness_asset_manager/application/bootstrap/planner.py`
- Inspect/extend: `harness_asset_manager/application/bootstrap/applier.py`
- Inspect/extend: `harness_asset_manager/application/container.py`
- Add/extend: `harness_asset_manager/api/routers/bootstrap.py`
- Add/extend: `harness_asset_manager/cli/commands/bootstrap.py`
- Test: `tests/unit/test_cross_device_arrival.py`
- Test: `tests/integration/test_bootstrap*` or the current bootstrap test module
- Docs: `docs/bootstrap-new-device.md`

**Scope:** Implement the Skills placement family first. Reuse the existing generic planner contracts if present, but do not make this task responsible for MCP, hooks, permissions, agents, or slash commands.

**Steps:**

1. Read `SkillStoreEntry.enabled_harnesses` as the only synced Skill binding-intent source.
2. For each `(shared:<package>, harness)` intent, produce one of:

   | Condition | Action |
   |---|---|
   | harness unavailable or disabled in HAM settings | `skip` with reason |
   | package absent from the local store | `skip` with reason |
   | correct link already exists | `skip` as `already-linked` |
   | target occupied by foreign content | `conflict`; never overwrite by default |
   | target absent | `link` |

3. Resolve the target path from the current machine’s `ResolutionContext`, including `hermes:<profile>` scope. Never copy a persisted absolute link target from machine A.
4. Make apply additive and idempotent. Re-check the target immediately before creating a link, aggregate per-item failures, and leave foreign files untouched.
5. Provide a dry-run and non-interactive path suitable for dotfiles bootstrap:

```text
harnessam bootstrap --skills --dry-run
harnessam bootstrap --skills --yes --json
```

   If the existing bootstrap command already has a generic action model, add a skills filter instead of inventing a second command.
6. Surface conflicts and missing harnesses clearly in CLI/API/UI. Do not auto-remove a binding that is absent from intent; a user may have disabled it locally.
7. Add a cross-device test: copy only the HAM store and tracked manifest from machine A to machine B, run the Skills bootstrap, assert links point under B’s store, assert machine A paths do not appear in B’s persisted state, and assert a second run is a no-op.

**Expected result:** A dotfiles clone plus one explicit bootstrap action reconstructs Hermes Skill links for the current machine and profile safely.

#### Task 3.3: Document the dotfiles runbook

**Objective:** Make the supported setup repeatable without undocumented symlink surgery.

**Files:**

- Modify: `docs/bootstrap-new-device.md`
- Modify: `README.md`
- Modify: `docs/hermes-cleanup.md` only if implementation decisions materially change this contract
- Optional external runbook: the dotfiles repository’s setup/bootstrap script, after its exact path is identified

**Document this workflow:**

```text
1. Clone/sync dotfiles.
2. Link or restore the canonical HAM store at ~/.harnessam.
3. Install Hermes and create/select the desired Hermes profile(s).
4. Start HAM once so migrations/path resolution complete.
5. Run `harnessam bootstrap --skills --dry-run`.
6. Review conflicts and missing harnesses.
7. Run `harnessam bootstrap --skills --yes --json`.
8. Verify `harnessam skills list --json` and Hermes `skills list`.
```

Explain that native Hermes Skills stay native; HAM-managed Skills appear under Hermes’s ordinary `harnessam` category; generated links are recreated per machine; and `skills.create_dir`/`external_dirs` are not part of this integration.

---

## 4. Test matrix and acceptance criteria

The feature is complete only when all of these are true.

### HAM behavior

- [ ] `harnessam skills enable shared:<name> --harness hermes --json` creates the expected default-profile directory symlink.
- [ ] `harnessam skills enable shared:<name> --harness hermes:<profile> --json` creates only the named-profile binding when profile-scoped enablement is supported by the existing CLI/API shape.
- [ ] Re-enable is idempotent; disable removes only the binding and retains canonical content.
- [ ] `skills-manifest.json` records `enabledHarnesses` deterministically and contains no absolute machine-specific binding target.
- [ ] `harnessam skills list/show` exposes the same managed Skill package and states as the other file-tree harnesses.
- [ ] Hermes is core for `skills` in the catalog/release gate; Hermes remains best-effort for slash commands and other unverified families.

### Hermes behavior

- [ ] A native Hermes Skill and a HAM-linked Skill both appear in `skills_list()` and `GET /api/skills`.
- [ ] Both appear in the Hermes Web UI with the same row/detail/content behavior.
- [ ] Both participate in normal prompt loading and invocation; no HAM-specific prompt loader exists.
- [ ] `skill_view()` works by bare name and categorized name for the HAM Skill.
- [ ] Hermes dashboard content GET and PUT work for the HAM Skill.
- [ ] Editing `SKILL.md` changes the canonical HAM package through the link and does not replace the link.
- [ ] Supporting files under `references/`, `templates/`, `assets/`, and `scripts/` resolve identically to native files.
- [ ] Hermes disabled-skill behavior remains independent from HAM’s per-harness binding intent.
- [ ] Deletion cannot recursively delete the canonical HAM package.
- [ ] Default and named Hermes profiles remain isolated.

### Dotfiles/portability behavior

- [ ] The canonical HAM Skill package tree is singular and documented.
- [ ] `skills-manifest.json` is intentionally persisted and safe to commit, or a clearly documented equivalent intent file is used.
- [ ] Generated `.hermes/skills/harnessam/*` bindings are regenerated locally and are not copied as absolute symlinks between devices.
- [ ] A two-device test proves no machine-A path leaks into machine-B links or persisted state.
- [ ] Existing native Hermes Skills are not deleted, adopted, or renamed by cleanup unless explicitly selected.
- [ ] No credential material, auth/session data, private keys, certificates, or runtime artifacts are introduced into either repository.

### Required validation

Run from `/home/herwin/projects/harnessAM` after HAM changes:

```bash
npm run typecheck
bash scripts/test_backend.sh
npm test
npm run build
```

Also run the focused tests during implementation:

```bash
pytest \
  tests/unit/test_harness_support_tiers.py \
  tests/unit/test_harness_catalog.py \
  tests/unit/test_skills_adapters.py \
  tests/unit/test_skill_binding_intent.py \
  tests/unit/test_cross_device_arrival.py \
  tests/integration/test_skills_mutations.py
```

Use the Hermes repository’s declared test command for:

```text
tests/tools/test_skill_manager_tool.py
tests/tools/test_skills_tool.py
tests/agent/test_skill_utils.py
tests/hermes_cli/test_web_server_skill_editor.py
tests/hermes_cli/test_web_server_skills_profiles.py
```

The previous environment did not successfully spawn the targeted `pytest` executable, so a future implementation must report that setup issue honestly and install/use the project’s declared test environment rather than treating a missing test process as a pass.

Before handoff:

```bash
git diff --check
rtk git status --short --branch
```

Review the diff for unintended path/config changes, and verify the generated build corresponds to the source branch before reporting completion.

---

## 5. Risks and guardrails

| Risk | Guardrail |
|---|---|
| Promoting all Hermes support to core by changing one field | Use family-scoped support tiers; assert Hermes Skills core and slash commands not core. |
| Exposing every HAM package to Hermes | Do not configure `skills.create_dir` or `skills.external_dirs` to the HAM store; materialize only explicit HAM bindings. |
| Hermes editor cannot find a directory symlink | Use `iter_skill_index_files(..., followlinks=True)` and lexical local-root matching; test categorized and bare lookup. |
| Hermes deletes canonical HAM content | Refuse or unlink only through an explicit safe ownership contract; never `rmtree()` a symlink. |
| Dotfiles copies stale absolute paths | Track canonical content/intent, regenerate bindings from current `ResolutionContext`, and audit symlink targets. |
| Duplicate native/HAM Skill names shadow one another | Preserve Hermes’s existing precedence/collision behavior and make adoption explicit. Add a collision test. |
| A manifest write failure makes a successful binding look like a failed mutation | Preserve HAM’s current best-effort manifest-write behavior and test it. |
| A new profile accidentally receives default-profile Skills | Test `hermes:<profile>` targets and `/api/skills?profile=...` in isolated homes. |
| Scope expands into slash commands, MCP, agents, or config synchronization | Keep this work in the Skills family; leave unrelated support tiers and adapters unchanged. |
| Cleanup commits secrets or runtime state | Audit files before staging; preserve existing dotfiles ignore rules for auth, `.env`, tokens, databases, logs, caches, and certificate/key material. |

---

## 6. Open decisions to resolve during implementation

These are bounded implementation choices, not reasons to block the overall direction:

1. **Hermes delete UX:** choose the conservative explicit refusal first unless a supported HAM callback/API already exists. Do not invent a hidden subprocess protocol solely to make deletion look native.
2. **Family-tier API exposure:** if HAM currently does not expose support tiers to the frontend, keep the new family-scoped metadata internal and update only release/catalog tests. Add UI metadata only if an existing surface needs to display it.
3. **Bootstrap command shape:** extend the existing bootstrap planner/applier if present; otherwise add a Skills-only filter/command. Do not duplicate the generic bootstrap engine.
4. **Manifest tracking policy:** track `skills-manifest.json` only after inspecting all fields for sensitive data. If the live file format later gains secrets, split intent into a safe persisted file rather than weakening the no-secrets rule.
5. **HAM edit provenance:** a Hermes UI edit through a HAM binding changes the canonical package. If HAM later needs audit/source-update conflict handling, add it to HAM’s existing store/audit model; do not copy files merely to avoid following the link.

---

## 7. Definition of done

The implementation can be called first-class/core for Hermes Skills only when:

1. HAM’s family-scoped catalog marks Hermes Skills core without marking unrelated Hermes families core.
2. HAM enable/disable and profile-scoped binding tests pass against the existing adapter path.
3. Hermes’s shared discovery/editor path finds and edits HAM directory symlinks exactly as native Skills.
4. Native and HAM Skills both appear in Hermes UI/API and function through the same runtime code paths.
5. HAM-managed deletion is safe and explicit.
6. A tracked manifest plus Skills bootstrap can recreate current-machine links without stale absolute paths.
7. The HAM validation suite, focused HAM tests, Hermes focused tests, and a two-device pressure test all pass.
8. README/bootstrap documentation and the dotfiles runbook describe the same ownership and configuration model.

Until the Hermes editor lookup fix and the cross-device intent path are verified, keep the Hermes Skills catalog commitment as a planned promotion rather than claiming the integration is complete.
