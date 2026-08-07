import { useQuery, type QueryClient } from "@tanstack/react-query";

import { queryPolicy } from "../../lib/query";
import { fetchActivity } from "./api/client";

const ACTIVITY_STALE_TIME_MS = 5_000;
const ACTIVITY_GC_TIME_MS = 5 * 60_000;

export const activityKeys = {
  all: ["activity"] as const,
  recent: (limit: number) => ["activity", "recent", limit] as const,
};

export function useActivityQuery(limit = 100) {
  return useQuery({
    queryKey: activityKeys.recent(limit),
    queryFn: () => fetchActivity(limit),
    ...queryPolicy(ACTIVITY_STALE_TIME_MS, ACTIVITY_GC_TIME_MS),
  });
}

export async function invalidateActivityQueries(queryClient: QueryClient): Promise<void> {
  await queryClient.invalidateQueries({ queryKey: activityKeys.all });
}
