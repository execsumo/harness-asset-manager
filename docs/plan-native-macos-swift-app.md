# Native macOS Swift app plan

## Goal

Create a native macOS application for Harness Asset Manager without regressing its local-first filesystem safety, cross-harness compatibility, CLI interoperability, or portable `~/.harnessam` store.

The recommended path is **not** a big-bang rewrite. Ship a SwiftUI application over the existing Python domain core first, then replace the core family by family behind a stable Swift service protocol. This produces a genuinely native user experience early while keeping the most failure-prone config and reconciliation behavior proven.

## Code review summary

### Current architecture

- `frontend/src/App.tsx` and `frontend/src/components/{Shell,Sidebar}.tsx` compose a React 19 single-page application with feature routes for Overview, Configs, Permissions, Agents, Skills, Slash Commands, MCP, Hooks, Marketplace, and Settings.
- Feature screens use TanStack Query and feature-local controllers. The common interaction is a filterable asset-by-harness matrix, URL-backed filters, a detail drawer/sheet, per-harness mutations, bulk actions, tags/stars, confirmation dialogs, and error/toast feedback. Representative implementations are:
  - `frontend/src/features/skills/screens/SkillsWorkspacePage.tsx`
  - `frontend/src/features/mcp/screens/McpInUsePage.tsx`
  - `frontend/src/features/permissions/screens/PermissionsPage.tsx`
  - `frontend/src/features/marketplace/components/MarketplaceLayout.tsx`
- Shared UI patterns live in `frontend/src/components`, especially `matrix/`, `detail/`, `BulkActionBar.tsx`, `FilterBar.tsx`, and `ConfirmActionDialog.tsx`.
- `harness_asset_manager/api/app.py` exposes the application through FastAPI. The checked-in OpenAPI document currently describes 77 paths and 89 operations. Generated TypeScript API types are in `frontend/src/api/generated.ts`.
- `harness_asset_manager/application/container.py` is the composition root. It wires query/read-model/mutation services for Skills, Agents, Slash Commands, MCP, Hooks, Permissions, Configs, Settings, Marketplace, tags, reconciliation, and mutation auditing.
- `harness_asset_manager/harness/catalog.py` is the canonical harness capability and path catalog. It currently covers Claude, Codex, Antigravity, Cursor, OpenCode, Factory Droid, and Hermes across JSON, JSONC, TOML, YAML, Markdown, symlink, and rendered-file bindings.
- The app is file-backed rather than database-backed. `harness_asset_manager/paths.py` defines the compatible `~/.harnessam` layout and migrations.
- The CLI builds the same backend container directly (`harness_asset_manager/cli/main.py`), so the web server and CLI share domain behavior and stores.

### Behavior that a port must preserve

1. **Safe filesystem mutation**
   - `harness_asset_manager/atomic_files.py` uses same-directory temporary files, `fsync`, atomic replacement, advisory `flock`, and explicit symlink handling.
   - The Swift implementation must match these semantics so the native app and existing CLI can run concurrently.

2. **Source-preserving config edits**
   - `harness_asset_manager/config_document.py` preserves comments, ordering, quoting, and untouched bytes across TOML, JSONC, YAML, and JSON edits.
   - Generic Swift `Codable`, TOML, or YAML decode/encode is not an acceptable substitute; it would destroy user formatting and comments.

3. **Ownership, drift, and conflict safety**
   - Skills and most agents use canonical store files plus symlinks.
   - MCP, hooks, permissions, slash commands, configs, and Codex agents render or merge native formats and track ownership/content hashes.
   - Agent reconciliation preserves competing edits and does not use newest-file-wins.

4. **Store and schema compatibility**
   - Existing manifests, sidecars, audit files, migration behavior, home-relative paths, and `--state-dir` isolation must remain compatible.
   - A native app must not create a parallel store or silently migrate data to an Apple-only format.

5. **Security and privacy**
   - The current HTTP service is loopback-only and guards Host/Origin (`harness_asset_manager/api/guards.py`), but it is intentionally unauthenticated for same-user local tools.
   - MCP environment values, headers, and hook commands may contain secrets. They must not enter logs, crash reports, telemetry, or notification text.

6. **Finder-launched process discovery**
   - `HarnessKernelService` currently probes tools through `PATH`. A GUI app launched by Finder has a much smaller environment than a terminal.
   - Native discovery must explicitly check Apple Silicon and Intel Homebrew paths, common user-local paths, application bundles, and user-configured overrides rather than assuming a login-shell `PATH`.

## Recommended target architecture

### Application modules

Create an Xcode workspace with Swift Package targets:

