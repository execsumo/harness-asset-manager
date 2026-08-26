import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchJson, postJson, putJson } from "../../../api/http";
import type { ConfigsPayload, ConfigDiff } from "./types";

export const CONFIGS_KEYS = {
  all: ["configs"] as const,
  list: () => [...CONFIGS_KEYS.all, "list"] as const,
};

export function useConfigsListQuery() {
  return useQuery({
    queryKey: CONFIGS_KEYS.list(),
    queryFn: async () => fetchJson<ConfigsPayload>("/configs/"),
  });
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
    mutationFn: async ({ harness, tags }: { harness: string; tags: string[] }) => {
      await putJson(`/configs/${encodeURIComponent(harness)}/tags`, { tags });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CONFIGS_KEYS.all }),
  });
}
