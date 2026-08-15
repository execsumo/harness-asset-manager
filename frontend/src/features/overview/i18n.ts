
const englishOverviewCopy = {
  screen: {
    title: "Overview",
    unableToLoadOverview: "Unable to load overview data.",
    unableToLoadSkills: (message: string) => `Unable to load skills: ${message}`,
    unableToLoadSlashCommands: (message: string) => `Unable to load slash commands: ${message}`,
    unableToLoadMcpServers: (message: string) => `Unable to load MCP servers: ${message}`,
  },
  sections: {
    inventoryStatistics: "Inventory statistics",
    extensions: "Extensions",
    discover: "Discover",
    review: "Review",
    activeHarnesses: "Active harnesses",
    noReviewWaiting: "No local adoption or config review is waiting.",
    noHarnesses: "No harnesses have been discovered yet.",
    harness: "Harness",
    skills: "Skills",
    mcp: "MCP",
    needsReview: "Needs review",
    mcpUnavailable: "MCP unavailable",
    different: (count: number) => `${count.toLocaleString()} different`,
  },
  stats: {
    inUse: "In use",
    needsReview: "Needs review",
    harnesses: "Harnesses",
    metricPart: (value: number | null, singular: string, plural: string) =>
      `${value == null ? "-" : value.toLocaleString()} ${value === 1 ? singular : plural}`,
    inUseDetail: (skills: number | null, commands: number | null, mcp: number | null) =>
      [
        `${skills == null ? "-" : skills.toLocaleString()} ${skills === 1 ? "skill" : "skills"}`,
        `${commands == null ? "-" : commands.toLocaleString()} ${commands === 1 ? "command" : "commands"}`,
        `${mcp == null ? "-" : mcp.toLocaleString()} MCP`,
      ].join(" · "),
    needsReviewDetail: "adoption · config · inventory",
    harnessesDetail: (count: number | null) => `${count == null ? "-" : count.toLocaleString()} observed`,
  },
  extensions: {
    skills: "Skills",
    slashCommands: "Slash Commands",
    mcpServers: "MCP Servers",
    inUseFact: "in use",
    reviewFact: "review",
  },
  marketplace: {
    skills: "Skills Marketplace",
    mcp: "MCP Marketplace",
    cli: "CLI Marketplace",
    browse: "Browse",
    previewOnly: "Preview only",
  },
  reviewItems: {
    skillsLabel: "Skills to review",
    skillsDescription: "Adopt local skills so they can be enabled consistently.",
    slashCommandsLabel: "Slash commands",
    slashCommandsDescription: "Unmanaged, changed, or missing command files need a decision.",
    mcpConfigsLabel: "MCP configs to review",
    mcpConfigsDescription: "Adopt existing harness configs into Harness Asset Manager.",
    differentMcpLabel: "Different MCP configs",
    differentMcpDescription: "Resolve which config should become the source of truth.",
    inventoryIssuesLabel: "MCP inventory issues",
    inventoryIssuesDescription: "Some Harness Asset Manager MCP records could not be loaded cleanly.",
    unavailableHarnessLabel: "MCP harness unavailable",
    unavailableHarnessDescription: "At least one harness cannot safely receive MCP writes.",
  },
} as const;

export type OverviewCopy = typeof englishOverviewCopy;

export const overviewCopy = englishOverviewCopy;

export function useOverviewCopy(): OverviewCopy {
  return overviewCopy;
}
