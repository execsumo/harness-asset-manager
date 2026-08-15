
const englishActivityCopy = {
  title: "Activity",
  subtitle: "Recent changes made by Harness Asset Manager, the CLI, and automatic repair.",
  loading: "Loading recent activity",
  unableToLoad: "Unable to load recent activity.",
  emptyTitle: "No activity yet",
  emptyBody: "Changes will appear here after Harness Asset Manager updates a managed asset or configuration.",
  details: "Details",
  parameters: "Parameters",
  changedPaths: "Changed paths",
  noPathsChanged: "No filesystem paths changed.",
  errorType: "Error type",
  outcomes: {
    succeeded: "Succeeded",
    partial: "Partial",
    refused: "Refused",
    failed: "Failed",
  },
} as const;

export type ActivityCopy = typeof englishActivityCopy;

export const activityCopy = englishActivityCopy;

export function useActivityCopy(): ActivityCopy {
  return activityCopy;
}
