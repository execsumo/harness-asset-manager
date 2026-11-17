import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import { queryPolicy, settleInvalidate } from "../../lib/query";
import { invalidateAgentsQueries } from "../agents/public";
import { invalidateConfigsQueries } from "../configs/public";
import { invalidateHooksQueries } from "../hooks/public";
import { invalidateMcpQueries } from "../mcp/public";
import { invalidatePermissionsQueries } from "../permissions/public";
import { invalidateSkillsQueries } from "../skills/public";
import { invalidateSlashCommandQueries } from "../slash-commands/public";
import { fetchSettings, updateAutoAdopt, updateAutoAdoptHarnesses, updateDisplayPreference, updateHarnessSupport } from "./api/client";
import type { SettingsData } from "./api/types";

const SETTINGS_STALE_TIME_MS = 60_000;
const SETTINGS_GC_TIME_MS = 15 * 60_000;

export const settingsKeys = {
  all: ["settings"] as const,
  detail: () => ["settings", "detail"] as const,
};

export function useSettingsQuery() {
  return useQuery({
    queryKey: settingsKeys.detail(),
    queryFn: fetchSettings,
    ...queryPolicy(SETTINGS_STALE_TIME_MS, SETTINGS_GC_TIME_MS),
  });
}

export async function invalidateSettingsQueries(queryClient: QueryClient): Promise<void> {
  await queryClient.invalidateQueries({ queryKey: settingsKeys.all });
}

// Harness support and auto-adopt decide which assets exist on disk for every family, so
// settling them refreshes every capability family. Imported from each feature's public
// entry rather than app/capability-registry, which imports this module.
// A function, so the imports are read at call time even if feature modules import each other.
const settleAllFamilies = (queryClient: QueryClient) =>
  settleInvalidate(
    queryClient,
    invalidateSettingsQueries,
    invalidateSkillsQueries,
    invalidateMcpQueries,
    invalidateAgentsQueries,
    invalidateHooksQueries,
    invalidatePermissionsQueries,
    invalidateSlashCommandQueries,
    invalidateConfigsQueries,
  );

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
    onSettled: settleAllFamilies(queryClient),
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
    onSettled: settleAllFamilies(queryClient),
  });
}

export function useAutoAdoptHarnessesMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ family, harnesses }: { family: string; harnesses: string[] }) =>
      updateAutoAdoptHarnesses(family, harnesses),
    onMutate: async ({ family, harnesses }) => {
      await queryClient.cancelQueries({ queryKey: settingsKeys.detail() });
      const previousSettings = queryClient.getQueryData<SettingsData>(settingsKeys.detail());
      if (previousSettings) {
        queryClient.setQueryData<SettingsData>(settingsKeys.detail(), {
          ...previousSettings,
          autoAdoptHarnesses: {
            ...previousSettings.autoAdoptHarnesses,
            [family]: harnesses,
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
    onSettled: settleInvalidate(queryClient, invalidateSettingsQueries),
  });
}

export type DisplayPreferenceKey = "showSkillAgentTags";

const DISPLAY_DEFAULTS: Record<DisplayPreferenceKey, boolean> = { showSkillAgentTags: true };

/** UI display preferences, falling back to defaults while settings load or if they fail. */
export function useDisplayPreferences(): Record<DisplayPreferenceKey, boolean> {
  const { data } = useSettingsQuery();
  return { ...DISPLAY_DEFAULTS, ...(data?.display ?? {}) };
}

export function useDisplayPreferenceMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ key, value }: { key: DisplayPreferenceKey; value: boolean }) =>
      updateDisplayPreference(key, value),
    onMutate: async ({ key, value }) => {
      await queryClient.cancelQueries({ queryKey: settingsKeys.detail() });
      const previousSettings = queryClient.getQueryData<SettingsData>(settingsKeys.detail());
      if (previousSettings) {
        queryClient.setQueryData<SettingsData>(settingsKeys.detail(), {
          ...previousSettings,
          display: { ...DISPLAY_DEFAULTS, ...(previousSettings.display ?? {}), [key]: value },
        });
      }
      return { previousSettings };
    },
    onError: (_error, _variables, context) => {
      if (context?.previousSettings) {
        queryClient.setQueryData(settingsKeys.detail(), context.previousSettings);
      }
    },
    onSettled: settleInvalidate(queryClient, invalidateSettingsQueries),
  });
}
