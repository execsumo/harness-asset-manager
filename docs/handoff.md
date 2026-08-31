# Handoff — native macOS Swift app, moving to Mac

**As of 2026-08-31.** Work continues on a Mac; everything below is on `main` and pushed.

## Where things stand

`docs/plan-native-macos-swift-app.md` is the plan. Phase 0 item 4 (the source-preserving
format spike) is **done**; everything else in Phase 0 is either portable prep work or blocked
on macOS hardware.

The spike lives in `spikes/swift-config-document/` with its report at
`docs/spike-swift-source-preserving-config.md`. Verdicts:

| Format | Verdict |
|---|---|
| JSON / JSONC | **GO** — hand-written `JsoncDocument`, ~450 lines, ported from the Python original |
| TOML | **GO only via `TomlSurgicalEngine`** (~320 lines). TOMLKit/toml++ destroys every comment, even on a no-op load/dump |
| YAML | **NO-GO** — Yams/libyaml drops comments at tokenization; no `ruamel.yaml` equivalent exists. Stays in the Python sidecar |

The plan has been amended to match: Phase 4 step 6 is split by format, step 9 and both exit
gates now say the sidecar can only be *reduced* to a YAML-only residue rather than removed,
and the "Swift format libraries lose comments" risk row is closed as a finding.

## First thing to do on the Mac

Re-run the spike suite. Every result was produced on **Linux Swift 6.0.3**, and two findings
rest on Foundation behavior that differs on Darwin, in code the spike itself wrote:

- **UTF-8 BOM in `JSONSerialization`** — Linux Foundation rejects a leading BOM; Darwin's
  behavior varies by SDK. `JsoncDocument` works around the Linux behavior and that workaround
  is unvalidated on macOS. The differential already shows this fixture diverging from Python
  (190 B vs 204 B) because Swift preserves the BOM Python drops.
- **`NSNumber` / `CFBoolean` bridging** — `ConfigValue` separates booleans from numbers with a
  `CFGetTypeID` check, which behaves differently under the Objective-C runtime.

```bash
cd spikes/swift-config-document && swift test        # expect 58/58
.venv/bin/python spikes/swift-config-document/differential_runner.py   # from repo root
```

## Known gaps in the spike

Close these before `TomlSurgicalEngine` is trusted in Phase 4 — the Swift TOML corpus is
smaller than the Python `TomlRoundTripTests` it claims parity with:

- `test_mutation_after_insertion_is_not_lost` — mutating a table inserted earlier in the same
  session. Behavioral, not cosmetic.
- `test_malformed_document_is_reported_not_silently_emptied` — exists for the TOMLKit tests but
  not for the surgical engine, which is the implementation that would actually ship.

Also note the surgical engine is byte-identical only for *untouched* documents; mutated
documents differ from Python by ±1 byte inside the rewritten region. That is within the
concession `config_document.py` already documents, but do not restate it as byte-identical.

## Prerequisites with lead time

- **Apple Developer Program membership** ($99/yr) — needed for the Developer ID signing and
  notarization in Phase 0 item 6. Not instant; start it before you need it.
- **Intel coverage decision.** The plan wants arm64 *and* x86_64. Universal binaries can be
  *built* on Apple Silicon, but *testing* the x86_64 path needs Intel hardware. Decide whether
  Intel is genuinely supported or quietly dropped, and write the answer into the plan.

## Still doable anywhere (Phase 0 items 1–3, none started)

1. Freeze the API surface: all operations and error codes from `frontend/src/api/openapi.json`
   (77 paths / 89 operations).
2. Export fake-home fixtures from `tests/support/fake_home.py` for every family × harness.
3. Golden before/after fixtures for every format, plus symlink ownership, drift, conflicts,
   migrations, and audit redaction.

## Repo state

- `main` carries the plan, the spike, the report, and these amendments.
- `spike/swift-config-document` is merged and can be deleted (locally and on `origin`).
- Swift toolchain on the Linux box: 6.0.3 via swiftly at `~/.local/bin/swift`. Not needed on
  the Mac, where Xcode supplies it.
- `DESIGN.md` in the working tree is an unrelated untracked color-theme file, not part of this.
