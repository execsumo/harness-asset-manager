import type { QueryClient } from "@tanstack/react-query";

import { invalidateAssetTagVocabulary } from "../../components/tags/asset-tag-vocabulary";
import { invalidateMarketplaceQueries } from "../../features/marketplace/public";
import { invalidateMcpQueries } from "../../features/mcp/public";
import { invalidateSettingsQueries } from "../../features/settings/public";
import { invalidateSkillsQueries } from "../../features/skills/public";
import { invalidateSlashCommandQueries } from "../../features/slash-commands/public";
import { invalidateHooksQueries } from "../../features/hooks/public";
import { invalidateAgentsQueries } from "../../features/agents/public";
import { invalidateConfigsQueries } from "../../features/configs/public";
import { invalidatePermissionsQueries } from "../../features/permissions/public";

export async function invalidateCapabilityQueries(queryClient: QueryClient): Promise<void> {
  // Dispatched first so a mounted tag bar's refetch is the one the vocabulary
  // invalidation below joins, instead of a second request after it.
  if (typeof window !== "undefined") window.dispatchEvent(new Event("asset-tags-changed"));
  await Promise.all([
    invalidateAssetTagVocabulary(queryClient),
    invalidateSkillsQueries(queryClient),
    invalidateMcpQueries(queryClient),
    invalidateSettingsQueries(queryClient),
    invalidateMarketplaceQueries(queryClient),
    invalidateSlashCommandQueries(queryClient),
    invalidateHooksQueries(queryClient),
    invalidateAgentsQueries(queryClient),
    invalidatePermissionsQueries(queryClient),
    invalidateConfigsQueries(queryClient),
  ]);
}
