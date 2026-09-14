const englishConfigsCopy = {
  title: "Configs",
  subtitle:
    "Capture each harness's own preferences — model, theme, effort — so you can restore them after a reinstall or a stray edit.",
  searchPlaceholder: "Search by harness or config path...",
  searchLabel: "Search configs",
  loading: "Loading configs",
  unableToLoad: "Unable to load configs.",
  captureAll: "Capture all",
  capturing: "Capturing",
  captureAllHint: "Re-read every managed config file and overwrite the stored snapshot.",
  filters: {
    all: "All",
    managed: "Managed",
    drifted: "Drifted",
    unmanaged: "Unmanaged",
    orphaned: "Record only",
  },
  summary: {
    inSync: "In sync",
    drifted: "Drifted",
    unmanaged: "Not managed",
    inSyncHint: "Config file matches the captured snapshot.",
    driftedHint: "Config file no longer matches the snapshot.",
    unmanagedHint: "Detected harnesses you have not captured yet.",
  },
  columns: {
    harness: "Harness",
    status: "Status",
    keys: "Keys",
    captured: "Last captured",
    actions: "Actions",
  },
  status: {
    managed: "In sync",
    drifted: "Drifted",
    unmanaged: "Not managed",
    orphaned: "Record only",
  },
  actions: {
    manage: "Manage",
    stopManaging: "Stop managing",
    restore: "Restore",
    capture: "Capture",
    removeRecord: "Remove record",
  },
  never: "Never",
  noKeys: "—",
  emptyTitle: "No harness configs detected",
  emptyBody:
    "HarnessAM manages a config once it can see the harness's own settings file. Install a supported harness, or enable it in Settings, and it will show up here.",
  noMatchesTitle: "No configs match these filters",
  noMatchesBody: "Adjust the search, status, or tag filters to see other harnesses.",
  clearFilters: "Clear filters",
  detail: {
    close: "Close config details",
    sourceHeading: "Config file",
    statusHeading: "Status",
    driftHeading: "Drift",
    preferencesHeading: "Captured preferences",
    keyCount: (count: number) => `${count} key${count === 1 ? "" : "s"}`,
    analyzing: "Analyzing drift...",
    noDrift: "The config file matches the captured snapshot.",
    driftDetected: "Drift detected",
    missing: "Missing in file",
    extra: "Extra in file",
    changed: "Changed values",
    orphanTitle: "Record without a local file",
    orphanBody:
      "A snapshot exists for this harness, but its config file is absent on this machine. If the harness is managed on another machine, leave this alone.",
    unmanagedBody:
      "Capture this harness's preferences to keep a restorable snapshot of its settings.",
    restoreHint: "Write the captured preferences back into the config file.",
    captureHint: "Overwrite the snapshot with what is in the config file right now.",
    capturedAt: "Captured",
  },
};

export type ConfigsCopy = typeof englishConfigsCopy;

export const configsCopy = englishConfigsCopy;

export function useConfigsCopy(): ConfigsCopy {
  return configsCopy;
}
