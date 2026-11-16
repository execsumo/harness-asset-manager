import { optimisticTags } from "../../../components/tags/optimistic-tags";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { queryPolicy } from "../../../lib/query";
import {
  adoptMcpServer,
  checkMcpServerAvailability,
  disableMcpServer,
  enableMcpServer,
  fetchMcpInventory,
  setMcpServerArchived,
  fetchMcpServerDetail,
  fetchMcpNeedsReviewByServer,
  reconcileMcpServer,
  setMcpServerHarnesses,
  setMcpServerTags,
  uninstallMcpServer,
} from "./management-client";
import { invalidateMcpQueries } from "./invalidation";
import { MCP_GC_TIME_MS, MCP_INVENTORY_REFETCH_INTERVAL_MS, MCP_STALE_TIME_MS, mcpManagementKeys } from "./keys";

export { invalidateMcpQueries } from "./invalidation";
export { mcpManagementKeys } from "./keys";

export function useMcpInventoryQuery(includeArchived = false) {
  return useQuery({
    queryKey: [...mcpManagementKeys.inventory(), includeArchived],
    queryFn: () => fetchMcpInventory(includeArchived),
    refetchInterval: MCP_INVENTORY_REFETCH_INTERVAL_MS,
    ...queryPolicy(MCP_STALE_TIME_MS, MCP_GC_TIME_MS),
  });
}

export function useSetMcpServerTagsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: [...mcpManagementKeys.all, "tags"],
    mutationFn: ({ name, tags }: { name: string; tags: string[] }) =>
      setMcpServerTags(name, tags),
    onMutate: ({ name, tags }) => optimisticTags(queryClient, { prefix: mcpManagementKeys.all, collectionKey: "inventory", collections: ["entries"], identity: "name", detail: mcpManagementKeys.detail(name) }, name, tags),
    onError: (_error, _variables, rollback) => rollback?.(),
    onSettled: () => queryClient.isMutating({ mutationKey: [...mcpManagementKeys.all, "tags"] }) === 1 ? invalidateMcpQueries(queryClient) : undefined,
  });
}

export function useEnableMcpServerMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: enableMcpServer,
    onSettled: () => invalidateMcpQueries(queryClient),
  });
}

export function useDisableMcpServerMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: disableMcpServer,
    onSettled: () => invalidateMcpQueries(queryClient),
  });
}

export function useSetMcpServerHarnessesMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: setMcpServerHarnesses,
    onSettled: () => invalidateMcpQueries(queryClient),
  });
}

export function useUninstallMcpServerMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: uninstallMcpServer,
    onSettled: () => invalidateMcpQueries(queryClient),
  });
}

export function useMcpServerDetailQuery(name: string | null) {
  return useQuery({
    queryKey: mcpManagementKeys.detail(name ?? "__none__"),
    queryFn: () => fetchMcpServerDetail(name!),
    enabled: Boolean(name),
    ...queryPolicy(MCP_STALE_TIME_MS, MCP_GC_TIME_MS),
  });
}

export function useCheckMcpServerAvailabilityMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: checkMcpServerAvailability,
    retry: 2,
    retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 4000),
    onSettled: () => invalidateMcpQueries(queryClient),
  });
}

export function useMcpNeedsReviewByServerQuery() {
  return useQuery({
    queryKey: mcpManagementKeys.needsReviewByServer(),
    queryFn: fetchMcpNeedsReviewByServer,
    ...queryPolicy(MCP_STALE_TIME_MS, MCP_GC_TIME_MS),
  });
}

export function useReconcileMcpServerMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: reconcileMcpServer,
    onSettled: () => invalidateMcpQueries(queryClient),
  });
}

export function useAdoptMcpServerMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: adoptMcpServer,
    onSettled: () => invalidateMcpQueries(queryClient),
  });
}

export function useSetMcpServerArchivedMutation() {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: ({ name, archived }: { name: string; archived: boolean }) => setMcpServerArchived(name, archived), onSettled: () => invalidateMcpQueries(queryClient) });
}
