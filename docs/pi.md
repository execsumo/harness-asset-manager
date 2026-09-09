# Pi support

Pi is supported as a **best-effort** harness. HAM targets Pi's global agent
directory, `~/.pi/agent/`, and does not write project-local `.pi/` resources.

## Supported assets

| Asset | Pi location | HAM status |
|---|---|---|
| Skills | `~/.pi/agent/skills/<name>/SKILL.md` | Supported, global only |
| Agents | `~/.pi/agent/agents/<name>.md` | Supported through Pi's subagent extension |
| Prompt templates | `~/.pi/agent/prompts/<name>.md` | Supported as global `/name` commands |

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
