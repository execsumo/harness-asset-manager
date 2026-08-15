
const englishMcpCopy = {
  inUse: {
    title: "MCP servers in use",
    subtitle: "Browse, enable, and remove MCP servers across your harnesses.",
    searchPlaceholder: "Search by name or transport...",
    searchLabel: "Search MCP servers",
    loading: "Loading MCP servers",
    unableToLoad: "Unable to load MCP servers.",
    inventoryIssue: (count: number) =>
      `${count} MCP catalog record${count === 1 ? "" : "s"} could not be loaded. Valid records are still shown.`,
    noMatchesBody: "Adjust the search or filter to see other MCP servers.",
    emptyTitle: "No MCP servers in use yet",
    emptyBody: "Install one from the marketplace, or adopt an existing entry from a harness config.",
    filters: {
      all: "All",
      enabled: "Enabled",
      allHarnesses: "Enabled on all",
      unbound: "Unbound",
      drifted: "Different config",
      aria: (label: string) => `Filter: ${label}`,
    },
    uninstall: {
      action: "Uninstall",
      title: (name: string) => `Uninstall ${name}?`,
      bulkTitle: (count: number) => `Uninstall ${count} server${count === 1 ? "" : "s"}?`,
      description:
        "Remove each server from the Harness Asset Manager catalog and delete its bindings from all harnesses where it is currently present.",
      singleDescription:
        "Remove this server from the Harness Asset Manager catalog and delete its bindings from all harnesses where it is currently present.",
      pending: "Uninstalling",
      fallbackName: "this server",
    },
  },
  review: {
    title: "MCP configs to review",
    subtitle: (count: number) =>
      count > 0
        ? `${count} unique server${count === 1 ? "" : "s"} across your harness configs.`
        : "No local MCP config entries need review across your harnesses.",
    adoptIdentical: (count: number) => `Adopt identical servers (${count})`,
    adoptSelected: "Adopt",
    adoptingSelected: "Adopting selected servers",
    searchPlaceholder: "Search by server name...",
    searchLabel: "Search MCP configs to review",
    loading: "Loading MCP configs to review",
    noMatchesBody: "Clear the search to see all MCP configs that need review.",
    emptyTitle: "No local MCP configs need review",
    emptyBody:
      "Your harness configs only reference MCP servers that harness-asset-manager already tracks. Install a new server from the marketplace to add more.",
  },
  detail: {
    close: "Close MCP server detail",
    closeShort: "Close detail",
    loadingServer: "Loading MCP server",
    loading: "Loading…",
    unableTitle: "Unable to load MCP server",
    unableToLoadInstallConfig: "Unable to load MCP configuration fields.",
    about: "About",
    differentConfigsTitle: "Different configs found",
    differentConfigsBody: "Choose which config Harness Asset Manager should manage, then apply it to current bindings.",
    resolveConfig: "Resolve config",
    connection: "Connection",
    bindings: "Bindings",
    environment: "Environment",
    uninstall: "Uninstall",
    sourceLinksAria: (name: string) => `Source links for ${name}`,
    viewInRegistry: "View in MCP Registry",
    github: "GitHub",
    website: "Website",
    unavailableLink: (label: string) => `${label} unavailable`,
    noRegistryLink: "This MCP server is not linked to an MCP Registry entry.",
    noGithubLink: "No GitHub repository is listed for this MCP server.",
    noWebsiteLink: "No website is listed for this MCP server.",
    skillManagerConfig: "Harness Asset Manager config",
    noConnectionData: "No connection data.",
    command: "Command",
    args: "Args",
    url: "URL",
    transport: "Transport",
    headers: "Headers",
    openDetail: (name: string) => `Open detail for ${name}`,
    select: (name: string) => `Select ${name}`,
    deselect: (name: string) => `Deselect ${name}`,
    enabledStatus: {
      enabled: "Enabled",
      disabled: "Disabled",
    },
    enabledStatusAria: (label: string) => `Status: ${label}`,
    mcpStatus: {
      available: "Available",
      needs_config: "Needs config",
      connection_issue: "Connection issue",
      unchecked: "Unchecked",
    },
    mcpStatusReason: {
      available: "MCP endpoint is reachable.",
      needs_config: "Required configuration is missing. Add it when enabling this MCP.",
      connection_issue: "Connection failed. Check this MCP's config.",
      unchecked: "Availability has not been checked yet.",
      httpUnauthorized: () =>
        "Authentication required, but no auth link is listed.",
      httpUnauthorizedWithDocs: () =>
        "Authentication required. Check the website or GitHub docs.",
      httpUnauthorizedNoDocs: () =>
        "Authentication required, but no auth link or docs are listed.",
      httpForbidden: () =>
        "Access refused. Check credentials, permissions, or quota.",
      httpNotFound: () =>
        "Endpoint not found. Check the server URL.",
      httpRateLimited: () =>
        "Rate limited. Try again later or check quota.",
      httpServerError: () =>
        "Provider error. Try again later.",
    },
    mcpStatusAria: (label: string) => `MCP status: ${label}`,
    installConfig: {
      allHarnesses: "all harnesses",
      title: (name: string) => `Configure ${name}`,
      description: (harness: string) => `Configure for ${harness}. These values will be written to your local Agent MCP config.`,
      bulkRequiresSingle: (name: string) =>
        `${name} requires credentials. Enable it by itself so Harness Asset Manager can collect the required configuration.`,
      requiredHint: "Complete the required fields before saving.",
      optionalHint: "Optional configuration",
      missingRequired: (fields: string) => `Missing required fields: ${fields}`,
      install: "Save",
      cancel: "Cancel",
      showSecret: "Show secret",
      hideSecret: "Hide secret",
    },
    review: {
      loadingServer: "Loading server",
      identicalAcross: (count: number) => `Identical across ${count} harnesses`,
      differentIn: (count: number) => `Different in ${count} harnesses`,
      marketplaceMetadata: "Marketplace metadata",
      marketplaceMatch: "Match in marketplace",
      sightings: "Sightings",
      configToAdopt: "Config to adopt",
      addTooltip: "Add this server to Harness Asset Manager",
      chooseTooltip: "Choose which config Harness Asset Manager should keep",
      adopt: "Adopt",
      chooseConfigToAdopt: "Choose config to adopt",
      identical: "Identical",
      differsAcrossHarnesses: "Differs across harnesses",
      foundInHarnesses: (count: number) => `Found in ${count} harness${count === 1 ? "" : "es"}`,
    },
    configChoice: {
      adoptTitle: "Choose config to adopt",
      resolveTitle: "Resolve different configs",
      adoptDescription:
        "Pick the config to store as the Harness Asset Manager config. Other harness entries will be rewritten to match it.",
      resolveDescription:
        "Pick the config Harness Asset Manager should manage. Current bindings will be rewritten to match it.",
      adoptConfirm: "Adopt",
      applyConfig: "Apply config",
      ariaLabel: (title: string, serverName: string) => `${title} for ${serverName}`,
      close: "Close config choice dialog",
      recommended: "Recommended",
      observedHarness: (label: string) => `Observed harness: ${label}`,
      managedConfig: "Managed MCP config",
      credentialInUrl: "Credential in URL",
      noEnvironmentValues: "No environment values",
      showPreview: "Show config preview",
      hidePreview: "Hide config preview",
      cancel: "Cancel",
      adoptTooltip: "Add to Harness Asset Manager using the selected config",
      resolveTooltip: "Apply the selected config to current bindings",
    },
    sheet: {
      inUseLabel: (name: string) => `MCP server ${name}`,
      inUseTitle: (name: string) => `MCP server ${name}`,
      inUseDescription: "Inspect and manage an installed MCP server.",
      reviewLabel: (name: string) => `MCP config to review ${name}`,
      reviewTitle: (name: string) => `MCP config to review ${name}`,
      reviewDescription:
        "Inspect an MCP server found across harnesses and adopt it, or choose a config to adopt.",
    },
    list: {
      reviewAriaLabel: "MCP configs to review",
    },
    matrix: {
      ariaLabel: "MCP server harness matrix",
      selectColumn: "Select",
      serverColumn: "Server",
      harnessesColumn: "Harnesses",
      enabledColumn: "Active",
      coverage: (enabled: number, writable: number) =>
        `Enabled on ${enabled} of ${writable} writable harnesses`,
      baseLabel: (serverName: string, harnessLabel: string) => `${serverName} on ${harnessLabel}`,
      enabledTooltip: (harnessLabel: string) => `${harnessLabel} — enabled`,
      disable: (baseLabel: string) => `Disable ${baseLabel}`,
      differentTooltip: (harnessLabel: string, detail: string) =>
        `${harnessLabel} — Different config${detail}`,
      resolveConfigFor: (baseLabel: string) => `Resolve config for ${baseLabel}`,
      foundTooltip: (harnessLabel: string) => `${harnessLabel} — Found in harness`,
      openDetailFor: (baseLabel: string) => `Open detail for ${baseLabel}`,
      unavailable: (baseLabel: string) => `${baseLabel} is unavailable`,
      disabledTooltip: (harnessLabel: string) => `${harnessLabel} — disabled`,
      enable: (baseLabel: string) => `Enable ${baseLabel}`,
    },
  },
} as const;

export type McpCopy = typeof englishMcpCopy;

export const mcpCopy = englishMcpCopy;

export function useMcpCopy(): McpCopy {
  return mcpCopy;
}
