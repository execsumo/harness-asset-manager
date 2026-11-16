import { optimisticTags } from "../../../components/tags/optimistic-tags";
import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { fetchJson, postJson, putJson } from "../../../api/http";
import type { ConfigsPayload, ConfigDiff } from "./types";

export const CONFIGS_KEYS = {
  all: ["configs"] as const,
  list: () => [...CONFIGS_KEYS.all, "list"] as const,
};

export const CONFIGS_REFETCH_INTERVAL_MS = 5_000;

export function useConfigsListQuery() {
  return useQuery({
    queryKey: CONFIGS_KEYS.list(),
    queryFn: async () => fetchJson<ConfigsPayload>("/configs/"),
    refetchInterval: CONFIGS_REFETCH_INTERVAL_MS,
  });
}

export async function invalidateConfigsQueries(queryClient: QueryClient): Promise<void> {
  await queryClient.invalidateQueries({ queryKey: CONFIGS_KEYS.all });
}

export function useConfigDiffMutation() {
  return useMutation({
    mutationFn: async (harness: string) => fetchJson<ConfigDiff>(`/configs/${encodeURIComponent(harness)}/diff`),
  });
}

export function useEnableConfigMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (harness: string) => postJson(`/configs/${encodeURIComponent(harness)}/enable`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CONFIGS_KEYS.all }),
  });
}

export function useDisableConfigMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (harness: string) => postJson(`/configs/${encodeURIComponent(harness)}/disable`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CONFIGS_KEYS.all }),
  });
}

export function useRestoreConfigMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (harness: string) => postJson(`/configs/${encodeURIComponent(harness)}/restore`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CONFIGS_KEYS.all }),
  });
}

export function useCaptureConfigsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (explicit: boolean) => postJson(`/configs/capture?explicit=${explicit}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CONFIGS_KEYS.all }),
  });
}

export function useSetConfigTagsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: [...CONFIGS_KEYS.all, "tags"],
    mutationFn: async ({ harness, tags }: { harness: string; tags: string[] }) => {
      await putJson(`/configs/${encodeURIComponent(harness)}/tags`, { tags });
    },
    onMutate: ({ harness, tags }) => optimisticTags(queryClient, { prefix: CONFIGS_KEYS.all, identity: "harness", collectionKey: "list", config: true }, harness, tags),
    onError: (_error, _variables, rollback) => rollback?.(),
    onSettled: () => queryClient.isMutating({ mutationKey: [...CONFIGS_KEYS.all, "tags"] }) === 1 ? queryClient.invalidateQueries({ queryKey: CONFIGS_KEYS.all }) : undefined,
  });
}