- **HarnessAMApp** — app lifecycle, windows, commands, settings, dependency assembly.
- **HAMUI** — SwiftUI screens and reusable matrix/detail/editor components.
- **HAMDomain** — value types, errors, capability models, operation protocols.
- **HAMServiceClient** — generated or hand-wrapped OpenAPI client used by the first native releases.
- **HAMSidecar** — bundled-backend process supervision, health/version handshake, authentication token, and shutdown.
- **HAMCore** — eventual native implementations of inventory, reconciliation, and mutation services.
- **HAMStorage** — paths, portable paths, locking, atomic writes, manifests, audit journal, migrations.
- **HAMFormats** — Markdown/frontmatter and source-preserving JSON/JSONC/TOML/YAML document editing.
- **HAMHarnessKit** — catalog definitions, installation discovery, codecs, and per-family adapters.
- **HAMMarketplace** — URLSession clients, caching, package download/extraction.
- **HAMTestSupport** — fake homes, fixtures, golden files, and fault-injecting filesystem/network doubles.

Define one async boundary used by every view model:

```swift
protocol HarnessAMService: Sendable {
    func skills() async throws -> SkillsInventory
    func setSkill(_ ref: String, harness: HarnessID, enabled: Bool) async throws
    // Equivalent operations for every family.
}
```

Initially `HTTPHarnessAMService` implements the protocol through the bundled backend. Native domain ports later implement the same protocol without changing screens.

Use `actor` repositories for mutable caches and `@MainActor @Observable` view models for presentation. Avoid reproducing React query details in views; centralize refresh, cancellation, stale-data display, and mutation invalidation in repositories.

### Sidecar boundary for the first release

Bundle the current PyInstaller backend inside the signed `.app`, run it without the static React frontend, and communicate over a random loopback port.

Before shipping this boundary:

- Add a per-launch bearer token passed through an inherited pipe or environment variable and require it on every request.
- Bind only to `127.0.0.1`; never enable `--allow-remote` from the app.
- Add a version/capabilities handshake and refuse mismatched app/backend versions.
- Capture logs to the app's diagnostics location with secret redaction and bounded retention.
- Terminate the child on app exit and recover cleanly from crashes.
- Do not attach automatically to an arbitrary already-running unauthenticated daemon. Concurrent access to the same store is safe through existing locks.

Using the CLI as a command-per-action subprocess is not recommended as the primary boundary: it has higher startup cost, weaker typed error/cancellation behavior, and makes multi-query screens expensive. Keep it only as a fallback diagnostic path.

### Native macOS information architecture

Use `NavigationSplitView` for the main window:

- Overview
- Configs
- Permissions
- Agents
- Skills
- Slash Commands
- MCP Servers
- Hooks
- Marketplace
- Settings

Native conventions:

- Put refresh, add/import, search, status scope, and sort in the window toolbar.
- Use a reusable asset matrix backed by `NSTableView` through `NSViewRepresentable` if SwiftUI `Table` cannot support dynamic harness columns, keyboard selection, and horizontal performance reliably.
- Open selected asset details in an inspector (`inspector`) on supported macOS versions, with an AppKit split-view fallback if needed.
- Use sheets for create/edit workflows and alerts for destructive confirmation; do not model every web detail drawer as a modal.
- Use `Menu`/context menus for row actions, native multi-selection for bulk actions, token fields for tags, and `NSOpenPanel` plus drag-and-drop for Skill import.
- Add standard commands and shortcuts: Refresh (`⌘R`), Find (`⌘F`), New (`⌘N` where meaningful), Settings (`⌘,`), sidebar/inspector toggles, and Help links.
- Follow system appearance by default, with optional Light/Dark/System preference. Use semantic colors rather than porting CSS values directly.
- Preserve deep-link concepts with an internal `NavigationState` containing family, status, harness, tags, and selected asset. Add an `harnessam://` URL scheme only after navigation is stable.
- Treat accessibility labels, VoiceOver order, keyboard traversal, reduced motion, and high contrast as release requirements.

## Delivery phases

### Phase 0 — Freeze contracts and prove feasibility

1. Record all API operations and error codes from `frontend/src/api/openapi.json`.
2. Export representative fake-home fixtures from `tests/support/fake_home.py` for every family and harness.
3. Add golden before/after fixtures for JSON, JSONC, TOML, YAML, Markdown/frontmatter, symlink ownership, drift, conflicts, migrations, and audit redaction.
4. ~~Spike Swift packages for source-preserving TOML and YAML.~~ **Done — see
   [`spike-swift-source-preserving-config.md`](spike-swift-source-preserving-config.md).**
   Verdicts: **JSON/JSONC GO** (hand-written `JsoncDocument`, ~450 lines);
   **TOML GO only via a hand-written surgical engine** (~320 lines) — TOMLKit/toml++ destroys
   every comment, including on a no-op load/dump; **YAML NO-GO** — Yams/libyaml discards
   comments at tokenization and no `ruamel.yaml` equivalent exists in the Swift ecosystem.
   Read the report's "Review corrections" section before quoting its pass rates.
