# Handoff — agent creation flow shipped

**As of 2026-09-01.** Newest session on top.

## Shipped: creating an agent now produces a complete, bound agent

`CreateAgentDialog` is still the only way to create an agent, but it is no longer behind what
an agent is. It expresses the whole contract, binds harnesses in the same request, and rejects
a bad name before it costs a round trip. Branch `feat/agent-create-flow`, merged to `main`.

**Binding happens server-side, inside the create request.** `CreateAgentRequest.harnesses`
carries the selection and `create_agent` (`api/routers/agents.py:103`) applies it after
`store.create`. The rejected alternative was a client-side `createAgent` then
`setAgentHarnesses`: a failed second call leaves an agent the user did not ask for, bound to
nothing, with no undo — the exact failure this work existed to remove. This also closes the
hole where the reconciler could not rescue a new agent: `reconcile()` iterates the *ledger*,
returns immediately when it is empty, and per-slug needs drift against an existing harness
file, so `_enable_defaults` was unreachable for a brand-new agent even with auto-adopt
configured.

**Partial success is a success.** `AgentMutations.partition_harnesses` splits the requested
ids into the ones an adapter can carry and the ones it cannot, because `set_harnesses`
validates up front and *raises* on the first unknown id — right when correcting an existing
binding set, wrong at creation, where the agent file already exists by the time the id is
inspected. The unknown ones and any per-target `MutationError` land together in
`AgentDetailResponse.harnessFailures` with `ok=False`. That field is separate from `failed`
on purpose: `failed` is `AutoEnableFailureResponse` (skillRef/harness/error) and is
skills-shaped; overloading it would have conflated two different failures.

**The empty-selection rule, and the note that makes it honest.** The picker preselects
`autoAdoptHarnesses.agents` and nothing when that list is empty. This is one rule, not two:
`AutoAdoptStore.is_enabled(family)` is literally `bool(default_harnesses()[family])`
(`application/settings/auto_adopt.py:44-51`), so "auto-adopt is off" *is* "the configured
list is empty" — do not add a branch on an `autoAdopt[family]` boolean, which is retained
only as the family catalog for API compatibility and is derived from the same list.

The previous session left open what to do about the resulting default path: a user who has
never opened Settings would be steered into creating an agent bound to nothing, which is the
complaint that motivated the work. **Resolved:** the dialog says so, inline, whenever the
selection is empty — *"This agent won't be available in any harness yet. Pick one above, or
set defaults in Settings → Auto-adopt."* It is a hint, not an error. Creating an unbound
agent stays legitimate and still succeeds cleanly; the rule that we never silently bind a
harness the user did not choose is unchanged.

**Two smaller things the dialog now gets right.** `slugify` is mirrored client-side from
`application/agents/store.py:19`, so an unslugifiable name and a duplicate are both caught
before submit rather than coming back as *"cannot derive a file name"* or a 409. Description
is required (the harness reads it to decide when to invoke the agent), and `onOpenChange` is
guarded while pending, so Escape can no longer close the dialog mid-create — Cancel and the X
were already disabled.

The contract fields reuse the structured editor's controls and constants rather than a second
set that would drift: `AGENT_CONTRACT_KEYS` order, `FrontmatterSegmentedField`,
`AgentSkillsFieldEditor`, and `COLOR_VALUES` / `EFFORT_VALUES` / `ISOLATION_VALUES` /
`ALLOWED_SUBAGENTS_VALUES` / `MAX_TURNS_DEFAULT` from `features/agents/api/types.ts`.
`max_turns` remains a placeholder and is never prefilled, and every key the user leaves unset
is omitted from the request rather than sent as `""`.

`EditAgentDialog.tsx` is deleted (`30a7fd9`, its own commit). It was exported and referenced
by nothing, and still modelled an agent as name/description/prompt/tools. `AgentSummaryResponse`
went with it in the same spirit: `createAgent` returns `AgentDetailDto` now, which is what the
router's `response_model` always said, and nothing else referenced the type.

Coverage: `AgentCreateHarnessBindingTests` (`tests/unit/test_agents.py`),
`CreateAgentDialog.test.tsx`, and `scripts/pressure_test_agent_create.py`, which drives
`AppTestHarness` end to end and asserts on the files and symlinks actually written, not just
on response bodies.

### If you touch this next

- `npm run codegen:check` is the step most likely to be forgotten — the create-request and
  detail-response shapes are in the OpenAPI schema, and stale `generated.ts` / `openapi.json`
  will fail the branch.
