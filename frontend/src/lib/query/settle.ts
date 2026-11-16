import type { QueryClient, QueryKey } from "@tanstack/react-query";

/** A query key to invalidate, or a family invalidator such as `invalidateAgentsQueries`. */
export type SettleTarget = QueryKey | ((queryClient: QueryClient) => Promise<unknown>);

/**
 * The one settle policy for a mutation's `onSettled`: when the mutation ends, success or
 * error, invalidate `targets` and stay pending until the refetches finish. The caller's
 * pending state then clears only once the cache holds the server's answer, and a failed or
 * partly applied mutation still refetches.
 *
 * A failed refetch is swallowed. `onSettled` runs before react-query reports the mutation
 * result, so a rejection here would turn a successful mutation into a failed one, or replace
 * the original mutation error.
 */
export function settleInvalidate(queryClient: QueryClient, ...targets: SettleTarget[]): () => Promise<void> {
  return async () => {
    await Promise.allSettled(
      targets.map(async (target) =>
        typeof target === "function" ? target(queryClient) : queryClient.invalidateQueries({ queryKey: target }),
      ),
    );
  };
}
