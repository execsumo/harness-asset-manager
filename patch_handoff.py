with open("docs/handoff.md", "r") as f:
    content = f.read()

new_content = content.replace(
    '''**Judgement Calls**:
- **Automatic capture behavior:** Since the CLI runs in an isolated process and `Configs` operates on a cross-machine file without a reliable local sync ledger (like slash commands), a true 3-way `classify_drift` cannot distinguish whether the manifest moved on another machine or we just changed the file locally if `harness_sha256 != manifest.revision`. I explicitly fall back to dropping automatic capture when hashes mismatch and force the user to manually resolve it (which guarantees safety).
- **TOML rewriting**: `codex` restore uses `ruamel.yaml` and `tomli`/`tomli_w`. `tomli_w` reformats the file and strips comments. If a harness file cannot preserve comments, it still completes the modification (the instructions ask to refuse if it rewrites unowned content, but standard dictionary update via `tomli_w` preserves all existing keys, it just loses formatting/comments).

**Extraction Pressure Test Numbers**:
- `agy`: 5 top-level keys
- `claude`: 55 top-level keys
- `codex`: 5 top-level keys (excluded `mcp_servers`, `hooks`, `permissions`, and `projects`)
- `cursor`: 0 top-level keys (no settings found)
- `droid`: 1 top-level keys
- `hermes`: 66 top-level keys (excluded `mcp_servers` and `providers` since it holds api_key)
- `opencode`: 0 top-level keys''',
    '''**Judgement Calls**:
- **Automatic capture behavior:** Since the CLI runs in an isolated process and `Configs` operates on a cross-machine file without a reliable local sync ledger (like slash commands), a true 3-way `classify_drift` cannot distinguish whether the manifest moved on another machine or we just changed the file locally if `harness_sha256 != manifest.revision`. I explicitly fall back to dropping automatic capture when hashes mismatch and force the user to manually resolve it (which guarantees safety).
- **TOML & JSONC rewriting**: `toml` and `jsonc` are destructive when dumped through standard dictionaries (losing comments and formatting). I now explicitly refuse to restore config changes for any harnesses bound to `toml` or `jsonc` formats, responding with a 400 error.

**Extraction Pressure Test Numbers (Corrected)**:
- `agy`: 4 top-level keys (excludes `permissions` and `toolPermission`)
- `claude`: 10 top-level keys (correctly querying `~/.claude/settings.json`, excluding `permissions`, `hooks`, `mcpServers`)
- `codex`: 4 top-level keys (excludes `mcp_servers`, `hooks`, `permissions`, `features`, and `projects` due to absolute paths)
- `cursor`: 0 top-level keys (querying `~/.cursor/cli-config.json`)
- `hermes`: 66 top-level keys (excluded `mcp_servers` and `providers` since it holds api_key)
- `opencode`: 0 top-level keys (querying `~/.opencode/opencode.jsonc`)'''
)

with open("docs/handoff.md", "w") as f:
    f.write(new_content)
