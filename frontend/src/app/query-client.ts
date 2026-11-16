import { MutationCache, QueryClient } from "@tanstack/react-query";

import { invalidateAssetTagVocabulary } from "../components/tags/asset-tag-vocabulary";

export function createAppQueryClient(): QueryClient {
  const queryClient: QueryClient = new QueryClient({
    // Any mutation can add, remove, or orphan a tag (tag edits, deletes, adoption),
    // and the vocabulary is cached across pages, so every settled mutation marks it stale.
    mutationCache: new MutationCache({
      onSettled: () => invalidateAssetTagVocabulary(queryClient),
    }),
    defaultOptions: {
      queries: {
        retry: 1,
      },
    },
  });
  return queryClient;
}
