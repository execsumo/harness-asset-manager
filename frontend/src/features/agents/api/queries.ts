import { optimisticTags } from "../../../components/tags/optimistic-tags";
import { useQuery, useMutation, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { settleInvalidate } from "../../../lib/query";
import { invalidateSkillsQueries } from "../../skills/public";
import { fetchAgentsInventory, fetchAgentDetail, fetchHermesOptions, createAgent, updateAgent, adoptAgent, adoptAllAgents, deleteAgent, enableAgent, disableAgent, setAgentTags, unmanageAgent, setAgentArchived } from "./client";
import { invalidateAgentsQueries } from "./invalidation";
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

// Skills payloads carry each skill's agent roster, and agent detail lists skills, so any
// mutation that can change which agents hold a skill must refresh both families.
const settleAgents = (queryClient: QueryClient) => settleInvalidate(queryClient, invalidateAgentsQueries);
const settleAgentsAndSkills = (queryClient: QueryClient) =>
  settleInvalidate(queryClient, invalidateAgentsQueries, invalidateSkillsQueries);

export function useEnableAgentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ref, harness }: { ref: string; harness: string }) => enableAgent(ref, harness),
    onSettled: settleAgents(queryClient),
  });
}

export function useDisableAgentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ref, harness }: { ref: string; harness: string }) => disableAgent(ref, harness),
    onSettled: settleAgents(queryClient),
  });
}

export function useAdoptAgentMutation() {
  const queryClient = useQueryClient();
  const settle = settleAgentsAndSkills(queryClient);
  return useMutation({
    mutationFn: ({ ref, onConflict }: { ref: string; onConflict?: "keep_store" | "replace_store" }) => adoptAgent(ref, onConflict),
    // A conflict answer changed nothing on disk: the caller shows a resolution dialog and
    // retries, so skip the refetch that would only flash the unchanged list.
    onSettled: (data) => (data && "conflict" in data ? undefined : settle()),
  });
}

export function useAdoptAllAgentsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => adoptAllAgents(),
    onSettled: settleAgentsAndSkills(queryClient),
  });
}

export function useDeleteAgentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteAgent,
    onSettled: settleAgentsAndSkills(queryClient),
  });
}

export function useUpdateAgentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ref, request }: Parameters<typeof updateAgent>[0] & { ref: string }) => updateAgent({ ref, request }),
    onSettled: settleAgentsAndSkills(queryClient),
  });
}

export function useCreateAgentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: Parameters<typeof createAgent>[0]) => createAgent(request),
    onSettled: settleAgentsAndSkills(queryClient),
  });
}

export function useUnmanageAgentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ref: string) => unmanageAgent(ref),
    onSettled: settleAgentsAndSkills(queryClient),
  });
}

export function useSetAgentArchivedMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ref, archived }: { ref: string; archived: boolean }) => setAgentArchived(ref, archived),
    onSettled: settleAgentsAndSkills(queryClient),
  });
}
