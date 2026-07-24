import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { fetchAgentsInventory, scaffoldAgent, updateAgent, adoptAgent, adoptAllAgents, deleteAgent, enableAgent, disableAgent } from "./client";
import { agentsKeys } from "./keys";
import type { AgentAdoptConflict, AdoptAllResponse } from "./types";

export function useAgentsInventoryQuery() {
  return useQuery({
    queryKey: agentsKeys.list(),
    queryFn: fetchAgentsInventory,
  });
}

export function useEnableAgentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ref, harness }: { ref: string; harness: string }) => enableAgent(ref, harness),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: agentsKeys.list() });
    },
  });
}

export function useDisableAgentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ ref, harness }: { ref: string; harness: string }) => disableAgent(ref, harness),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: agentsKeys.list() });
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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: agentsKeys.list() });
    },
  });
}

export function useCreateAgentMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (request: Parameters<typeof scaffoldAgent>[0]) => scaffoldAgent(request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: agentsKeys.list() });
    },
  });
}
