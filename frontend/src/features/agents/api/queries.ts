import { optimisticTags } from "../../../components/tags/optimistic-tags";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchAgentsInventory, fetchAgentDetail, fetchHermesOptions, createAgent, updateAgent, adoptAgent, adoptAllAgents, deleteAgent, enableAgent, disableAgent, setAgentTags, unmanageAgent, setAgentArchived } from "./client";
import { AGENTS_LIST_REFETCH_INTERVAL_MS, agentsKeys } from "./keys";

export function useHermesOptionsQuery() {
  return useQuery({
    queryKey: agentsKeys.hermesOptions(),
    queryFn: fetchHermesOptions,
    staleTime: 60_000,
  });
}

export function useAgentsInventoryQuery(includeArchived = false) {
  return useQuery({
    queryKey: [...agentsKeys.list(), includeArchived],
    queryFn: () => fetchAgentsInventory(includeArchived),
    refetchInterval: AGENTS_LIST_REFETCH_INTERVAL_MS,
  });
}

export function useAgentDetailQuery(ref: string) {
  return useQuery({
    queryKey: agentsKeys.detail(ref),
    queryFn: () => fetchAgentDetail(ref),
  });
}

export function useSetAgentTagsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: [...agentsKeys.all, "tags"],
    mutationFn: ({ ref, tags }: { ref: string; tags: string[] }) => setAgentTags(ref, tags),
    onMutate: ({ ref, tags }) => optimisticTags(queryClient, { prefix: agentsKeys.all, collectionKey: "list", collections: ["entries"], identity: "ref", detail: agentsKeys.detail(ref) }, ref, tags),
    onError: (_error, _variables, rollback) => rollback?.(),
    onSettled: () => {
      if (queryClient.isMutating({ mutationKey: [...agentsKeys.all, "tags"] }) === 1) {
        return queryClient.invalidateQueries({ queryKey: agentsKeys.all });
      }
    },
  });
}

export function useEnableAgentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ref, harness }: { ref: string; harness: string }) => enableAgent(ref, harness),
    onSuccess: (_, { ref }) => {
      queryClient.invalidateQueries({ queryKey: agentsKeys.list() });
      queryClient.invalidateQueries({ queryKey: agentsKeys.detail(ref) });
    },
  });
}

export function useDisableAgentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ref, harness }: { ref: string; harness: string }) => disableAgent(ref, harness),
    onSuccess: (_, { ref }) => {
      queryClient.invalidateQueries({ queryKey: agentsKeys.list() });
      queryClient.invalidateQueries({ queryKey: agentsKeys.detail(ref) });
    },
  });
}

export function useAdoptAgentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ref, onConflict }: { ref: string; onConflict?: "keep_store" | "replace_store" }) => adoptAgent(ref, onConflict),
    onSuccess: (data) => {
      if (!data || !("conflict" in data)) {
        queryClient.invalidateQueries({ queryKey: agentsKeys.list() });
      }
    },
  });
}

export function useAdoptAllAgentsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => adoptAllAgents(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: agentsKeys.list() });
    },
  });
}

export function useDeleteAgentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteAgent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: agentsKeys.list() });
    },
  });
}

export function useUpdateAgentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ref, request }: Parameters<typeof updateAgent>[0] & { ref: string }) => updateAgent({ ref, request }),
    onSuccess: (_, { ref }) => {
      queryClient.invalidateQueries({ queryKey: agentsKeys.list() });
      queryClient.invalidateQueries({ queryKey: agentsKeys.detail(ref) });
    },
  });
}

export function useCreateAgentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: Parameters<typeof createAgent>[0]) => createAgent(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: agentsKeys.list() });
    },
  });
}

export function useUnmanageAgentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ref: string) => unmanageAgent(ref),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: agentsKeys.list() });
    },
  });
}


export function useSetAgentArchivedMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ref, archived }: { ref: string; archived: boolean }) => setAgentArchived(ref, archived),
    onSuccess: (_, { ref }) => {
      queryClient.invalidateQueries({ queryKey: agentsKeys.list() });
      queryClient.invalidateQueries({ queryKey: agentsKeys.detail(ref) });
    },
  });
}
