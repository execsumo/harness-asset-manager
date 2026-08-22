
const englishCommonCopy = {
  actions: {
    cancel: "Cancel",
    refresh: "Refresh",
    refreshing: "Refreshing",
    clearFilters: "Clear filters",
    clearSearch: "Clear search",
    clearSelection: "Clear selection",
    enableAll: "Enable all",
    disableAll: "Disable all",
    enabling: "Enabling",
    disabling: "Disabling",
    delete: "Delete",
    browseMarketplace: "Browse marketplace",
    openMarketplace: "Open Marketplace",
    reviewItems: "Review items",
  },
  nav: {
    primary: "Primary navigation",
    overview: "Overview",
    skills: "Skills",
    slashCommands: "Slash Commands",
    mcpServers: "MCP Servers",
    marketplace: "Marketplace",
    clis: "CLIs",
    permissions: "Permissions",
    settings: "Settings",
    light: "Light",
    dark: "Dark",
    lightComingSoon: "Light theme — coming soon",
  },
  productLanguage: {
    inUse: "In use",
    needsReview: "Unmanaged",
    review: "Review",
    discover: "Discover",
  },
  loading: {
    overview: "Loading overview",
    mcp: "Loading MCP",
    marketplace: "Loading marketplace",
    slashCommands: "Loading slash commands",
    settings: "Loading settings",
    document: "Loading document",
  },
  search: {
    placeholder: "Search...",
    label: "Filter search",
    filterOptions: "Filter options",
  },
  bulk: {
    ariaLabel: "Bulk actions",
    selected: (count: number) => `${count} selected`,
    selectedAction: (action: string, count: number) => `${action} ${count} selected`,
  },
  status: {
    noMatches: "No matches",
    unknownError: "Unknown error",
  },
} as const;

export type CommonCopy = typeof englishCommonCopy;

export const commonCopy = englishCommonCopy;

export function useCommonCopy(): CommonCopy {
  return commonCopy;
}
