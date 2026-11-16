export const AGENTS_LIST_REFETCH_INTERVAL_MS = 5_000;

export const agentsKeys = {
  all: ["agents"] as const,
  list: () => [...agentsKeys.all, "list"] as const,
  hermesOptions: () => [...agentsKeys.all, "hermes-options"] as const,
  detail: (ref: string) => [...agentsKeys.all, "detail", ref] as const,
};
