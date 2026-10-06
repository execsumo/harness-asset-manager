# harness-asset-manager — working agreement

This is **our fork** of harness-asset-manager. Read this before doing any git or delegation work.

## Remotes

- `origin` → `execsumo/harness-asset-manager` — **standalone repository**. This is where we develop and ship.

## Branch strategy — fork `main` is the cumulative trunk

`fork/main` is the single line where everything accumulates. It only grows; it always
contains every shipped feature (agy harness, light mode, hooks, …). **Run the app off `main`.**

- New work = a **short-lived** branch off `main` → merge **back into `main`** when done → delete the branch.
- Do **not** keep long-lived feature branches. They drift from `main` and from the running
  instance (this is how light mode "disappeared" once — the checkout was parked on a side branch).
- Commit/push to `main` or a short-lived feature branch. Never develop on a throwaway extract branch.
- Land features into `main` promptly so there is nothing to "keep cumulative" — it just is.

## Contributing upstream (mode-io) — opt-in and isolated

**Default: don't.** The fork is a complete product on its own. Only extract an upstream PR when
there is a real reason (you want mode-io to maintain/ship it). It is occasional, not per-feature.

When you do, **never switch this checkout to an upstream-extract branch** — that strips fork-only
features (light mode, etc.) and breaks the running instance. Do it in a separate worktree so the
main checkout never moves:

```bash
git worktree add ../harness-asset-manager-upstream origin/main
cd ../harness-asset-manager-upstream
git cherry-pick <only the commits upstream should get>   # keep it a clean subset
git push fork <extract-branch>
gh pr create --repo mode-io/harness-asset-manager --base main --head execsumo:<extract-branch>
cd - && git worktree remove ../harness-asset-manager-upstream
```

Keep the upstream PR a focused subset; do not bundle unrelated fork features into it.

## Running the app

Serve/run from `main`. After switching branches or building on a different branch, rebuild so
`frontend/dist` matches the source, then hard-refresh / restart the instance:

```bash
npm run build
```

### Serving over a tailnet

Where the app is published to a tailnet, it stays on its loopback port and `tailscale serve`
terminates TLS in front of it. Ports and hostnames are a property of the host, not of this
repo, and are never checked in.

**This is now automatic.** Every `harnessam start`/`serve` best-effort applies the
`tailscale serve --bg` mapping itself on launch (when the `tailscale` CLI and daemon are
reachable — silently skipped otherwise) and tears down that one port again on clean shutdown
(`--https=<port> off`, never a full `serve reset`, so other apps this host proxies on other
ports are untouched). Disable with `--no-tailnet`; the published port defaults to `7443` and
is overridden with `--tailnet-port` or `$HAM_TAILNET_PORT`. `scripts/serve-tailnet.sh` still
exists as the manual re-apply path for an instance that was launched by hand with
`--no-tailnet`, or after tailscaled state loss.

The app also auto-detects this device's own Tailscale hostname and trusts it for `Host`/`Origin`
with **no flag needed** — just `harnessam start`. Serve forwards the tailnet hostname in `Host`,
which the loopback guard would otherwise reject; auto-detection (`runtime/tailscale.py`, a
best-effort `tailscale status --json` read) fills the same role `--trusted-host` does, without
disabling either guard. Never use `--allow-remote` here — it "fixes" the hostname mismatch by
dropping the Host and Origin guards entirely. Override or add a hostname with `--trusted-host`
or `HARNESS_ASSET_MANAGER_TRUSTED_HOSTS`; either takes priority over auto-detection. Remote
requests authenticate on the `Tailscale-User-Login` header Serve injects and strips from
incoming requests (so it cannot be forged), which is what keeps the tailnet front door
paste-free.

If the app is killed with SIGKILL (not a clean `harnessam stop`/SIGTERM), the teardown never
runs and the mapping is left pointing at a dead backend until the app is relaunched or
`scripts/serve-tailnet.sh` is re-applied.

## Delegating development (herdr + agy)

We work inside **herdr** (`HERDR_ENV=1`) and delegate substantial implementation to the **`agy`**
agent in a sibling pane.

**Read the `delegate` skill before orchestrating or handing work to another agent.** It owns the
whole workflow — spawning the delegate with a reverse channel, writing the spec, monitoring by
exception, and verifying before integration — and it has the tested helpers. Do not hand-roll
pane splits, escalation, or monitor loops from memory; the mechanics that used to live in this
section were stale and incomplete. Use the `ogulcancelik--herdr` skill for raw herdr operations
that fall outside a delegation.

Three project-specific requirements to carry into every brief:

- **Branch discipline**, per the strategy above: a short-lived branch off `main`, logical commits,
  push — and **no merge to `main` without review**.
- **A mandatory pressure test** plus the full validation suite below as the Definition of Done.
- **Always independently verify** before reporting work done — re-run the validation suite yourself
  and spot-check the diff. Do not relay a delegate's pass counts on faith.

## Validation suite

Run the whole thing with one command — it mirrors what CI enforces, in CI's order:

```bash
npm run validate
```

That is equivalent to:

```bash
npm run lint:backend          # ruff
npm run typecheck:backend     # pyright
npm run audit:backend         # pip-audit
bash scripts/test_backend.sh
npm run audit:check           # npm dependency audit
npm run version:sync          # VERSION files agree
npm run release-targets:check
npm run lint:frontend
npm run typecheck
npm run codegen:check         # OpenAPI client is not stale
npm run test:coverage         # vitest + the coverage ratchet
npm run build
```

**That list is enforced, not aspirational.**
`tests/unit/test_validation_suite_parity.py` parses `.github/workflows/ci.yml` and
fails if any step in `backend-compat` or `frontend-validate` is missing from
`validate`. Add a step to CI without adding it here and the parity test names the
command it would otherwise only have caught after a push.

The ratchet exists because this suite drifted from CI twice. First `lint:backend`
was missing, and an import-order nit failed CI before pyright, pip-audit, or the
backend tests ever ran — three commits, one of them a release, reached `main` red.
Then `codegen:check` was missing, and a new endpoint shipped with a stale generated
OpenAPI client. Both times `validate` passed locally and CI did not.
`npm run lint:backend:fix` auto-fixes the whole ruff class of finding.

Two notes on running it locally. `audit:backend` and `audit:check` hit the network,
so the suite needs connectivity. And `codegen:check` compares the working tree
against the index, so if it regenerates the client you have uncommitted codegen
output to stage — that is the signal working, not a flake.

CI no longer lets one failing check hide the others — every validation step runs
and reports independently once dependencies install — but a red check is still a
red check. Run this before you push.
