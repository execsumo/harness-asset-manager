import { optimisticTags } from "../../../components/tags/optimistic-tags";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { queryPolicy } from "../../../lib/query";
import {
  createPermission,
  disablePermission,
  enablePermission,
  fetchPermissionsInventory,
  fetchPermissionDetail,
  promotePermission,
  reconcilePermission,
  setPermissionHarnesses,
  setPermissionTags,
  uninstallPermission,
  unmanagePermission,
} from "./management-client";
import { invalidatePermissionsQueries } from "./invalidation";
import { HOOKS_GC_TIME_MS, HOOKS_INVENTORY_REFETCH_INTERVAL_MS, HOOKS_STALE_TIME_MS, permissionsManagementKeys } from "./keys";

export { invalidatePermissionsQueries } from "./invalidation";
export { permissionsManagementKeys } from "./keys";

export function usePermissionsInventoryQuery() {
  return useQuery({
    queryKey: permissionsManagementKeys.inventory(),
    queryFn: fetchPermissionsInventory,
    refetchInterval: HOOKS_INVENTORY_REFETCH_INTERVAL_MS,
    ...queryPolicy(HOOKS_STALE_TIME_MS, HOOKS_GC_TIME_MS),
  });
}

export function useSetPermissionTagsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: [...permissionsManagementKeys.all, "tags"],
    mutationFn: ({ id, tags }: { id: string; tags: string[] }) =>
      setPermissionTags(id, tags),
    onMutate: ({ id, tags }) => optimisticTags(queryClient, { prefix: permissionsManagementKeys.all, collectionKey: "inventory", collections: ["entries"], identity: "id", detail: permissionsManagementKeys.detail(id) }, id, tags),
    onError: (_error, _variables, rollback) => rollback?.(),
    onSettled: () => queryClient.isMutating({ mutationKey: [...permissionsManagementKeys.all, "tags"] }) === 1 ? invalidatePermissionsQueries(queryClient) : undefined,
  });
}

export function useEnablePermissionMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: enablePermission,
    onSettled: () => invalidatePermissionsQueries(queryClient),
  });
}

export function useDisablePermissionMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: disablePermission,
    onSettled: () => invalidatePermissionsQueries(queryClient),
  });
}

export function useSetPermissionHarnessesMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: setPermissionHarnesses,
    onSettled: () => invalidatePermissionsQueries(queryClient),
  });
}

export function useUninstallPermissionMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: uninstallPermission,
    onSettled: () => invalidatePermissionsQueries(queryClient),
  });
}

export function usePermissionDetailQuery(id: string | null) {
  return useQuery({
    queryKey: permissionsManagementKeys.detail(id ?? "__none__"),
    queryFn: () => fetchPermissionDetail(id!),
    enabled: Boolean(id),
    ...queryPolicy(HOOKS_STALE_TIME_MS, HOOKS_GC_TIME_MS),
  });
}

export function useCreatePermissionMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createPermission,
    onSettled: () => invalidatePermissionsQueries(queryClient),
  });
}

export function usePromotePermissionMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: promotePermission,
    onSettled: () => invalidatePermissionsQueries(queryClient),
  });
}

export function useReconcilePermissionMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: reconcilePermission,
    onSettled: () => invalidatePermissionsQueries(queryClient),
  });
}

export function useUnmanagePermissionMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => unmanagePermission(id),
    onSettled: () => invalidatePermissionsQueries(queryClient),
  });
}

