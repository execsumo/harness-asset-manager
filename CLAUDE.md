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
terminates TLS in front of it. That mapping lives in tailscaled's own state and survives
reboots, so it needs no boot-time step — and it is per-machine, never checked in. Ports and
hostnames are therefore a property of the host, not of this repo.

`scripts/serve-tailnet.sh` applies or re-applies the mapping — after a tailscaled state loss,
or to move the front door — reading `HAM_TAILNET_PORT` (default `7443`) and `HAM_BACKEND_PORT`
(default `8000`) from the environment. It is idempotent and **never deletes mappings**: a host
usually proxies unrelated apps on other ports, and `tailscale serve reset` would take them all
out. To retire a port, run the `tailscale serve --https=<port> off` line the script prints.

If the app was launched by hand (`nohup … serve --allow-remote`) rather than by a supervisor,
it does **not** survive a reboot, and the front door will proxy nothing until it is relaunched.

## Delegating development (herdr + agy)

We work inside **herdr** (`HERDR_ENV=1`) — use the `ogulcancelik--herdr` skill. Delegate
substantial implementation to the **`agy`** agent running in another pane:

- Check for an agy pane with `herdr pane list`. If one exists, send the brief with
  `herdr pane run <agy-pane-id> "<instruction>"`.
- **If no agy pane exists, create one**: split a pane (`herdr pane split <pane> --direction right --no-focus`)
  and run `agy` in it, then delegate to it.
- Give agy a **complete written brief** (a `/tmp/<task>.md` file works well, then point agy at it):
  the task, the branch to use (short-lived off `main`, per the strategy above), git discipline
  (logical commits, push, **no merge to main without review**), and a **mandatory** pressure-test
  plus the full validation suite.
- **Monitor by exception.** Watch agy's herdr `agent_status`: `blocked` → grant the permission or
  answer; `idle`/`done` are unreliable instantaneously (agy flaps and reports `done` while waiting
  on its own subprocess) — only act on **sustained** quiescence, and **read the pane to confirm it
  actually finished** before trusting it.
- **Always independently verify agy's work** before reporting it done — re-run the validation suite
  yourself and spot-check the diff. Do not relay agy's pass counts on faith.

## Validation suite

```bash
npm run typecheck
bash scripts/test_backend.sh
npm test
npm run build
```

<!-- rtk-instructions v2 -->
# RTK (Rust Token Killer) - Token-Optimized Commands

## Golden Rule

**Always prefix commands with `rtk`**. If RTK has a dedicated filter, it uses it. If not, it passes through unchanged. This means RTK is always safe to use.

**Important**: Even in command chains with `&&`, use `rtk`:
```bash
# ❌ Wrong
git add . && git commit -m "msg" && git push

# ✅ Correct
rtk git add . && rtk git commit -m "msg" && rtk git push
```

## RTK Commands by Workflow

### Build & Compile (80-90% savings)
```bash
rtk cargo build         # Cargo build output
rtk cargo check         # Cargo check output
rtk cargo clippy        # Clippy warnings grouped by file (80%)
rtk tsc                 # TypeScript errors grouped by file/code (83%)
rtk lint                # ESLint/Biome violations grouped (84%)
rtk prettier --check    # Files needing format only (70%)
rtk next build          # Next.js build with route metrics (87%)
```

### Test (60-99% savings)
```bash
rtk cargo test          # Cargo test failures only (90%)
rtk go test             # Go test failures only (90%)
rtk jest                # Jest failures only (99.5%)
rtk vitest              # Vitest failures only (99.5%)
rtk playwright test     # Playwright failures only (94%)
rtk pytest              # Python test failures only (90%)
rtk rake test           # Ruby test failures only (90%)
rtk rspec               # RSpec test failures only (60%)
rtk test <cmd>          # Generic test wrapper - failures only
```

### Git (59-80% savings)
```bash
rtk git status          # Compact status
rtk git log             # Compact log (works with all git flags)
rtk git diff            # Compact diff (80%)
rtk git show            # Compact show (80%)
rtk git add             # Ultra-compact confirmations (59%)
rtk git commit          # Ultra-compact confirmations (59%)
rtk git push            # Ultra-compact confirmations
rtk git pull            # Ultra-compact confirmations
rtk git branch          # Compact branch list
rtk git fetch           # Compact fetch
rtk git stash           # Compact stash
rtk git worktree        # Compact worktree
```

Note: Git passthrough works for ALL subcommands, even those not explicitly listed.

### GitHub (26-87% savings)
```bash
rtk gh pr view <num>    # Compact PR view (87%)
rtk gh pr checks        # Compact PR checks (79%)
rtk gh run list         # Compact workflow runs (82%)
rtk gh issue list       # Compact issue list (80%)
rtk gh api              # Compact API responses (26%)
```

### JavaScript/TypeScript Tooling (70-90% savings)
```bash
rtk pnpm list           # Compact dependency tree (70%)
rtk pnpm outdated       # Compact outdated packages (80%)
rtk pnpm install        # Compact install output (90%)
rtk npm run <script>    # Compact npm script output
rtk npx <cmd>           # Compact npx command output
rtk prisma              # Prisma without ASCII art (88%)
rtk uv run <cmd>        # Compact uv project command output
```

### Files & Search (60-75% savings)
```bash
rtk ls <path>           # Tree format, compact (65%)
rtk read <file>         # Code reading with filtering (60%)
rtk grep <pattern>      # Search grouped by file (75%). Format flags (-c, -l, -L, -o, -Z) run raw.
rtk find <pattern>      # Find grouped by directory (70%)
```

### Analysis & Debug (70-90% savings)
```bash
rtk err <cmd>           # Filter errors only from any command
rtk log <file>          # Deduplicated logs with counts
rtk json <file>         # JSON structure without values
rtk deps                # Dependency overview
rtk env                 # Environment variables compact
rtk summary <cmd>       # Smart summary of command output
rtk diff                # Ultra-compact diffs
```

### Infrastructure (85% savings)
```bash
rtk docker ps           # Compact container list
rtk docker images       # Compact image list
rtk docker logs <c>     # Deduplicated logs
rtk kubectl get         # Compact resource list
rtk kubectl logs        # Deduplicated pod logs
```

### Network (65-70% savings)
```bash
rtk curl <url>          # Compact HTTP responses (70%)
rtk wget <url>          # Compact download output (65%)
```

### Meta Commands
```bash
rtk gain                # View token savings statistics
rtk gain --history      # View command history with savings
rtk discover            # Analyze Claude Code sessions for missed RTK usage
rtk proxy <cmd>         # Run command without filtering (for debugging)
rtk init                # Add RTK instructions to CLAUDE.md
rtk init --global       # Add RTK to ~/.claude/CLAUDE.md
```

## Token Savings Overview

| Category | Commands | Typical Savings |
|----------|----------|-----------------|
| Tests | vitest, playwright, cargo test | 90-99% |
| Build | next, tsc, lint, prettier | 70-87% |
| Git | status, log, diff, add, commit | 59-80% |
| GitHub | gh pr, gh run, gh issue | 26-87% |
| Package Managers | pnpm, npm, npx | 70-90% |
| Files | ls, read, grep, find | 60-75% |
| Infrastructure | docker, kubectl | 85% |
| Network | curl, wget | 65-70% |

Overall average: **60-90% token reduction** on common development operations.
<!-- /rtk-instructions -->