import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useToast } from "../../../components/Toast";
import { flattenUniquePageItems, queryPolicy, settleInvalidate } from "../../../lib/query";
import { invalidateMcpQueries } from "../../mcp/public";
import { useMarketplaceCopy } from "../i18n";
import { useInstallingState } from "../model/installing-context";
import {
  fetchMcpMarketplaceDetail,
  fetchMcpMarketplacePopular,
  addMcpServer,
  searchMcpMarketplace,
} from "./mcp-client";
import type {
  AddMcpServerResponseDto,
  McpMarketplaceItemDto,
  McpMarketplacePageResultDto,
} from "./mcp-types";

const MCP_MARKETPLACE_STALE_TIME_MS = 60_000;
const MCP_MARKETPLACE_GC_TIME_MS = 15 * 60_000;
const PAGE_SIZE = 20;

export const mcpMarketplaceKeys = {
  all: ["marketplace", "mcp"] as const,
  feed: (query: string) =>
    ["marketplace", "mcp", "feed", query] as const,
  detail: (qualifiedName: string) =>
    ["marketplace", "mcp", "detail", qualifiedName] as const,
};

export function useMcpMarketplaceFeedQuery(query: string) {
  const trimmed = query.trim();
  const usePopular = !trimmed;

  return useInfiniteQuery({
    queryKey: mcpMarketplaceKeys.feed(trimmed || "__popular__"),
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      usePopular
        ? fetchMcpMarketplacePopular({ limit: PAGE_SIZE, offset: pageParam })
        : searchMcpMarketplace({
            query: trimmed,
            limit: PAGE_SIZE,
            offset: pageParam,
          }),
    getNextPageParam: (lastPage) =>
      lastPage.hasMore ? lastPage.nextOffset ?? undefined : undefined,
    ...queryPolicy(MCP_MARKETPLACE_STALE_TIME_MS, MCP_MARKETPLACE_GC_TIME_MS),
  });
}

export function useMcpMarketplaceDetailQuery(qualifiedName: string | null) {
  return useQuery({
    queryKey: mcpMarketplaceKeys.detail(qualifiedName ?? "__none__"),
    queryFn: () => fetchMcpMarketplaceDetail(qualifiedName!),
    enabled: Boolean(qualifiedName),
    ...queryPolicy(MCP_MARKETPLACE_STALE_TIME_MS, MCP_MARKETPLACE_GC_TIME_MS),
  });
}

/**
 * Shared marketplace install mutation used by the detail view.
 * Handles: pending-state publication, inventory invalidation, and success/error toasts.
 */
export function useAddMcpServerMutation() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const { begin, finish } = useInstallingState();
  const copy = useMarketplaceCopy();
  const settle = settleInvalidate(queryClient, invalidateMcpQueries);

  return useMutation<
    AddMcpServerResponseDto,
    Error,
    {
      qualifiedName: string;
      displayName?: string;
    }
  >({
    mutationFn: ({ qualifiedName }) =>
      addMcpServer({ qualifiedName }),
    onMutate: ({ qualifiedName }) => {
      begin(qualifiedName);
    },
    onSuccess: (response, { displayName }) => {
      toast(copy.detail.installButton.addedToMcp(displayName ?? response.server.name));
    },
    onError: (error) => {
      toast(error instanceof Error ? error.message : copy.detail.installButton.installFailed);
    },
    // Refetch the central inventory so the card button flips to "Open in MCPs" in place,
    // and keep the card's installing state until it has. A failed install may still have
    // written part of the config, so it refetches too.
    onSettled: async (_data, _err, { qualifiedName }) => {
      await settle();
      finish(qualifiedName);
    },
  });
}

export function flattenMcpMarketplaceItems(
  data: { pages: McpMarketplacePageResultDto[] } | undefined,
): McpMarketplaceItemDto[] {
  return flattenUniquePageItems(data, (item) => item.qualifiedName);
}
