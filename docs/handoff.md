# Handoff — native macOS app cancelled; API bearer token added

**As of 2026-08-31.** Newest session on top.

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