5. Decide the minimum macOS version after testing `NavigationSplitView`, inspector APIs, table behavior, and updater support. **(macOS-only; not started.)**
6. Produce a signed/notarized proof app that launches the bundled sidecar on both arm64 and x86_64. **(macOS-only; not started. Requires Apple Developer Program membership — allow lead time.)**

**Exit gate:** the app can read a fixture store, perform one harmless mutation through the sidecar, and produce exactly the same bytes as the current implementation.

**Gate status:** item 4 is closed; items 1–3 can proceed on any platform; items 5–6 and the exit
gate itself require macOS hardware and cannot be advanced on Linux. All spike results were
produced on Linux Swift 6.0.3 and carry two Darwin-specific re-validations (UTF-8 BOM handling in
`JSONSerialization`, and `NSNumber`/`CFBoolean` bridging in `ConfigValue`) — re-run the spike's
`swift test` on macOS as the first task there.

### Phase 1 — Native shell and read-only inventories

1. Set up Swift packages, dependency injection, sidecar supervision, OpenAPI client generation, error mapping, and diagnostics.
2. Implement the sidebar, toolbar, Overview, Settings, and read-only inventories for every family.
3. Implement shared loading, empty, stale, partial-error, tag/filter, and selection states.
4. Implement the reusable matrix and inspector foundations before family-specific polishing.
5. Refresh on launch, manual refresh, and app activation. Preserve current behavior: do not introduce a filesystem watcher that mutates state implicitly.

**Exit gate:** every current inventory and review count is visible natively and matches the web UI against the same fake home.

### Phase 2 — Mutation parity through the proven backend

Implement family workflows in risk order:

1. Tags/stars and Settings toggles.
2. Skills and Agents: adopt, create/edit, enable/disable, bulk operations, conflicts, delete.
3. Slash Commands: create/edit, sync, review, restore, and delete.
4. MCP: install, configuration parameters, enable/disable, availability, adoption, conflict source choice, reconcile, uninstall.
5. Hooks and Permissions: create, representability feedback, apply/remove, adoption, reconcile, delete.
6. Configs: capture, diff, enable/disable management, restore.
7. Marketplace: Skills and MCP install flows; CLI remains preview-only.

Every mutation must show precise partial failures and preserve current confirmation rules.

**Exit gate:** all 89 API operations used by the product have a native workflow or an explicitly documented non-UI/headless-only status; no normal workflow requires opening the browser UI.

### Phase 3 — macOS product integration

1. Add app menus, keyboard commands, Help, reveal-in-Finder/open-in-editor actions, drag-and-drop import, and notification policy.
2. Add optional menu-bar status only if it has a concrete use; avoid turning HAM into a background watcher by accident.
3. Sign nested executables, enable hardened runtime, notarize, staple, and package `.dmg`/`.zip` artifacts for arm64 and x86_64 (or a validated universal app).
4. Ship outside the Mac App Store initially. The App Sandbox conflicts with HAM's core job: reading/writing multiple hidden tool directories, creating symlinks, probing executables, and merging arbitrary config files. A sandboxed edition would require explicit security-scoped authorization for every root and still needs a separate feasibility review.
5. Keep the existing Homebrew CLI formula. Add a cask for the `.app` rather than replacing the CLI package.
6. Define update strategy: signed Sparkle feed or manual/Homebrew cask updates. Do not auto-update the sidecar independently from the app.

**Exit gate:** clean-machine install, launch, upgrade, rollback, and uninstall are tested on supported macOS versions and both CPU architectures.

### Phase 4 — Incremental all-Swift core

Port behind `HarnessAMService`; never let UI screens call the filesystem directly.

Recommended order:

1. `HAMStorage`: paths, migrations, portable paths, atomic writes, `flock`, hashing, audit journal.
2. Harness catalog and installation discovery.
3. Tags, settings, and read-only scanning.
4. Skills and Agents, including parsers, symlink ownership, binding ledger, and conflict preservation.
5. Slash Commands and rendered-file sync state.
6. Source-preserving config document engine. **Split by format — this is no longer one step.**
   - **JSON and JSONC**: port `JsoncDocument` (~450 lines of Swift, already written and tested
     in the spike). Ready.
   - **TOML**: port `TomlSurgicalEngine` (~320 lines, already written and tested). Close the two
     corpus gaps the review found first — `test_mutation_after_insertion_is_not_lost` and a
     malformed-document test for the surgical engine.
   - **YAML**: **stays in the sidecar.** A pure-Swift round-trip YAML engine is estimated at
     1,500–2,500 lines and carries high risk (indentation rules, flow/block styles, block-scalar
     chomping, anchors/aliases). Only Hermes (`~/.hermes/config.yaml`) binds YAML, so the blast
     radius of deferring this is one harness.
