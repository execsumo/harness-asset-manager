
const englishGlossary = {
  skill: "Skill",
  skills: "Skills",
  mcp: "MCP",
  mcpServer: "MCP Server",
  mcpServers: "MCP Servers",
  cli: "CLI",
  clis: "CLIs",
  slashCommand: "Slash command",
  slashCommands: "Slash Commands",
  skillManager: "Harness Asset Manager",
  marketplace: "Marketplace",
} as const;

export type GlossaryCopy = typeof englishGlossary;

export const glossaryCopy = englishGlossary;

export function useGlossary(): GlossaryCopy {
  return glossaryCopy;
}
