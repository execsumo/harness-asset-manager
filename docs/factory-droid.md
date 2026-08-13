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
`/tmp/factory-home/droids`, and `/tmp/factory-home/commands`.

## Documentation basis

- [Skills](https://docs.factory.ai/harness/skills.md)
- [MCP](https://docs.factory.ai/harness/mcp.md)
- [Custom droids](https://docs.factory.ai/harness/subagents.md)
- [Custom slash commands](https://docs.factory.ai/harness/custom-slash-commands.md)
- [Hooks](https://docs.factory.ai/harness/hooks.md)
- [Settings](https://docs.factory.ai/droid-cli/settings.md)