- `partition_harnesses` exists for creation specifically. Do not reroute the
  `PUT /agents/{ref}/harnesses` endpoint through it: raising on an unknown id is the right
  behaviour there, because nothing has been written yet and the caller can simply retry.

---

*Everything below is the earlier 2026-09-01 session — the contract fields this flow now creates.*

## Shipped: four new agent contract fields

`color`, `max_turns`, `allowed_subagents`, and `isolation` are now real agent contract
fields, threaded parser → store → mutations → inventory → API → structured editor, rather
than free-form rows in the "other frontmatter" channel.

`CONTRACT_KEYS` (`application/agents/model.py`) is the single source of truth for both the
render order and the editor's field order, and it now reads as a progression: identity
(`name`, `description`, `color`) → which model runs it (`model`, `effort`) → what it may
reach for (`tools`, `skills`, `allowed_subagents`) → the envelope it runs in (`max_turns`,
`isolation`). `ContractKeyParityTests` pins the TypeScript mirror, and its vocabulary check
was generalized to cover every mirrored tuple rather than just `EFFORT_VALUES`.

Three decisions worth not re-litigating:

- **Every fixed-vocabulary control has an explicit "unset" state.** `FrontmatterSegmentedField`
  renders `Unset · true · false`, not a two-state switch. A key that is absent from the file
  is a third state; a plain toggle would have to invent a value for it and write that value on
  the next save.
- **`max_turns: 30` is a placeholder, never prefilled.** Writing 30 into every agent file that
  never asked for it converts an implicit harness default into an explicit, now-frozen setting.
- **`allowed_subagents` and `max_turns` round-trip as a real YAML bool and int.**
  `parser._optional_bool_str` exists because `str(True)` is `"True"` — a value neither the file
  nor the picker ever produces.

Fixed along the way: `FrontmatterEditor` wrapped every field in a `<label>`, which handed all
three buttons of a segmented group the same accessible name (`"Allowed Subagents Allowed
Subagents"`). Fields rendering a group now opt out via `wrapInLabel: false` and name themselves.

Suite green: typecheck, backend 740 + 257, frontend 435, build. `npm run codegen:openapi` was
re-run. The two `eslint` errors in `frontend/src/api/http.test.ts` are pre-existing and unrelated.

---

*Everything below is the 2026-08-31 session — native macOS app cancelled; API bearer token added.*

## Decision: the native macOS app is cancelled

`docs/plan-native-macos-swift-app.md` is **not being built**. The plan and the Phase 0 spike
stay in the repo as the evidence for the decision, not as live work. Do not resume Phases 1–4
without revisiting the reasoning below.

Why:

- **The Phase 0 spike killed it.** It set out to prove Swift could do source-preserving config
  editing and came back with JSON/JSONC yes, TOML only via a hand-written ~320-line surgical
  engine, and **YAML not at all** — Yams/libyaml discards comments at tokenization and no
  `ruamel.yaml` equivalent exists. That is one subsystem out of roughly ten, already failing a
  third of the way through, for something Python gets from two dependencies.
- **The value is in the adapter matrix, not the UI.** Six families × seven harnesses, and the
  product is the accumulated edge cases — Cursor's single-token `Shell()`, Codex's TOML profiles
  having no command-prefix concept, verbatim-block YAML round-tripping, "reads must not write"
  in `SkillsQueryService`, `flock` coexistence with the CLI, drift auto-repair. ~20k LOC of
  tests encode those. A rewrite re-earns every one of those bugs, and Swift's type system does
  not help — they are the semantics of other people's config files.
- **The usual reason to go native is unavailable.** App Sandbox is incompatible with writing
  into `~/.claude`, `~/.codex`, `~/.cursor`, `~/.gemini` and creating symlinks, so there is no
  Mac App Store route either way. Native buys UX polish, not distribution or capability.
- **Cost nobody had priced:** ~30k LOC of hand-written React thrown away and rebuilt in SwiftUI.

If the browser tab is the actual complaint, the cheap answer the plan never considered is a
WKWebView shell around the existing SPA — signed `.app`, Dock icon, native menus, days of work,
frontend kept. That option remains open and unbuilt.

The spike itself (`spikes/swift-config-document/`, report at
`docs/spike-swift-source-preserving-config.md`) is still worth keeping: its JSON/JSONC and TOML
engines are real, tested code, and its findings are the record of why this was stopped.

## Shipped: per-launch API bearer token

Branch `feat/api-bearer-token`. This was lifted out of the cancelled plan's sidecar security
section — it was worth doing on its own.

