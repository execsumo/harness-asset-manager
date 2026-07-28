import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import { queryPolicy } from "../../lib/query";
import { invalidateAgentsQueries } from "../agents/public";
import { invalidateMcpQueries } from "../mcp/public";
import { invalidateSkillsQueries } from "../skills/public";
import { fetchConfigSnapshots, fetchSettings, triggerConfigSnapshot, updateAutoAdopt, updateHarnessSupport } from "./api/client";
import type { SettingsData } from "./api/types";

const SETTINGS_STALE_TIME_MS = 60_000;
const SETTINGS_GC_TIME_MS = 15 * 60_000;

export const settingsKeys = {
  all: ["settings"] as const,
  detail: () => ["settings", "detail"] as const,
  snapshots: (harness?: string) => ["settings", "snapshots", harness ?? "all"] as const,
};

export function useSettingsQuery() {
  return useQuery({
    queryKey: settingsKeys.detail(),
    queryFn: fetchSettings,
    ...queryPolicy(SETTINGS_STALE_TIME_MS, SETTINGS_GC_TIME_MS),
  });
}

export function useConfigSnapshotsQuery(harness?: string) {
  return useQuery({
    queryKey: settingsKeys.snapshots(harness),
    queryFn: () => fetchConfigSnapshots(harness),
    ...queryPolicy(10_000, 60_000),
  });
}

export function useTriggerConfigSnapshotMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: triggerConfigSnapshot,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["settings", "snapshots"] });
    },
  });
}

export async function invalidateSettingsQueries(queryClient: QueryClient): Promise<void> {
  await queryClient.invalidateQueries({ queryKey: settingsKeys.all });
}

export function useHarnessSupportMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ harness, enabled }: { harness: string; enabled: boolean }) =>
      updateHarnessSupport(harness, enabled),
    onMutate: async ({ harness, enabled }) => {
      await queryClient.cancelQueries({ queryKey: settingsKeys.detail() });
      const previousSettings = queryClient.getQueryData<SettingsData>(settingsKeys.detail());
      if (previousSettings) {
        queryClient.setQueryData<SettingsData>(settingsKeys.detail(), {
          ...previousSettings,
          harnesses: previousSettings.harnesses.map((item) =>
            item.harness === harness
              ? {
                  ...item,
                  supportEnabled: enabled,
                }
              : item,
          ),
        });
      }
      return { previousSettings };
    },
    onError: (_error, _variables, context) => {
      if (context?.previousSettings) {
        queryClient.setQueryData(settingsKeys.detail(), context.previousSettings);
      }
    },
    onSuccess: async () => {
      await Promise.all([
        invalidateSkillsQueries(queryClient),
        invalidateMcpQueries(queryClient),
        invalidateSettingsQueries(queryClient),
      ]);
    },
  });
}

export function useAutoAdoptMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ family, enabled }: { family: string; enabled: boolean }) =>
      updateAutoAdopt(family, enabled),
    onMutate: async ({ family, enabled }) => {
      await queryClient.cancelQueries({ queryKey: settingsKeys.detail() });
      const previousSettings = queryClient.getQueryData<SettingsData>(settingsKeys.detail());
      if (previousSettings) {
        queryClient.setQueryData<SettingsData>(settingsKeys.detail(), {
          ...previousSettings,
          autoAdopt: {
            ...previousSettings.autoAdopt,
            [family]: enabled,
          },
        });
      }
      return { previousSettings };
    },
    onError: (_error, _variables, context) => {
      if (context?.previousSettings) {
        queryClient.setQueryData(settingsKeys.detail(), context.previousSettings);
      }
    },
    onSuccess: async () => {
      await Promise.all([
        invalidateSkillsQueries(queryClient),
        invalidateMcpQueries(queryClient),
        invalidateSettingsQueries(queryClient),
        invalidateAgentsQueries(queryClient),
      ]);
    },
  });
}
