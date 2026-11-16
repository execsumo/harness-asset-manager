export const SKILLS_STALE_TIME_MS = 60_000;
export const SKILLS_GC_TIME_MS = 15 * 60_000;
// A skills scan stats every package file (~1s on a large library), so poll gently
// and lean on refetch-on-focus for prompt pickup of on-disk changes.
export const SKILLS_LIST_REFETCH_INTERVAL_MS = 30_000;

export const skillsKeys = {
  all: ["skills"] as const,
  list: () => ["skills", "list"] as const,
  detailPrefix: () => ["skills", "detail"] as const,
  detail: (skillRef: string) => ["skills", "detail", skillRef] as const,
  sourceStatusPrefix: () => ["skills", "source-status"] as const,
  sourceStatus: (skillRef: string) => ["skills", "source-status", skillRef] as const,
};
