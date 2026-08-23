# Plan — Asset tags with a pinned `starred` system tag

**Status: Planned (2026-08-23). Nothing shipped yet.** Phase 1 targets Skills only;
the storage schema is family-generic from day one so later phases are presentation
work, not migrations.

**Goal:** give users a way to mark and group their most important assets. Skills
routinely bloat into the hundreds; the owner wants to pull up "all skills tagged
`DevOps`" or "everything tagged `Core`", and to star the handful of assets they
touch constantly.

## 1. Decision of record

**Tags are the model; a star is its fastest interaction.**

- One tagging mechanism covers both needs: "my most important assets" is a
  boolean, "all DevOps skills" is a group. Two parallel marking systems
  (stars *and* tags) would force users to decide which one a given asset
  "deserves" — do not build that.
- The UI surfaces a special **`starred` system tag**: pre-listed, always offered,
  rendered as a one-click star toggle in matrix rows and detail headers. It is a
  real tag under the hood (appears in tag filters and counts), just promoted in
  the interface because starring must be zero-friction.
- All other tags are free-form user choices with autocomplete-from-existing to
  keep the vocabulary tight.

Rejected alternatives, for the record:

| Alternative | Why rejected |
|---|---|
| Stars only | Solves ~30% of the stated need; one undifferentiated pile, no DevOps/Core split |
| Stars + tags as separate features | Two mental models for one job; confusion guaranteed |
| Hierarchical/colored taxonomies | Overbuilt for now; revisit only if flat tags visibly strain |
| Deriving importance from usage telemetry | HAM doesn't run the harnesses; no signal source |

## 2. Storage: sidecar file, never frontmatter

Tags live in **`data/asset-tags.json`** (alongside `bindings.json`,
`skills-manifest.json`). They must NOT be written into asset documents:

- Skill Markdown gets synced/symlinked into harness roots; injecting HAM-owned
  frontmatter there pollutes files other tools read and complicates every codec.
- Tagging should be a cheap sidecar mutation that does not touch the document
  pipeline, reconcile paths, or audit snapshots.

Schema (v1):

```json
{
  "version": 1,
  "tags": {
    "skills:academic-research": ["starred", "core"],
    "skills:apple-notes": ["devops"]
  }
}
```

- Keys are `<family>:<ref>` (`family` ∈ the six capability families). Refs are
  stable slugs for managed assets. Unmanaged assets may be tagged in Phase 2+
  using their qualified ref (`skills:<harness>/<slug>`) — the schema does not
  care, but Phase 1 restricts writes to managed skills.
- The `starred` key has no special casing at the storage layer; it is a normal
  string. Only presentation treats it specially.

### Portable-store invariants apply

This file travels with folder sync like everything else in the store, so it
follows the three pinned invariants (ARCHITECTURE §4 "Store Portability"):

1. **No device-local data** — keys are family+slug refs, never absolute paths.
   (If unmanaged refs are admitted later, they persist home-relative per the
   `portable_paths.py` pattern.)
2. **Total reads** — a truncated/corrupt file degrades to "no tags" plus a
   surfaced issue, exactly like the agents ledger and sync-state stores. A bad
   tags file must never break an inventory read.
3. **Artifact tolerance** — conflict copies / editor backups of this file are
   ignored by scanners (already covered by `is_sync_artifact()`).

Writes go through `atomic_files` (atomic write + lock) like every other store
file.

## 3. API

- Tags ride along on existing reads: skill list/detail payloads gain a `tags`
  array (sorted, `starred` first). No new read endpoints.
- Mutations:
  - `PUT /api/skills/{ref}/tags` body `{tags: [...]}` → replace the full set
    (idempotent, matches the document-endpoint style). Response returns updated
    tags. Unknown tags are created implicitly; empty list clears all.
  - Normalization at write time: trim, case-fold for comparison but preserve
    first-seen display form; dedupe; reject `>` N chars / empty strings with a
    4xx `{code, error}` envelope.
- OpenAPI regenerated via `npm run codegen:openapi`.
- Deliberately out of scope for Phase 1: tag rename/delete across assets
  (edit each asset instead), per-tag metadata, permissions-family tagging.

## 4. Frontend (Skills phase)

- **Star toggle**: star icon in the skills matrix rows and detail header;
  optimistic update; also usable from BulkActionBar ("Star selected").
- **Filter integration** — this is where the value lives:
  - New URL-backed `?tag=` filter on `/skills`, composing with the existing
    `?status=` and `?harness=` params (multi-tag = OR within `tag=`, AND with
    everything else). Clear filters resets it.
  - FilterBar gains a tag section: chips for existing tags with counts,
    autocomplete input offering known tags.
  - `starred` renders as a star chip, pinned to the top of the tag list.
- **Sort**: "starred-first" as the default secondary sort is NOT imposed;
  sorting stays user-controlled. (Revisit if the owner asks.)
- Detail view shows tags as editable chips alongside the existing metadata.
- App-wide conventions respected: i18n copy, shared filter-chip component,
  selector-level filtering with tests mirroring the `?harness=` pattern.

## 5. Phases

1. **Skills (this plan's scope)** — store file + service, PUT endpoint, payload
   fields, star toggle, tag filters, bulk-star. Ships when the validation suite
   is green and the owner has used it live.
2. **Generalize** — extend payloads/endpoints to agents, slash commands, MCP,
   hooks, permissions; `docs/adding-a-family.md` checklist gains a "tags render
   in matrix + detail and support `?tag=`" item. Presentation work only; the
   schema already spans families.
3. **Possible later** — unmanaged-asset tagging (qualified refs); tag rename/
   merge tooling; marketplace-item tags.

## 6. Validation requirements (per phase)

Full suite green before landing: `npm run typecheck`, `bash scripts/test_backend.sh`,
`npm test`, `npm run build`. Specifically required:

- Unit: normalization/dedupe rules; corrupt-file total read; concurrent-write
  atomicity; round-trip preservation of unknown keys.
- Integration: PUT happy path + 4xx shapes; tags appear in list/detail payloads;
  `?tag=` filter semantics incl. composition with `status`/`harness`; portable
  arrival test (move store between synthetic homes, tags survive).
- Frontend: selector tests for tag filtering; star-toggle mutation tests;
  FilterBar chip rendering + Clear-filters participation.

## 7. Delegation notes

Implementation goes to agy via herdr per the working agreement: short-lived
branch off `main`, complete written brief, mandatory pressure-test (exercise
starring + filtering live against the real store), full validation suite, and
independent owner verification before merge.
