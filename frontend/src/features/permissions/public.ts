export {
  useCreatePermissionMutation,
  useDisablePermissionMutation,
  useEnablePermissionMutation,
  usePermissionsInventoryQuery,
  usePermissionDetailQuery,
  usePromotePermissionMutation,
  useReconcilePermissionMutation,
  useSetPermissionHarnessesMutation,
  useUninstallPermissionMutation,
} from "./api/management-queries";
export { createPermission } from "./api/management-client";
export { invalidatePermissionsQueries } from "./api/invalidation";
export { permissionsManagementKeys } from "./api/keys";
export type {
  PermissionBindingDto,
  PermissionInventoryColumnDto,
  PermissionInventoryDto,
  PermissionInventoryEntryDto,
  PermissionSpecDto,
} from "./api/management-types";
export { isPermissionsHarnessAddressable } from "./model/selectors";

export const permissionsRoutes = {
  index: "/permissions",
  // Legacy paths kept as redirect sources; both now resolve to the unified inventory.
  inUse: "/permissions",
  needsReview: "/permissions",
} as const;
