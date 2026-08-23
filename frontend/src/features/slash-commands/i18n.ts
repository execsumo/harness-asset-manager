import type { SlashCommandReviewDto, SlashReviewAction } from "./api/types";

const englishSlashCommandsCopy = {
  inUse: {
    title: "Slash Commands",
    subtitle: "Create one global prompt and sync it into local slash command folders.",
    newCommand: "New command",
    searchPlaceholder: "Search slash commands",
    searchLabel: "Search slash commands",
    loading: "Loading slash commands",
    unableToLoad: "Unable to load slash commands.",
    deleteTitle: (name: string) => `Delete ${name}?`,
    deleteDescription: "This removes the source command and generated command files from every synced target.",
    deleting: "Deleting",
    bulkDeleteTitle: (count: number) => `Delete ${count} slash command${count === 1 ? "" : "s"}?`,
    bulkDeleteDescription:
      "This removes the source command and generated command files for every selected slash command.",
  },
  review: {
    title: "Slash commands to review",
    subtitle: (count: number) =>
      count > 0
        ? `${count} command${count === 1 ? "" : "s"} found outside normal managed state.`
        : "No unmanaged, changed, or missing slash command files were found.",
    adoptAllEligible: "Adopt all eligible",
    adoptingAllCommands: "Adopting all commands",
    searchPlaceholder: "Search slash commands to review",
    searchLabel: "Search slash commands to review",
    loading: "Loading slash commands to review",
    listAria: "Slash commands to review list",
    emptyTitle: "Nothing needs review",
    emptyBody:
      "Slash command files in target folders are already managed or no supported target folders contain commands.",
    cannotUpdate: "Cannot update",
    actionLabel: (action: SlashReviewAction | null) => {
      if (action === "restore_managed") return "Restore";
      if (action === "adopt_target") return "Adopt";
      if (action === "remove_binding") return "Remove binding";
      if (action === "import") return "Adopt";
      return "Review";
    },
    actionTitle: (action: SlashReviewAction) => {
      if (action === "restore_managed") return "Restore the managed command content to this harness";
      if (action === "adopt_target") return "Use this harness command as the managed command content";
      if (action === "remove_binding") return "Stop tracking this harness command without deleting it";
      return "Adopt this command into Harness Asset Manager";
    },
    metaText: (row: SlashCommandReviewDto) => {
      if (row.kind === "drifted") return `Changed in ${row.targetLabel}`;
      if (row.kind === "missing") return `Missing from ${row.targetLabel}`;
      return `Found in ${row.targetLabel}`;
    },
  },
  detail: {
    about: "About",
    delete: "Delete",
    enableTargetFor: (target: string, name: string) => `Enable ${target} for ${name}`,
    disableTargetFor: (target: string, name: string) => `Disable ${target} for ${name}`,
    close: "Close slash command detail",
    actionsAria: "Slash command actions",
    edit: "Edit",
    harnesses: "Harnesses",
    harnessesFor: (name: string) => `Harnesses for ${name}`,
    enabled: "Enabled",
    disabled: "Disabled",
    enable: "Enable",
    disable: "Disable",
    locations: "Locations",
    noHarnessLocations: "No harness locations are enabled.",
    written: "Written",
    description: "Description",
    prompt: "Prompt",
    noDescription: "No description provided.",
    noPrompt: "No prompt content.",
    document: "Document",
    save: "Save",
    saving: "Saving",
    cancel: "Cancel",
    unsavedChanges: "Unsaved changes",
    savedSuccess: (name: string) => `Successfully updated ${name}`,
    discardTitle: "Discard changes?",
    discardDescription: "You have unsaved changes that will be lost. Are you sure you want to discard them?",
    discardConfirm: "Discard changes",
    form: {
      createTitle: "New slash command",
      editTitle: "Edit command",
      description: "Save one prompt and sync it into selected global command folders.",
      close: "Close",
      name: "Name",
      nameError: "Use lowercase letters, numbers, and hyphens, for example code-review.",
      descriptionLabel: "Description",
      descriptionPlaceholder: "Review code for bugs and security risks",
      prompt: "Prompt",
      promptPlaceholder: "Review the following content:\n\n$ARGUMENTS",
      harnesses: "Harnesses",
      cancel: "Cancel",
      create: "Create",
      save: "Save",
    },
    review: {
      actionsAria: "Slash command review actions",
      conflictNotice:
        "A managed slash command already uses this name. Adopting the harness command will replace the Harness Asset Manager source.",
      driftedNotice:
        "The harness command changed after Harness Asset Manager last synced it. Restore writes the Harness Asset Manager source back to the harness; Adopt updates Harness Asset Manager from this harness command.",
      canonicalGapNotice:
        "The review entry says this command is managed, but the canonical command is not present in the current slash command list.",
      harnessContext: (name: string) => `Harness review context for ${name}`,
      noDescriptionParsed: "No description parsed.",
      noPromptParsed: "No prompt content parsed.",
      skillManagerSource: "Harness Asset Manager source",
      noCanonicalContent: "No canonical command content is available.",
      harnessCommand: "Harness command",
      path: "Path",
      notPresent: "Not present",
      adoptHint: "Adopt this command to manage it",
      resolveHint: "Resolve from footer",
      changedInHarness: "Changed in harness",
      missingFromHarness: "Missing from harness",
      foundInHarness: "Found in harness",
    },
  },
} as const;

export type SlashCommandsCopy = typeof englishSlashCommandsCopy;

export const slashCommandsCopy = englishSlashCommandsCopy;

export function useSlashCommandsCopy(): SlashCommandsCopy {
  return slashCommandsCopy;
}
