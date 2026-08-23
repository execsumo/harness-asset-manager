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
    review: "Review to Adopt",
    activeHarnesses: "Active harnesses",
    allHarnesses: "All harnesses",
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
    capabilityOnHarness: (capability: string, harness: string) => `${capability} on ${harness}`,
    reviewOnHarness: (count: number, capability: string, harness: string) =>
      `${count.toLocaleString()} ${capability} to review on ${harness}`,
    allCapabilityAria: (capability: string) => `All ${capability.toLowerCase()}`,
    allReviewAria: (count: number, capability: string) =>
      `${count.toLocaleString()} ${capability} to review across all harnesses`,
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
    slashCommandsLabel: "Slash commands",
    mcpConfigsLabel: "MCP configs to review",
    differentMcpLabel: "Different MCP configs",
    inventoryIssuesLabel: "MCP inventory issues",
    unavailableHarnessLabel: "MCP harness unavailable",
    hooksLabel: "Hooks to review",
    permissionsLabel: "Permissions to review",
    agentsLabel: "Agents to review",
  },
} as const;

export type OverviewCopy = typeof englishOverviewCopy;

export const overviewCopy = englishOverviewCopy;

export function useOverviewCopy(): OverviewCopy {
  return overviewCopy;
}
