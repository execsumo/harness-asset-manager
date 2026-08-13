# Adding a Harness

This guide is the implementation and verification checklist for adding a harness
integration. Harness support is declared once in the catalog and then consumed by
all asset families. Do not add a family-specific list of harnesses elsewhere.

## Establish the support contract first

- [ ] Identify the exact CLI/product and the versions to support. Distinguish
      the CLI from an IDE integration when they use different configuration
      files or permission models.
- [ ] Read the current official documentation and inspect a live installation.
      Do not infer a native schema from a neighboring harness.
- [ ] Record global, project, workspace, environment-variable, and command-line
      precedence.
- [ ] For each family, record the native file/config path, format, ownership
      boundary, discovery paths, and whether HAM can write it safely.
- [ ] Classify every family as supported, unsupported, provisional, or
      not installable. Explain why an unsupported cell exists.
- [ ] Choose `core` only when behavior is verified against the live CLI and the
      harness meets the core support contract. Use `best_effort` for documented
      assumptions that must not block releases.

## Add the catalog entry

Add one `HarnessDefinition` to
`harness_asset_manager/harness/catalog.py`:

- [ ] Use a stable lowercase `harness` ID and user-facing `label`.
- [ ] Add the logo key and an `install_probe` executable.
- [ ] Set `support_tier` deliberately. The catalog order is the canonical matrix
      order; place the new definition in the intended product order.
- [ ] Add only the family bindings that are actually supported. A binding is a
      contract, not a placeholder for future work.
- [ ] Use `FileTreeBindingProfile` for directory-shaped assets. Define the
      managed root, environment override, discovery roots, availability, app
      probes, layout, and category behavior as applicable.
- [ ] Use `ConfigSubtreeBindingProfile` for a HAM-owned subtree inside a native
      document. Define the canonical write path, discovery paths, file format,
      subtree path, codec, and capability probe.
- [ ] Use `CommandFileBindingProfile` for rendered prompt/command files. Define
      the root, output directory, invocation prefix, render format, scope,
      glob, frontmatter support, and documentation URL.
- [ ] Use `AgentFileBindingProfile` for static agent definitions. Define the
      output format, file glob, root/output paths, and unavailable reason when
      the harness has no installable agent format.
- [ ] Add a `support_note` or capability-unavailable reason for limitations that
      the UI should explain.

## Implement and verify each family

For every binding added to the catalog:

- [ ] Start with the native format fixture and mapper/codec tests. Verify exact
      field names, nesting, path semantics, and disablement behavior.
- [ ] Preserve unknown native keys, sibling entries, comments where supported,
      and user-authored allow/ask entries. HAM must mutate only its owned data.
- [ ] Verify enablement, repair, disablement, and deletion are idempotent.
      Re-enabling must repair HAM-owned stale state without clobbering unrelated
      user settings.
- [ ] Test managed, unmanaged, drifted, missing, duplicate, malformed, and
      partially representable native entries.
- [ ] Confirm the binding never writes a project/workspace file when the product
      contract is global-only.
- [ ] For rendered files, test baseline hashes and the safe drift decision table.
      Preserve native-only fields through a store/render/parse round trip.
- [ ] For permissions, verify deny/allow/ask semantics and auto-run behavior
      independently. Never write an inferred no-prompt mode.
- [ ] For hooks and config-subtree families, test alternate discovery locations
      and preservation of foreign entries.
- [ ] For skills, test directory symlinks, adoption, layout, and app-vs-CLI
      installation detection.

## Detection, settings, and capability behavior

- [ ] Add a fake-home fixture path for the harness and a stub CLI name to
      `tests/support/fake_home.py` when needed.
- [ ] Test both installed and omitted CLI cases. If the harness can be present
      as an app without a CLI, test the app probe separately.
- [ ] Verify environment-variable and legacy override precedence through
      `resolve_context` and the catalog resolver.
- [ ] Confirm disabled harness settings remove the harness from every family
      matrix without requiring a restart.
- [ ] Confirm unsupported families remain visible with an explanatory status
      rather than disappearing from the matrix.
- [ ] Add or update support-tier tests. A core harness with a missing family
      requires an explicit entry in `KNOWN_CORE_GAPS` and a justification.

## API, CLI, and frontend integration

- [ ] Confirm existing family endpoints and CLI commands automatically consume
      the catalog entry. Add code only where the new harness has genuinely
      different behavior.
- [ ] Add frontend copy for native limitations, unavailable capabilities, and
      installation notes. Keep the capability matrix derived from the catalog.
- [ ] Update README support tables, `ARCHITECTURE.md`, and native documentation
      links.
- [ ] If support is version-specific, document the tested versions and the
      unsupported range instead of presenting it as universal.

## Verification matrix

Use a synthetic home and test at least:

| Scenario | Expected result |
|---|---|
| CLI installed, empty native state | Harness is detected and the first enable creates valid native state |
| CLI omitted | Harness is reported unavailable and no native path is written |
| Existing unrelated native keys | Keys survive every HAM mutation |
| Existing unmanaged asset | It is shown for review or safely adopted, per family policy |
| HAM-owned asset edited natively | Safe repair or manual conflict review, never silent loss |
| Project config differs from global config | Only the documented scope is read or written |
| Harness disabled in Settings | Its columns disappear across all family matrices |
| Malformed/legacy native config | Error or review state is explicit and recoverable |
| Repeated enable/disable/sync | Output is stable and entries are not duplicated |

The minimum relevant commands are:

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

Before calling the harness supported, independently inspect the native files
produced in a fake home, run the exact live CLI versions, and record the evidence
in `docs/handoff.md`. A delegate's passing report is not the acceptance signal.