7. MCP, Hooks, Permissions, and Configs adapters/codecs.
8. Marketplace networking, caching, GitHub package acquisition, and availability probes.
9. Remove the sidecar only after cross-implementation parity has been green for at least one release cycle. **Note that full removal is now conditional:** while YAML editing stays in Python, the sidecar cannot be removed outright. Either accept a permanently reduced sidecar that serves YAML config writes only, or fund the 1,500–2,500 line Swift YAML engine as an explicit, separately-scoped decision.

For each slice, run the Python and Swift implementations against the same fixture home and compare:

- returned models and errors;
- all created, changed, and deleted paths;
- exact file bytes and symlink targets;
- audit events with secret fields excluded;
- behavior under malformed files, permission errors, partial fan-out failures, concurrent CLI access, and sync-conflict artifacts.

**Exit gate:** the bundled Python core is removable — or reduced to the YAML-only residue described
in step 9 — without changing the store, CLI interoperability, or user-visible behavior.

## Validation strategy

- Keep the current backend, integration, pressure, and frontend tests green while the sidecar is used.
- Generate Swift contract tests from OpenAPI examples and checked-in JSON fixtures.
- Port high-value Python tests first: `test_writer_round_trip.py`, `test_atomic.py`, drift/reconcile tests, cross-device arrival, path isolation, mutation audit, and each family adapter/mapper suite.
- Add XCTest unit tests for reducers/view models and codec/storage primitives.
- Add XCUITest coverage for navigation, filtering, matrix toggles, detail editing, conflict resolution, bulk actions, and destructive confirmations.
- Run end-to-end tests in temporary fake homes; never use the CI account's real harness directories.
- Run concurrency tests with the native app and `harnessam --state-dir ...` operating on the same fixture.
- Test Finder launch separately from terminal launch to catch `PATH`, environment, and file-permission differences.
- Require code signing/notarization verification and a no-network/no-telemetry assertion for local workflows.

## Main risks and mitigations

| Risk | Mitigation |
|---|---|
| Big-bang rewrite corrupts user configs | Ship SwiftUI over the existing core; port one domain at a time with byte-level differential tests. |
| ~~Swift format libraries lose comments/order~~ **Confirmed, not a risk — a finding.** | Measured in Phase 0: TOMLKit and Yams both destroy comments unconditionally. Mitigation is now the plan of record: port HAM's surgical span-patching strategy to Swift for JSON/JSONC/TOML, and retain YAML in the sidecar. |
| Sandbox blocks required filesystem access | Use Developer ID distribution without App Sandbox initially; document exactly what paths are accessed. |
| Bundled local HTTP API is callable by another process | Random port, per-launch token, loopback-only bind, version handshake, app-owned lifecycle. |
| Finder launch cannot find Homebrew/user CLIs | Implement deterministic native executable discovery and user-configurable overrides. |
| Native matrix performs poorly with dynamic columns | Prototype early; use `NSTableView` when SwiftUI `Table` is insufficient. |
| App and CLI write concurrently | Preserve existing advisory locks, atomic replacement, store schemas, and one-second invalidation expectations. |
| Secrets leak through native diagnostics | Structured redaction, no payload logging, opt-in diagnostics export, and tests using sentinel secrets. |
| Native and web products drift during migration | Treat OpenAPI and golden fixture behavior as the shared contract; declare one parity checklist per feature. |

## Definition of done

The native app is complete when it:

- provides every current day-to-day workflow without a browser;
- opens and mutates the existing `~/.harnessam` store safely;
- remains interoperable with the existing headless CLI;
- preserves comments, formatting, unknown keys, symlinks, conflicts, and audit privacy;
- supports all cataloged harnesses and current capability distinctions;
- is keyboard- and VoiceOver-usable;
- is signed, hardened, notarized, and upgrade-tested on supported Intel and Apple Silicon Macs;
- has no unauthenticated app-private network boundary; and
- can eventually remove the Python sidecar — or reduce it to the YAML-only residue — after
  differential parity proves the Swift core equivalent. A fully Python-free build additionally
  requires a Swift round-trip YAML engine that does not yet exist in the ecosystem.
