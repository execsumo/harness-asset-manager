# Factory Droid support

Factory Droid is supported as a **best-effort** harness. The catalog is based on
Factory's official harness documentation, not on a compatibility assumption with
Claude Code.

HAM currently manages the personal/global Droid locations under `~/.factory` only.
Factory also supports project-scoped files under the repository's `.factory/`
directory, but HAM does not read, write, adopt, or delete those project files.
This prevents a global sync from unexpectedly changing committed team configuration.

## Supported assets

| Asset | Native Droid location | HAM status |
|---|---|---|
| Skills | `~/.factory/skills/<name>/SKILL.md` | Supported, global only |
| MCP servers | `~/.factory/mcp.json`, under `mcpServers` | Supported, global only |
| Custom droids | `~/.factory/droids/<name>.md` | Supported, personal only |
| Custom slash commands | `~/.factory/commands/<name>.md` | Supported, personal only |
| Preferences | `~/.factory/settings.json` | Supported through the Configs family |

Preferences (`model`, `reasoningEffort`, `outputStyle`, `diffMode`, sound and
session defaults, …) are captured from `~/.factory/settings.json` into the
portable manifest. Four groups are withheld: `hooks`, which Droid also writes
into this file and which HAM does not map (below), and `commandAllowlist`,
`commandDenylist`, and `commandBlocklist`, which are the command policy the
permissions family deliberately leaves alone (below). Capturing either would
make Configs a second, silent owner of them. `trustedFolders` and `customModels`
drop out on their own — the first is keyed by absolute path, the second carries
a credential.

`~/.factory/settings.local.json` is a user-level override that merges on top of
`settings.json`. HAM manages `settings.json` only; keep machine-specific values
in the local override if you do not want them in the manifest.

HAM can also store the portable `AGENTS.md` instructions file as ordinary project
content, but it is not a managed asset family and is not copied into
`~/.factory/`.

Factory's plugin package is also a distinct distribution surface. HAM does not
install or manage `.factory-plugin/` packages, plugin marketplaces, or plugin-owned
skills, commands, droids, hooks, and MCP definitions.

## Not currently supported

- **Hooks**: Droid supports user, project, enterprise, and legacy hook scopes, with
  lifecycle names and matcher semantics that differ from HAM's canonical hook model.
  We should add a dedicated Droid mapper rather than writing Claude-shaped hook JSON.
- **Permissions**: Droid's `commandAllowlist`, `commandDenylist`, and
  `commandBlocklist` are command-policy controls, not the denylist-only,
  shell/file/web/MCP rule model HAM currently manages. HAM deliberately does not
  infer a mapping.

The catalog uses `~/.factory` by default. Tests and installations can override the
root with `HARNESS_ASSET_MANAGER_FACTORY_ROOT`.

When the override is set, it replaces the entire personal Factory root. For example,
setting it to `/tmp/factory-home` makes HAM use
`/tmp/factory-home/skills`, `/tmp/factory-home/mcp.json`,
`/tmp/factory-home/droids`, `/tmp/factory-home/commands`, and
`/tmp/factory-home/settings.json`.

## Documentation basis

- [Skills](https://docs.factory.ai/harness/skills.md)
- [MCP](https://docs.factory.ai/harness/mcp.md)
- [Custom droids](https://docs.factory.ai/harness/subagents.md)
- [Custom slash commands](https://docs.factory.ai/harness/custom-slash-commands.md)
- [Hooks](https://docs.factory.ai/harness/hooks.md)
- [Settings](https://docs.factory.ai/droid-cli/settings.md)
