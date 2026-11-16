import { useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useCallback, useSyncExternalStore } from "react";
import { fetchJson } from "../../api/http";

export const assetTagKeys = {
  all: ["asset-tags"] as const,
  vocabulary: () => ["asset-tags", "vocabulary"] as const,
};

// Every page shows the shared vocabulary, so it is cached across route changes
// instead of being refetched on each mount. Mutations, Refresh, rename, and window
// focus refresh it; see App's query client and invalidateCapabilityQueries.
export const ASSET_TAG_VOCABULARY_STALE_TIME_MS = 60_000;
const VOCABULARY_RETRY_DELAY_MS = 5_000;

/** Accept only a list of tag strings; anything else is treated as an empty vocabulary. */
function vocabularyFrom(result: { tags?: unknown } | null | undefined): string[] {
  const tags = result?.tags;
  return Array.isArray(tags) ? tags.filter((tag): tag is string => typeof tag === "string") : [];
}

export async function fetchAssetTagVocabulary(): Promise<string[]> {
  return vocabularyFrom(await fetchJson<{ tags?: unknown }>("/asset-tags/"));
}

const vocabularyQuery = {
  queryKey: assetTagKeys.vocabulary(),
  queryFn: fetchAssetTagVocabulary,
  staleTime: ASSET_TAG_VOCABULARY_STALE_TIME_MS,
};

const EMPTY_VOCABULARY: string[] = [];

/**
 * The shared vocabulary, from cache when any page already loaded it.
 *
 * useQuery drives fetching, retries and staleness, but the value is read straight
 * from the cache: useQuery defers its re-render by a scheduler tick, and a tag bar
 * should show the vocabulary the moment it lands.
 */
export function useAssetTagVocabulary(): { vocabulary: string[]; refresh: () => void } {
  const queryClient = useQueryClient();
  const { refetch } = useAssetTagVocabularyQuery();
  const subscribe = useCallback(
    (onChange: () => void) => queryClient.getQueryCache().subscribe(onChange),
    [queryClient],
  );
  const vocabulary = useSyncExternalStore(
    subscribe,
    () => queryClient.getQueryData<string[]>(assetTagKeys.vocabulary()) ?? EMPTY_VOCABULARY,
  );
  const refresh = useCallback(() => { void refetch({ cancelRefetch: false }); }, [refetch]);
  return { vocabulary, refresh };
}

function useAssetTagVocabularyQuery() {
  return useQuery({
    ...vocabularyQuery,
    // Focus is handled by an explicit window listener in useSharedTagCounts.
    refetchOnWindowFocus: false,
    // Keep retrying while a page shows the bar; a page unmount cancels the retries.
    retry: true,
    retryDelay: VOCABULARY_RETRY_DELAY_MS,
  });
}

export function prefetchAssetTagVocabulary(queryClient: QueryClient): Promise<void> {
  return queryClient.prefetchQuery(vocabularyQuery);
}

export function invalidateAssetTagVocabulary(queryClient: QueryClient): Promise<void> {
  // Join a refetch already in flight rather than restarting it.
  return queryClient.invalidateQueries({ queryKey: assetTagKeys.vocabulary() }, { cancelRefetch: false });
}
