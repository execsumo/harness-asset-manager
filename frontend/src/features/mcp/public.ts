export {
  useAdoptMcpServerMutation,
  useDisableMcpServerMutation,
  useEnableMcpServerMutation,
  useMcpInventoryQuery,
  useMcpNeedsReviewByServerQuery,
  useMcpServerDetailQuery,
  useReconcileMcpServerMutation,
  useSetMcpServerHarnessesMutation,
  useUninstallMcpServerMutation,
} from "./api/management-queries";
export { checkMcpServerAvailability } from "./api/management-client";
export { invalidateMcpQueries } from "./api/invalidation";
export { mcpManagementKeys } from "./api/keys";
export type {
  McpBindingDto,
  McpIdentitySightingDto,
  McpInventoryColumnDto,
  McpInventoryDto,
  McpInventoryEntryDto,
} from "./api/management-types";
export { isMcpHarnessAddressable } from "./model/selectors";

export const mcpRoutes = {
  index: "/mcp",
  inUse: "/mcp",
  needsReview: "/mcp?status=untracked",
  marketplace: "/marketplace/mcp",
} as const;
