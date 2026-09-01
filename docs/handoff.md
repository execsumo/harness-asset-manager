# Handoff — agent contract fields shipped; agent creation flow planned

**As of 2026-09-01.** Newest session on top.

## Shipped (uncommitted, working tree on `main`): four new agent contract fields

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

## Plan: shore up the agent creation flow

### The problem

`CreateAgentDialog` is the only way to create an agent — `AgentsInUsePage.tsx:440`, opened from
the header **Add Agent** (`:308`) and the empty-state **Add Agent** (`:432`). It is well behind
what an agent now is.

- **A created agent is bound to zero harnesses.** `create_agent` (`api/routers/agents.py:103`)
  only writes the store file. The reconciler cannot rescue it either: `reconcile()` iterates the
  *ledger* and returns immediately when it is empty (`application/agents/reconcile.py:77-79`),
  and per-slug it requires drift against an existing harness file. A brand-new agent has neither,
  so `_enable_defaults` is unreachable for it — **even when auto-adopt defaults are configured**.
  "Add Agent" therefore produces a row that is disabled everywhere.
- **It can only produce a four-key agent.** `CreateAgentRequest` accepts `skills`, `model`,
  `effort` and now the four fields above, but the dialog sends only name/description/prompt/tools
  (`CreateAgentDialog.tsx:45-50`). Every agent is born bare and must immediately be edited.
- **Name errors only surface after a round trip.** `slugify` runs server-side, so `"???"` returns
  *"cannot derive a file name"* and a duplicate returns a 409, both after a request.
- **No component tests** on the sole creation entry point.
- **Two small inconsistencies:** description is not required (the harness reads it to decide when
  to invoke the agent), and `Dialog.Root` (`:59`) passes `onOpenChange` through unguarded, so
  Escape closes the dialog mid-create even though Cancel and the X are correctly disabled.

### Decisions

1. **The harness picker preselects `autoAdoptHarnesses.agents`, and nothing when that is empty.**
   This is one rule, not two: `AutoAdoptStore.is_enabled(family)` is literally
   `bool(default_harnesses()[family])` (`application/settings/auto_adopt.py:44-51`), so
   "auto-adopt is off" *is* "the configured list is empty". Do not add a branch on an
   `autoAdopt[family]` boolean — that map is retained only as the family catalog for API
   compatibility and is derived from the same list.
2. **Binding happens server-side, inside the create request.** Add `harnesses: list[str]` to
   `CreateAgentRequest`. This matches slash-commands, which sends `targets` in the create body
   (`useSlashCommandsController.ts:194`). *Rejected:* a client-side two-step of `createAgent`
   then `setAgentHarnesses`. A failed second call leaves an agent the user did not ask for, bound
   to nothing, with no undo — the exact failure this work exists to remove.
3. **Reuse the structured editor's controls and constants.** Same field order, same pickers,
   importing `COLOR_VALUES` / `ISOLATION_VALUES` / `ALLOWED_SUBAGENTS_VALUES` / `MAX_TURNS_DEFAULT`
   from `features/agents/api/types.ts` and reusing `FrontmatterSegmentedField` and
   `AgentSkillsFieldEditor`. A second set of pickers would drift from the first.
4. **`EditAgentDialog.tsx` is deleted.** It is exported and referenced by nothing — editing moved
   into the detail sheet. It still models an agent as name/description/prompt/tools, so leaving it
   invites someone to rewire a dialog that silently cannot express most of the contract.

### Work items

**A — Backend: bind at create.**
- `CreateAgentRequest.harnesses: list[str] = Field(default_factory=list)` in `api/schemas/agents.py`.
- In `create_agent` (`api/routers/agents.py:103`), after `store.create`, call
  `container.agents_mutations.set_harnesses(agent.slug, body.harnesses)` when the list is non-empty.
- `AgentDetailResponse.failed` is skills-shaped (`AutoEnableFailureResponse`: skillRef/harness/error).
  Do **not** overload it. Add `harnessFailures: list[AgentMutationFailureResponse] = []` and set
  `ok=False` when it is non-empty.
- An unknown or unsupported harness id must not 500; `set_harnesses` already returns
  `(succeeded, failed)` and that contract must hold through the router.
- Tests in `tests/unit/test_agents.py`: creates with defaults, creates with an empty list, creates
  with an unsupported harness (partial success surfaced, agent still created).

**B — Frontend: rewrite `CreateAgentDialog`.**
- Read `useSettingsQuery()` via `features/settings/public` for `autoAdoptHarnesses.agents`
  (settings already imports from `agents/public`, so this direction is the sanctioned pattern).
  Harness labels, logos and `installed` come from the agents inventory `columns`.
- Model the harness fieldset on `SlashCommandFormDialog.tsx:159-190`, reusing `DetailBindingIdentity`.
- Add the contract fields in `AGENT_CONTRACT_KEYS` order with the controls from decision 3.
- Inline name validation: slugify client-side, block an empty slug and a collision against the
  inventory before submit, in the shape of `SlashCommandFormDialog.tsx:71-74`.
- Require description in `canSubmit`; guard `onOpenChange` while pending.
- Judgment call left to the implementer: the dialog roughly triples in height, so it may need the
  scroll or two-column treatment the detail sheet uses.

**C — Frontend: tests for the dialog.** Preselection from configured defaults; nothing preselected
when the list is empty; the create body carries the contract fields and the selected harnesses;
duplicate-name blocked before any fetch; partial harness failure surfaced rather than swallowed.

**D — Delete `EditAgentDialog.tsx`.** Its own commit.

### What to delegate

**Delegate A + B + C to `agy` as one brief on one short-lived branch** (`feat/agent-create-flow`
off `main`). They share the create-request shape; splitting A from B across panes creates a
cross-pane dependency and a stale-contract window for no gain.

The brief must state: the branch and that it is short-lived per the working agreement; logical
commits and a push; **no merge to `main` without review**; the definition of done below; and a
**mandatory** pressure test at `scripts/pressure_test_agent_create.py` in the style of
`scripts/pressure_test_agent_skills.py`, driving `AppTestHarness` end to end — create with
defaults, create with none, create against an uninstalled harness.

**Keep D and the verification pass in the driving session.** D is a deletion, which should be a
reviewed commit of its own rather than buried in a feature branch. Per the working agreement,
agy's work is independently verified here — re-run the suite and spot-check the diff; do not
relay its pass counts on faith.

### Definition of done

```
npm run typecheck
bash scripts/test_backend.sh
npm test
npm run build
npm run codegen:check     # the create-request shape changes the OpenAPI schema
python3 scripts/pressure_test_agent_create.py
```

`codegen:check` is the one most likely to be forgotten and will fail the branch if `generated.ts`
and `openapi.json` are not regenerated. Also confirm by hand: creating an agent with **no**
harnesses selected still succeeds and reports cleanly.

### Open question for the next session

Preselecting nothing when auto-adopt is off means a user who has never opened Settings gets
"create an agent bound to nothing" as the default path — which is the complaint that motivated
this work. The rule is right (silently binding harnesses the user never chose is worse), but the
dialog should probably say so: an inline note when the selection is empty, pointing at Settings →
auto-adopt defaults. Not decided; do not invent copy for it without asking.

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
