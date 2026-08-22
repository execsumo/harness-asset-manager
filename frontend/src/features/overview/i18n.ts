const englishOverviewCopy = {
  screen: {
    title: "Overview",
    unableToLoadOverview: "Unable to load overview data.",
    unableToLoadSkills: (message: string) => `Unable to load skills: ${message}`,
    unableToLoadSlashCommands: (message: string) => `Unable to load slash commands: ${message}`,
    unableToLoadMcpServers: (message: string) => `Unable to load MCP servers: ${message}`,
    unableToLoadHooks: (message: string) => `Unable to load hooks: ${message}`,
    unableToLoadPermissions: (message: string) => `Unable to load permissions: ${message}`,
    unableToLoadAgents: (message: string) => `Unable to load agents: ${message}`,
  },
  sections: {
    shortcuts: "Shortcuts",
    review: "Review",
    activeHarnesses: "Active harnesses",
    noReviewWaiting: "No local adoption or config review is waiting.",
    noHarnesses: "No harnesses have been discovered yet.",
    harness: "Harness",
    skills: "Skills",
    commands: "Cmds",
    mcp: "MCP",
    hooks: "Hooks",
    permissions: "Perms",
    agents: "Agents",
    needsReview: "Review",
    manageGroup: "Manage",
    discoverGroup: "Discover",
    unavailableFallback: "writes are unavailable for an unknown reason",
    capabilityIssue: (capability: string, reason: string) => `${capability} writes unavailable — ${reason}`,
  },
  extensions: {
    skills: "Skills",
    slashCommands: "Slash Commands",
    mcpServers: "MCP Servers",
  },
  marketplace: {
    skills: "Skills Marketplace",
    mcp: "MCP Marketplace",
    cli: "CLI Marketplace",
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
