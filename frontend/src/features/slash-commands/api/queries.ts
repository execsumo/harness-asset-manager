import { optimisticTags } from "../../../components/tags/optimistic-tags";
import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";

import { queryPolicy, settleInvalidate } from "../../../lib/query";
import {
  createSlashCommand,
  deleteSlashCommand,
  fetchSlashCommands,
  importSlashCommand,
  resolveSlashCommandReview,
  setSlashCommandTags,
  setSlashCommandArchived,
  syncSlashCommand,
  unmanageSlashCommand,
  updateSlashCommand,
} from "./client";
import {
  SLASH_COMMANDS_GC_TIME_MS,
  SLASH_COMMANDS_REFETCH_INTERVAL_MS,
  SLASH_COMMANDS_STALE_TIME_MS,
  slashCommandKeys,
} from "./keys";
import type {
  SlashCommandMutationRequest,
  SlashCommandResolveRequest,
  SlashCommandUpdateRequest,
  SlashSyncRequest,
} from "./types";

export { slashCommandKeys } from "./keys";

export function useSlashCommandsQuery(includeArchived = false) {
  return useQuery({
    queryKey: [...slashCommandKeys.list(), includeArchived],
    queryFn: () => fetchSlashCommands(includeArchived),
    refetchInterval: SLASH_COMMANDS_REFETCH_INTERVAL_MS,
    ...queryPolicy(SLASH_COMMANDS_STALE_TIME_MS, SLASH_COMMANDS_GC_TIME_MS),
  });
}

export async function invalidateSlashCommandQueries(queryClient: QueryClient): Promise<void> {
  await queryClient.invalidateQueries({ queryKey: slashCommandKeys.all });
}

export function useSetSlashCommandTagsMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationKey: [...slashCommandKeys.all, "tags"],
    mutationFn: ({ name, tags }: { name: string; tags: string[] }) =>
      setSlashCommandTags(name, tags),
    onMutate: ({ name, tags }) => optimisticTags(queryClient, { prefix: slashCommandKeys.all, collectionKey: "list", collections: ["commands", "reviewCommands"], identity: "name" }, name, tags),
    onError: (_error, _variables, rollback) => rollback?.(),
    onSettled: () => queryClient.isMutating({ mutationKey: [...slashCommandKeys.all, "tags"] }) === 1 ? invalidateSlashCommandQueries(queryClient) : undefined,
  });
}

export function useCreateSlashCommandMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SlashCommandMutationRequest) => createSlashCommand(body),
    onSettled: settleInvalidate(queryClient, invalidateSlashCommandQueries),
  });
}

export function useUpdateSlashCommandMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ name, body }: { name: string; body: SlashCommandUpdateRequest }) =>
      updateSlashCommand(name, body),
    onSettled: settleInvalidate(queryClient, invalidateSlashCommandQueries),
  });
}

export function useSyncSlashCommandMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ name, body }: { name: string; body: SlashSyncRequest }) =>
      syncSlashCommand(name, body),
    onSettled: settleInvalidate(queryClient, invalidateSlashCommandQueries),
  });
}

export function useDeleteSlashCommandMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ name }: { name: string }) => deleteSlashCommand(name),
    onSettled: settleInvalidate(queryClient, invalidateSlashCommandQueries),
  });
}

export function useImportSlashCommandMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: importSlashCommand,
    onSettled: settleInvalidate(queryClient, invalidateSlashCommandQueries),
  });
}

export function useResolveSlashCommandReviewMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SlashCommandResolveRequest) => resolveSlashCommandReview(body),
    onSettled: settleInvalidate(queryClient, invalidateSlashCommandQueries),
  });
}

export function useUnmanageSlashCommandMutation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ name }: { name: string }) => unmanageSlashCommand(name),
    onSettled: settleInvalidate(queryClient, invalidateSlashCommandQueries),
  });
}


export function useSetSlashCommandArchivedMutation() {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: ({ name, archived }: { name: string; archived: boolean }) => setSlashCommandArchived(name, archived), onSettled: settleInvalidate(queryClient, invalidateSlashCommandQueries) });
}
