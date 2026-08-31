# Handoff — native macOS app cancelled; API bearer token added

**As of 2026-08-30.** Newest session on top.

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

## Known limitation — read this before claiming the API is protected

**The token is not a boundary against a same-user local process.** `GET /` is unauthenticated
and returns the token in the injected meta tag, so any local process does:

```
curl -s http://127.0.0.1:8000/ | grep ham-api-token
```

and has full API access. `test_frontend_index_html_injects_token_meta_tag` documents exactly
this, unauthenticated, as passing behaviour.

This is not fixable by hardening the delivery. A same-user process can read the runtime state
file (0600 is same-UID), the child's environment, and the served HTML. **Any secret the browser
can obtain, a same-user process can obtain.** The original motivation — stopping a misbehaving
or prompt-injected coding agent from deleting the deny rules that constrain it — needs OS-level
separation (a different UID, or a real sandbox), not a token.

What the token does buy:

1. Incidental and naive access now fails. An agent that blindly `curl`s `/api/permissions`
   gets a 401 instead of succeeding.
2. It is the prerequisite for any real boundary later.
3. It closes cross-origin browser access that the Origin guard alone did not cover on
   `--allow-remote`.

What it does **not** buy: protection on the tailnet. Any device that can reach the port can
`GET /` and read the token out of the HTML, exactly as a local process can. **If the tailnet
deployment is still in use, treat it as unauthenticated.** Closing that needs the HTML itself
gated — e.g. a one-time token paste from `harnessam token` held in sessionStorage, or leaning
on Tailscale's own device identity headers. Neither is built.

## Next steps

- Decide whether the tailnet front door stays. If it does, gate `index.html`.
- Consider replacing the all-or-nothing `--allow-remote` with a `--trusted-host <hostname>`
  that adds one name to the Host/Origin allowlist while keeping both guards on. That is a
  better fit for `tailscale serve` than disabling the guards wholesale.
- A launchd plist would fix the other real gripe: a hand-launched server does not survive a
  reboot, and there is no Dock or Spotlight entry.

## Repo state

- `main` carries the cancelled plan, the spike, and its report.
- `feat/api-bearer-token` carries the token work. Not merged to `main`.
- `spike/swift-config-document` is merged and can be deleted locally and on `origin`.
