# Pi support

Pi is supported as a **best-effort** harness. HAM targets Pi's global agent
directory, `~/.pi/agent/`, and does not write project-local `.pi/` resources.

## Supported assets

| Asset | Pi location | HAM status |
|---|---|---|
| Skills | `~/.pi/agent/skills/<name>/SKILL.md` | Supported, global only |
| Agents | `~/.pi/agent/agents/<name>.md` | Supported through Pi's subagent extension |
| Prompt templates | `~/.pi/agent/prompts/<name>.md` | Supported as global `/name` commands |
| Preferences | `~/.pi/agent/settings.json` | Supported through the Configs family |

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

## Not currently supported

Pi does not provide a standard native MCP, hooks, or permissions document that
matches HAM's canonical family contracts. Extensions may add those capabilities,
but extension-specific configuration remains outside this integration.

## Documentation basis

- [Pi skills](https://pi.dev/docs/latest/skills)
- [Pi prompt templates](https://pi.dev/docs/latest/prompt-templates)
- [Pi settings and global resource locations](https://pi.dev/docs/latest/settings)
- [Pi extensions](https://pi.dev/docs/latest/extensions)
