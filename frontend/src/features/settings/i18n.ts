
const englishSettingsCopy = {
  title: "Settings",
  subtitle: "Local paths and per-harness discovery.",
  loading: "Loading settings",
  storage: {
    heading: "Local storage",
    storeTitle: "Harness Asset Manager store",
    storeSubtitle: "Canonical copies of skills in use live here.",
    cacheTitle: "Marketplace cache",
    cacheSubtitle: "Downloaded previews and install bundles.",
  },
  harnesses: {
    heading: "Harness roots",
    detectedHeading: "Detected harnesses",
    notDetectedHeading: "Not detected harnesses",
    enableSupport: (label: string) => `Enable ${label} support`,
    saving: "Saving...",
  },
  autoAdopt: {
    heading: "Automatic Adoption",
    enableAll: "Enable all auto-maintenance",
    agents: {
      label: "Repair drifted Agent bindings",
      short: "Repair Drift",
      sub: "Fold an edited harness copy back into the store only when it is provably the only edit.",
    },
    skills: {
      label: "Adopt new local Skills",
      short: "Skills",
      sub: "Adopt equivalent unmanaged Skill folders and replace them with store links.",
    },
    slash_commands: {
      label: "Adopt new slash commands",
      short: "Commands",
      sub: "Adopt equivalent unmanaged command files without overwriting their contents.",
    },
    mcp: {
      label: "Adopt MCP configurations",
      short: "MCP",
      sub: "Adopt only when all observed harness configurations are identical.",
    },
    hooks: {
      label: "Adopt Hooks",
      short: "Hooks",
      sub: "Promote equivalent unmanaged Hooks into the shared manifest.",
    },
    permissions: {
      label: "Adopt Permissions",
      short: "Permissions",
      sub: "Promote equivalent unmanaged deny rules into the shared manifest.",
    },
  },
  errors: {
    unableToLoad: "Unable to load settings.",
    unableToUpdateHarnessSupport: "Unable to update harness support.",
  },
} as const;

export type SettingsCopy = typeof englishSettingsCopy;

export const settingsCopy = englishSettingsCopy;

export function useSettingsCopy(): SettingsCopy {
  return settingsCopy;
}
