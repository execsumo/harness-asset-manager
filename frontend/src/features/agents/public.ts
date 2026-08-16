import { useAgentsInventoryQuery } from "./api/queries";
import { invalidateAgentsQueries } from "./api/invalidation";
import type { AgentInventoryDto } from "./api/types";

export const agentsRoutes = {
  index: "/agents",
  inUse: "/agents",
  needsReview: "/agents?status=untracked",
} as const;

export { useAgentsInventoryQuery, invalidateAgentsQueries, type AgentInventoryDto };