**Before:** the API had no authentication of any kind. `LoopbackOnlyMiddleware` was the only
gate and it explicitly trusts every non-browser local process. `--allow-remote` short-circuits
*both* the Host and Origin checks (`guards.py:61`), so the documented tailnet deployment ran
with no guard at all.

**Now:** `ApiTokenMiddleware` (`api/guards.py`) requires `Authorization: Bearer <token>` on
every `/api/*` request except `/api/health`.

- Token is `secrets.token_urlsafe(32)` per launch, or `HARNESSAM_API_TOKEN` if set. `start`
  generates it in the parent and passes it to the child through the environment.
- The middleware is **deliberately separate from `LoopbackOnlyMiddleware`** and sits inside it,
  so `--allow-remote` cannot bypass the token. `test_8_middleware_ordering_is_pinned` exists to
  stop a later reorder from silently undoing that.
- 401 + `WWW-Authenticate: Bearer` via a new `_reject_unauthorized`; the existing 403 host/origin
  path is untouched.
- `/api/health` is exempt because `wait_for_health` (`runtime/startup.py:32`) probes it from
  `start_command` before runtime state exists. Accepted cost: health discloses `homeDir`
  (username) and harness install state.
- Browser delivery injects `<meta name="ham-api-token">` into the served `index.html`.
  Dev mode uses `VITE_API_TOKEN` (wired in `vite.config.ts`).
- `RuntimeState` carries the token; the state file is written 0600 and read with
  `payload.get("token")` so a stale file degrades to "no token" rather than "not running".
- `harnessam token` prints the token for curl/script use. It only covers `start`-launched
  instances — a bare `serve` writes no runtime state. There is deliberately no `--no-auth`.

## Auth model — what is and is not defended

A request to `/api/*` (except `/api/health`) is authenticated by **any one** of:

1. **A genuine local client** — loopback peer *and* a loopback `Host`.
2. **`Tailscale-User-Login`** present, injected by `tailscale serve`.
3. **`Authorization: Bearer <token>`** matching the stored token.

**The `Host` half of rule 1 is load-bearing.** `tailscale serve` proxies to 127.0.0.1, so
tailnet traffic arrives with a loopback peer exactly like a local client. Trusting the peer
alone lets every device on the tailnet through unauthenticated and makes rules 2 and 3
unreachable. That bug shipped in `db5240f` and is fixed in `f0e2d0d`;
`test_6_serve_proxied_traffic_is_not_trusted_as_a_loopback_client` pins it and fails with
`200 != 401` against the broken version. Note the other remote tests use a synthetic
non-loopback peer, which the real deployment never produces — that is why the suite was green
while the front door was open.

Remote auth is paste-free because Serve **strips** `Tailscale-User-Login` from incoming
requests before injecting its own, so a tailnet client cannot forge it
(<https://tailscale.com/docs/features/tailscale-serve>, "Identity headers"). Funnel traffic
gets no identity headers; we never use Funnel.

**Same-user local processes are deliberately trusted and not defended.** They can read the
token file, the child's environment, and anything the browser can read — any secret the browser
can obtain, a same-user process can obtain. Constraining a local coding agent needs OS-level
separation, not a token. The boundary this enforces is the remote one, which was previously
wide open.

## Tailnet deployment

`harnessam start`/`serve` now auto-detects this device's own Tailscale hostname
(`runtime/tailscale.detect_tailnet_dns_name`, a best-effort `tailscale status --json` read) and
trusts it for Host/Origin with **no flag required** — `resolved_trusted_hosts` in `cli/main.py`
only falls back to detection when neither `--trusted-host` nor `HARNESS_ASSET_MANAGER_TRUSTED_HOSTS`
is set. Detection never raises and only ever widens the allowlist.

**Do not use `--allow-remote`** — it disables the Host and Origin guards wholesale to work
around a hostname mismatch that auto-detection (or an explicit `--trusted-host`) solves
precisely. `scripts/serve-tailnet.sh` derives the tailnet name the same way and verifies the
guard actually passes before pointing Serve at the backend.

The token is now persistent in `~/.harnessam` (0600) rather than per-launch, so `harnessam
token` works for `serve` as well as `start`, and `harnessam token --rotate` cycles it.

## Next steps

- A launchd plist: a hand-launched server does not survive a reboot, and there is no Dock or
  Spotlight entry.
- `tailscale serve status` reported no config as of this session — the front door needs
  re-applying via `scripts/serve-tailnet.sh` once the app runs with `--trusted-host`.

## Repo state

- `main` carries the cancelled plan, the spike, and its report.
- `feat/api-bearer-token` carries the token and auth work. Not merged to `main`.
- `spike/swift-config-document` is merged and can be deleted locally and on `origin`.
