import { MutationCache, QueryClient } from "@tanstack/react-query";

import { ApiError } from "../api/http";
import { invalidateAssetTagVocabulary } from "../components/tags/asset-tag-vocabulary";

/**
 * Retry a failed query once, and only when a second try can plausibly succeed:
 * network failures, timeouts and 5xx. A 4xx response is the server's final answer.
 */
export function shouldRetryQuery(failureCount: number, error: unknown): boolean {
  if (failureCount >= 1) return false;
  if (!(error instanceof ApiError)) return true;
  return error.code === "network_error" || error.code === "timeout" || error.status >= 500;
}

export function createAppQueryClient(): QueryClient {
  const queryClient: QueryClient = new QueryClient({
    // Any mutation can add, remove, or orphan a tag (tag edits, deletes, adoption),
    // and the vocabulary is cached across pages, so every settled mutation marks it stale.
    mutationCache: new MutationCache({
      onSettled: () => invalidateAssetTagVocabulary(queryClient),
    }),
    defaultOptions: {
      queries: {
        retry: shouldRetryQuery,
      },
    },
  });
  return queryClient;
}
