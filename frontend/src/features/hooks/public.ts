export {
  useCreateHookMutation,
  useDisableHookMutation,
  useEnableHookMutation,
  useHooksInventoryQuery,
  useHookDetailQuery,
  usePromoteHookMutation,
  useReconcileHookMutation,
  useSetHookHarnessesMutation,
  useUninstallHookMutation,
} from "./api/management-queries";
export { createHook } from "./api/management-client";
export { invalidateHooksQueries } from "./api/invalidation";
export { hooksManagementKeys } from "./api/keys";
export type {
  HookBindingDto,
  HookInventoryColumnDto,
  HookInventoryDto,
  HookInventoryEntryDto,
  HookSpecDto,
} from "./api/management-types";
export { isHooksHarnessAddressable } from "./model/selectors";

export const hooksRoutes = {
  index: "/hooks",
  inUse: "/hooks",
  needsReview: "/hooks?status=untracked",
} as const;
