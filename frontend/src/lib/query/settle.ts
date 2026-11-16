import type { Query, QueryClient, QueryKey } from "@tanstack/react-query";

/** A query key to invalidate, or a family invalidator such as `invalidateAgentsQueries`. */
export type SettleTarget = QueryKey | ((queryClient: QueryClient) => Promise<unknown>);

/**
 * The one settle policy for a mutation's `onSettled`: when the mutation ends, success or
 * error, invalidate `targets` and stay pending until the refetches finish. The caller's
 * pending state then clears only once the cache holds the server's answer, and a failed or
 * partly applied mutation still refetches.
 *
 * When mutations overlap, a later `invalidateQueries` cancels an earlier in-flight refetch,
 * and the earlier call can then resolve before any fresh data lands. So this waits until
 * every query it touched has stopped fetching, which includes the newer refetch that
 * replaced its own.
 *
 * A failed refetch is swallowed. `onSettled` runs before react-query reports the mutation
 * result, so a rejection here would turn a successful mutation into a failed one, or replace
 * the original mutation error.
 */
export function settleInvalidate(queryClient: QueryClient, ...targets: SettleTarget[]): () => Promise<void> {
  return async () => {
    const cache = queryClient.getQueryCache();
    const fetched = new Set<Query>();
    const busy = () => [...fetched].some((query) => query.state.fetchStatus === "fetching");
    let wake: (() => void) | undefined;
    const unsubscribe = cache.subscribe((event) => {
      if (event.type === "updated" && event.action.type === "fetch") fetched.add(event.query);
      if (!busy()) wake?.();
    });
    try {
      await Promise.allSettled(
        targets.map(async (target) =>
          typeof target === "function" ? target(queryClient) : queryClient.invalidateQueries({ queryKey: target }),
        ),
      );
      while (busy()) await new Promise<void>((resolve) => { wake = resolve; });
    } finally {
      unsubscribe();
    }
await new Promise<void>((resolve) => setTimeout(resolve, 0));
  };
}
