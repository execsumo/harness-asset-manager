# Adding an Asset Family

This guide is the implementation checklist for adding a new kind of extension to
Harness Asset Manager. It is intentionally a checklist rather than a framework
design: families share a lifecycle, but their native ownership and preservation
rules are different. Do not extract shared code until the family has proved which
parts are actually invariant.

## Before writing code

- [ ] Read `ARCHITECTURE.md`, the relevant existing family, and
      `harness_asset_manager/harness/catalog.py`.
- [ ] Define the family’s canonical record and ownership boundary.
      Decide exactly which fields HAM owns, which native fields must survive a
      read/write cycle, and whether the family is portable across machines.
- [ ] List every supported harness and every unsupported capability. An
      unsupported scope or harness must be reported explicitly; do not silently
      drop data or claim support based on a guessed native schema.
- [ ] Decide whether the family is a file tree, config subtree, rendered command
      file, or another shape. Reuse an existing binding profile where its
      invariants fit. Add a new profile only when the native ownership model
      genuinely differs.
- [ ] Decide whether unmanaged local observations can be adopted safely, whether
      drift can be repaired automatically, and what must remain a manual review.

## Canonical storage and domain model

- [ ] Add the family key to `FamilyKey` in
      `harness_asset_manager/harness/contracts.py`.
- [ ] Add a dedicated store or manifest under the central data directory. Keep
      device-local paths, generated output, credentials, and runtime state out
      of portable canonical records unless the family explicitly requires them.
- [ ] Give records stable IDs and deterministic serialization.
- [ ] Define validation and normalization rules at the store boundary.
      Reject malformed records rather than allowing invalid native output.
- [ ] Preserve unknown fields when the family owns a whole record or native
      document. A writer must not turn an unrelated native key into data loss.
- [ ] Define deletion, disablement, and stale-record behavior before adding UI
      actions.
- [ ] Add path helpers to `paths.py` and migration logic only if the family needs
      a new persisted location. Use atomic writes and the existing file-lock
      conventions.

## Native representation

### Mappers and codecs

- [ ] Add a mapper/codec for each native format. Keep conversion separate from
      filesystem mutation.
- [ ] Document the representability boundary for every canonical field.
      Unsupported values should produce a visible unsupported result, not a
      lossy approximation.
- [ ] Round-trip known fields and preserve unowned native fields, comments, and
      disabled state where the format permits it.
- [ ] Handle empty, malformed, legacy, and partially populated native documents.
- [ ] Make writes idempotent. Running enable or sync twice must not duplicate
      entries, reorder unrelated content unnecessarily, or change user-owned
      settings.

### Adapters and ownership

- [ ] Implement the adapter lifecycle for the chosen binding shape:
      discovery, read, enable/sync, disable, drift detection, and cleanup.
- [ ] For config-subtree families, read the complete document, mutate only the
      owned subtree, and atomically write it back. Preserve sibling keys and
      unmanaged entries.
- [ ] For rendered files, record the baseline needed to distinguish a clean
      clobber, one-sided edit, two-sided conflict, and missing baseline. Reuse
      `application/drift.py` instead of creating a second classifier.
- [ ] Define managed IDs and ownership metadata. Disabling the final HAM entry
      must remove only settings HAM can prove it owns.
- [ ] Keep project/workspace paths separate from global paths. Never rewrite a
      project file when the catalog binding is global-only.
- [ ] Keep secrets out of logs, audit parameters, manifests, and rendered
      artifacts unless the family has an explicit secure storage design.

## Application wiring

- [ ] Add the family’s store, read model, query service, mutation service, and
      optional reconciliation/auto-adoption service under
      `harness_asset_manager/application/<family>/`.
- [ ] Add the services to `BackendContainer` and construct them in
      `application/container.py`.
- [ ] Register read models with `InvalidationFanout` when mutations can make
      cached or derived views stale.
- [ ] Route mutations through the audited mutation boundary so successful,
      failed, and partial operations are recorded without leaking content or
      secrets.
- [ ] If auto-adoption is supported, add its setting and consumer together.
      Use safe equivalence checks, make it opt-in unless the safety case is
      already established, and leave conflicts for review.
- [ ] Add the family to refresh/reconciliation paths only after its read path is
      safe and idempotent.

