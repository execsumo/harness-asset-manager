
const englishSkillsCopy = {
  inUse: {
    title: "Skills",
    subtitle: (count: number) =>
      count > 0
        ? `${count} skill${count === 1 ? "" : "s"} being managed across harnesses.`
        : "No skills are being managed across harnesses.",
    importFolder: "Import folder",
    importFolderComingSoon: "Import folder — coming soon",
    searchPlaceholder: "Search by name, tag, description...",
    searchLabel: "Search skills in use",
    loading: "Loading skills in use",
    unableToLoad: "Unable to load skills in use.",
    emptyTitle: "No skills in use yet",
    emptyBody:
      "Review local skill folders or install something from the marketplace to start controlling harness coverage here.",
    filterAria: (label: string) => `Filter: ${label}`,
    harnessToggleAria: (enabled: number, total: number) => `Enabled on ${enabled} of ${total} harnesses`,
    harnessToggleTooltip: (label: string, enabled: boolean) => `${label} - ${enabled ? "enabled" : "disabled"}`,
    enableHarnessAria: (skillName: string, harnessLabel: string) => `Enable ${skillName} on ${harnessLabel}`,
    disableHarnessAria: (skillName: string, harnessLabel: string) => `Disable ${skillName} on ${harnessLabel}`,
    pills: {
      all: "All",
      enabled: "Enabled",
      allHarnesses: "Enabled on all",
      off: "Off",
    },
  },
  review: {
    title: "Skills to review",
    subtitle: (count: number) =>
      count > 0
        ? `${count} skill${count === 1 ? "" : "s"} need${count === 1 ? "s" : ""} a review decision.`
        : "No local skill folders need review across your harnesses.",
    adoptAllEligible: "Adopt all eligible",
    adoptingAllSkills: "Adopting all skills",
    adoptSelected: "Adopt",
    adoptingSelected: "Adopting selected skills",
    searchPlaceholder: "Search skills to review...",
    searchLabel: "Search skills to review",
    loading: "Loading skills to review",
    unableToLoad: "Unable to load skills to review.",
    emptyTitle: "Nothing needs review",
    emptyBody:
      "Your local harness folders are either already in use through Harness Asset Manager or currently empty. Install from the marketplace to add new skills.",
  },
  filters: {
    noMatchTitle: "No skills match the current filters.",
    noMatchBody: "Adjust the search or filter controls to bring skills back into view.",
    clearFilters: "Clear Filters",
  },
  bulk: {
    delete: "Delete",
    confirmTitle: (count: number) => `Delete ${count} skill${count === 1 ? "" : "s"}?`,
    confirmDescription: "This removes the Harness Asset Manager copy and its symlinks from every harness.",
    confirmNote: "The source on disk outside the Harness Asset Manager store is not touched.",
  },
  confirm: {
    removeTitle: "Remove skill from Harness Asset Manager?",
    removeDescription: (skillName: string) =>
      `This removes ${skillName} from the Harness Asset Manager store and restores local copies only for the harnesses that are currently enabled.`,
    restoreTo: (labels: readonly string[]) => `Will restore to: ${labels.join(", ")}`,
    remove: "Remove",
    removing: "Removing",
    deleteTitle: "Delete skill from Harness Asset Manager?",
    deleteDescription: (skillName: string) =>
      `This will remove ${skillName} from the shared store and delete its links from all harnesses.`,
    cannotUndo: "This action cannot be undone.",
    affectedHarnesses: (labels: readonly string[]) => `Affected harnesses: ${labels.join(", ")}`,
    delete: "Delete",
    deletingSkill: "Deleting skill",
  },
  detail: {
    unableToLoad: "Unable to load skill",
    close: "Close skill details",
    tryAgain: "Try selecting the skill again, or return to the list and reopen it.",
    sourceLinksAria: (label: string) => `Source links for ${label}`,
    openSkillFolder: "Open Skill Folder",
    loading: "Loading",
    about: "About",
    noDescription: "No description provided.",
    loadingDocument: "Loading document",
    noDocument: "No SKILL.md document is available for this entry.",
    harnesses: "Harnesses",
    locations: "Locations",
    storeNote:
      "Harness Asset Manager Store is the canonical physical package. Tool locations are symlinks to it when enabled.",
    addToSkillManager: "Add to Harness Asset Manager",
    managingSkill: "Managing skill",
    deleteSkill: "Delete Skill",
    canonicalPhysicalPackage: "Canonical physical package",
    symlinkToStore: "Symlink to Harness Asset Manager Store",
    moreActions: (name: string) => `More actions for ${name}`,
    removeFromSkillManager: "Remove from Harness Asset Manager",
    delete: "Delete",
    enableOnAll: "Enable on all",
    enableOnAllAria: "Enable on all harnesses",
    disableEverywhere: "Disable everywhere",
    inUseList: "Skills in use list",
    reviewList: "Skills to review list",
  },
} as const;

export type SkillsCopy = typeof englishSkillsCopy;

export const skillsCopy = englishSkillsCopy;

export function useSkillsCopy(): SkillsCopy {
  return skillsCopy;
}
