# Pi support

Pi is supported as a **best-effort** harness. HAM targets Pi's user-level
resources under `~/.pi/agent/` and does not write project-local `.pi/` resources.

## Supported assets

| Asset | Pi location | HAM status |
|---|---|---|
| Skills | `~/.pi/agent/skills/<name>/SKILL.md` | Supported, global only |
| Agents | `~/.pi/agent/agents/<name>.md` | Supported through Pi's subagent extension |
| Prompt templates | `~/.pi/agent/prompts/<name>.md` | Supported as global `/name` commands |
| Preferences | `~/.pi/agent/settings.json` | Supported through the Configs family |
| MCP servers | `~/.pi/agent/mcp.json` | Supported through the MCP family; stdio and streamable HTTP |

Preferences (provider, model, thinking level, theme, terminal and markdown
options, installed packages, …) are captured from `~/.pi/agent/settings.json`
into the portable manifest. Three keys are withheld: `skills` and `prompts` are
resource path lists the skills and slash-command families already own, and
`trackingId` is a per-install analytics UUID that must not be cloned onto
another machine. Secrets and absolute paths are stripped by the Configs family
itself, so path-valued keys such as `shellPath` or `sessionDir` never travel.

Agents use HAM's standard Markdown frontmatter format. Pi's subagent extension
discovers the user-level `agents/` directory, so HAM installs agents there as
symlinks. Pi prompt templates use Markdown with optional frontmatter and are
managed by HAM's slash-command family.

## MCPs in subagents

Pi's built-in MCP support reads `~/.pi/agent/mcp.json`; it does not define MCP
servers in agent frontmatter. With the `@tintinweb/pi-subagents` extension, a
subagent can opt into Pi's MCP extension independently. To keep MCP tools and
server context out of the main agent while making them available to opted-in
subagents:

1. Manage the MCP server in HAM's Pi MCP family.
2. Start the main Pi session with `pi --no-mcp`.
3. Add `extensions: [mcp]` and `tools: "*, ext:mcp"` to only the subagent frontmatter that should use MCPs.

The Pi MCP config remains user-level, so opted-in subagents can see the configured
servers. The subagent extension also supports exact extension-tool selectors (for
example, `ext:mcp/<tool-name>`); Pi does not provide a stable server-level
frontmatter binding. HAM must not imply that selecting the MCP extension grants
only one server.

Pi does not have native hooks or permissions configuration that matches HAM's
canonical family contracts. Extensions may add those capabilities, but
extension-specific configuration remains outside this integration.

## Documentation basis

- [Pi skills](https://pi.dev/docs/latest/skills)
- [Pi prompt templates](https://pi.dev/docs/latest/prompt-templates)
- [Pi settings and global resource locations](https://pi.dev/docs/latest/settings)
- [Pi MCP servers and `--no-mcp`](https://pi.dev/docs/latest/mcp)
- [`@tintinweb/pi-subagents` frontmatter fields](https://github.com/tintinweb/pi-subagents#frontmatter-fields)
- [Pi extensions](https://pi.dev/docs/latest/extensions)