## API, CLI, and frontend

- [ ] Add Pydantic request/response models and a router under
      `harness_asset_manager/api/routers/`.
- [ ] Include the router from `harness_asset_manager/api/app.py`.
- [ ] Expose list, detail, review, create/update, enable/disable, sync, and
      delete operations only where the family semantics support them.
- [ ] Use stable machine-readable API error codes when the endpoint needs client
      branching; keep human-readable messages for display.
- [ ] Add the corresponding `harnessam <family>` command group and register it
      in `harness_asset_manager/cli/commands/__init__.py`. CLI handlers must use
      the shared backend container, not a second implementation.
- [ ] Regenerate the OpenAPI client and verify `npm run codegen:check`.
- [ ] Add the frontend feature screens, navigation, loading/error/empty states,
      review actions, i18n strings, and capability-query invalidation.
- [ ] Ship ONE unified In-use page per family: managed and unadopted entries in
      the same view, with unadopted items reachable behind a URL-backed status
      filter (`?status=untracked`) and adopt/review actions inline. Do not add a
      second sidebar entry for review/unmanaged state — every existing family
      (skills, agents, slash commands, MCP, hooks) follows the single-link
      convention; see `McpInUsePage.tsx` or `AgentsInUsePage.tsx`.
- [ ] Make unsupported harnesses and unsupported scopes visible in the matrix.
      Do not hide a column or silently omit a record.
- [ ] Wire the family into the shared asset-tags system (see
      `docs/plan-asset-tags.md` §5 and the Skills implementation as the reference):
      include each entry's sorted `tags` array (`starred` first) in list/detail
      payloads via `AssetTagService` (`application/asset_tags/`, keyed
      `<family>:<ref>`); add a `PUT /api/<family>/{ref}/tags` replace-set endpoint;
      render the star column after the identity column with the filterable filled-star
      header toggling `?tag=starred` (see `SkillsWorkspacePage.tsx`,
      `MatrixView.tsx`/`MatrixRow.tsx`, `matrix-table__th/cell--star`); support tag
      chips and bulk actions where the family's BulkActionBar supports them. Tagging
      is sidecar-only — never write tags into documents or harness files.

## Catalog and documentation

- [ ] Add the family binding to each supported harness in
      `SUPPORTED_HARNESS_DEFINITIONS`.
- [ ] Use the correct profile fields for global/project scope, discovery paths,
      file format, subtree path, codec, render format, and capability probes.
- [ ] Add support notes and exact limitations to the catalog when behavior is
      provisional or best-effort.
- [ ] Update `ARCHITECTURE.md` and the README capability matrix.
- [ ] Link native documentation from catalog profiles where possible.
- [ ] Add a handoff entry recording the exact harness versions and behavior
      verified. A core-harness claim requires live evidence; documentation-only
      assumptions belong in best-effort support.

## Tests

Add tests at all three boundaries:

- [ ] **Pure model/mapper tests:** normalization, validation, round trips,
      unknown-field preservation, representability, malformed input, and
      idempotence.
- [ ] **Adapter tests:** fake-home path resolution, global/project boundaries,
      unmanaged promotion, managed drift, partial matches, disable cleanup,
      preservation of unrelated native content, and repeated operations.
- [ ] **API/CLI integration tests:** matrix status, CRUD and mutation behavior,
      error responses, audit records, refresh behavior, and auto-adoption gates.
- [ ] Add frontend tests for the matrix, detail/review states, unsupported
      capabilities, mutation errors, and invalidation after changes.
- [ ] Use `tests/support/fake_home.py` instead of the real home directory.
      Include both installed and omitted harness CLIs where capability detection
      matters.
- [ ] Add a regression test for every data-loss, path-escape, or ownership bug
      found during implementation.

## Validation gate

Run the narrowest relevant checks while developing, then the repository suite:

```bash
ruff check harness_asset_manager tests scripts
./.venv/bin/python -m unittest discover -s tests/unit
./.venv/bin/python -m unittest discover -s tests/integration
npm run typecheck
npm test
npm run build
npm run codegen:check
git diff --check
```

Review the diff for accidental generated files, real-home paths, secrets, and
changes outside the family before opening a pull request.
