import type {
  PermissionBindingDto,
  PermissionInventoryColumnDto,
  PermissionInventoryDto,
  PermissionInventoryEntryDto,
} from "../api/management-types";
import { permissionsCopy, type PermissionsCopy } from "../i18n";

export type PermissionsMatrixCellState = "enabled" | "disabled" | "different" | "unavailable" | "observed";

export interface PermissionsMatrixCellModel {
  state: PermissionsMatrixCellState;
  binding: PermissionBindingDto | null;
  writable: boolean;
  pendingKey: string;
  tooltip: string;
  ariaLabel: string;
  action: "enable" | "disable" | "resolve" | "open" | null;
}

export function isPermissionsHarnessAddressable(column: PermissionInventoryColumnDto): boolean {
  return column.permissionsWritable !== false && (column.installed || column.configPresent);
}

function inUseBindingCount(
  entry: PermissionInventoryEntryDto,
  addressable?: ReadonlySet<string>,
): number {
  return entry.sightings.filter(
    (b) => b.state === "managed" && (!addressable || addressable.has(b.harness)),
  ).length;
}

function hasDrift(entry: PermissionInventoryEntryDto, addressable?: ReadonlySet<string>): boolean {
  return entry.sightings.some(
    (b) => b.state === "drifted" && (!addressable || addressable.has(b.harness)),
  );
}

function addressableHarnesses(inventory: PermissionInventoryDto): ReadonlySet<string> {
  return new Set(inventory.columns.filter(isPermissionsHarnessAddressable).map((column) => column.harness));
}

function matchesSearch(entry: PermissionInventoryEntryDto, query: string): boolean {
  if (!query) return true;
  const needle = query.toLowerCase();
  if (entry.id.toLowerCase().includes(needle)) return true;
  if (entry.displayName.toLowerCase().includes(needle)) return true;
  if (entry.spec?.pattern && entry.spec.pattern.toLowerCase().includes(needle)) return true;
  if (entry.spec?.decision && entry.spec.decision.toLowerCase().includes(needle)) return true;
  if (entry.spec?.scope && entry.spec.scope.toLowerCase().includes(needle)) return true;
  return false;
}

export type PermissionsDecisionFilter = "all" | "allow" | "ask" | "deny";
export type PermissionsStatusFilter = "all" | "applied" | "not-applied" | "differs" | "untracked";

export interface PermissionsFilters {
  search: string;
  decision: PermissionsDecisionFilter;
  status: PermissionsStatusFilter;
}

function matchesStatus(
  entry: PermissionInventoryEntryDto,
  status: PermissionsStatusFilter,
  addressable: ReadonlySet<string>,
): boolean {
  if (status === "untracked") return entry.kind === "unmanaged";
  if (status === "all") return true;
  // Remaining statuses describe managed (tracked) rules only.
  if (entry.kind !== "managed") return false;
  const enabledCount = inUseBindingCount(entry, addressable);
  const drift = hasDrift(entry, addressable);
  switch (status) {
    case "applied":
      return enabledCount > 0;
    case "not-applied":
      return enabledCount === 0 && !drift;
    case "differs":
      return drift;
    default:
      return true;
  }
}

/** Unified inventory filter: managed and unmanaged rules in one list. */
export function filterPermissions(
  inventory: PermissionInventoryDto | null,
  filters: PermissionsFilters,
): PermissionInventoryEntryDto[] {
  if (!inventory) return [];
  const addressable = addressableHarnesses(inventory);
  const needle = filters.search.trim();
  return inventory.entries.filter((entry) => {
    if (!matchesSearch(entry, needle)) return false;
    if (filters.decision !== "all" && entry.spec?.decision !== filters.decision) return false;
    if (!matchesStatus(entry, filters.status, addressable)) return false;
    return true;
  });
}

export interface PermissionsInventorySummary {
  total: number;
  tracked: number;
  untracked: number;
  differs: number;
}

/** Counts for the page header / sidebar badge. "Attention" = untracked + drifted. */
export function permissionsSummary(inventory: PermissionInventoryDto | null): PermissionsInventorySummary {
  if (!inventory) return { total: 0, tracked: 0, untracked: 0, differs: 0 };
  const addressable = addressableHarnesses(inventory);
  const tracked = inventory.entries.filter((e) => e.kind === "managed");
  return {
    total: inventory.entries.length,
    tracked: tracked.length,
    untracked: inventory.entries.filter((e) => e.kind === "unmanaged").length,
    differs: tracked.filter((e) => hasDrift(e, addressable)).length,
  };
}

export function matrixColumns(inventory: { columns: PermissionInventoryColumnDto[] } | null): PermissionInventoryColumnDto[] {
  return inventory?.columns ?? [];
}

export function matrixCellFor(
  entry: PermissionInventoryEntryDto,
  column: PermissionInventoryColumnDto,
  _copy: PermissionsCopy = permissionsCopy,
): PermissionsMatrixCellModel {
  const binding = entry.sightings.find((candidate) => candidate.harness === column.harness) ?? null;
  const writable = isPermissionsHarnessAddressable(column);
  const pendingKey = `${entry.id}:${column.harness}`;
  const baseLabel = `${entry.displayName} on ${column.label}`;

  let cell: PermissionsMatrixCellModel;

  if (binding?.state === "managed") {
    cell = {
      state: "enabled",
      binding,
      writable,
      pendingKey,
      tooltip: `Applied on ${column.label}`,
      ariaLabel: `Remove ${baseLabel}`,
      action: "disable",
    };
  } else if (binding?.state === "drifted") {
    const detail = binding.driftDetail ? ` (${binding.driftDetail})` : "";
    cell = {
      state: "different",
      binding,
      writable,
      pendingKey,
      tooltip: `Config differs on ${column.label}${detail}`,
      ariaLabel: `Resolve config for ${baseLabel}`,
      action: "resolve",
    };
  } else if (binding?.state === "unmanaged") {
    cell = {
      state: "observed",
      binding,
      writable,
      pendingKey,
      tooltip: `Untracked on ${column.label}`,
      ariaLabel: `Open details for ${baseLabel}`,
      action: "open",
    };
  } else if (!writable || !entry.canEnable) {
    cell = {
      state: "unavailable",
      binding,
      writable,
      pendingKey,
      tooltip: column.permissionsUnavailableReason ?? "Unavailable",
      ariaLabel: `Unavailable for ${baseLabel}`,
      action: null,
    };
  } else {
    cell = {
      state: "disabled",
      binding,
      writable,
      pendingKey,
      tooltip: `Not applied on ${column.label}`,
      ariaLabel: `Apply ${baseLabel}`,
      action: "enable",
    };
  }

  if (binding?.caveat) {
    cell.tooltip = `${cell.tooltip} (Caveat: ${binding.caveat})`;
  }

  return cell;
}

export function matrixCoverage(
  entry: PermissionInventoryEntryDto,
  columns: readonly PermissionInventoryColumnDto[],
): { enabled: number; writable: number } {
  const addressable = new Set(columns.filter(isPermissionsHarnessAddressable).map((column) => column.harness));
  return {
    enabled: entry.sightings.filter(
      (binding) => addressable.has(binding.harness) && binding.state === "managed",
    ).length,
    writable: addressable.size,
  };
}

export type PermissionsSortDirection = "asc" | "desc";
export type PermissionsSortKey = "name" | "coverage" | { harness: string };

export interface PermissionsSortState {
  key: PermissionsSortKey;
  direction: PermissionsSortDirection;
}

export function isPermissionsHarnessSortKey(key: PermissionsSortKey): key is { harness: string } {
  return typeof key === "object" && key !== null && "harness" in key;
}

export function permissionsSortKeysEqual(a: PermissionsSortKey, b: PermissionsSortKey): boolean {
  if (typeof a === "string" && typeof b === "string") return a === b;
  if (isPermissionsHarnessSortKey(a) && isPermissionsHarnessSortKey(b)) return a.harness === b.harness;
  return false;
}

const PERMISSIONS_HARNESS_STATE_PRIORITY: Record<PermissionsMatrixCellState, number> = {
  enabled: 0,
  disabled: 1,
  different: 2,
  observed: 2,
  unavailable: 3,
};

function comparePermissionsByName(a: PermissionInventoryEntryDto, b: PermissionInventoryEntryDto): number {
  const nameA = a.displayName || a.id;
  const nameB = b.displayName || b.id;
  return nameA.localeCompare(nameB, undefined, { sensitivity: "base" });
}

export function sortPermissionsRows(
  entries: PermissionInventoryEntryDto[],
  columns: PermissionInventoryColumnDto[],
  sort: PermissionsSortState,
  copy: PermissionsCopy = permissionsCopy,
): PermissionInventoryEntryDto[] {
  const directionMultiplier = sort.direction === "asc" ? 1 : -1;
  const next = entries.slice();

  if (sort.key === "name") {
    next.sort((a, b) => comparePermissionsByName(a, b) * directionMultiplier);
    return next;
  }

  if (sort.key === "coverage") {
    next.sort((a, b) => {
      const aCoverage = matrixCoverage(a, columns).enabled;
      const bCoverage = matrixCoverage(b, columns).enabled;
      const diff = aCoverage - bCoverage;
      if (diff !== 0) return diff * directionMultiplier;
      return comparePermissionsByName(a, b);
    });
    return next;
  }

  const harness = sort.key.harness;
  const column = columns.find((c) => c.harness === harness) ?? {
    harness,
    label: harness,
    installed: true,
    configPresent: true,
    permissionsWritable: true,
  };

  next.sort((a, b) => {
    const aCell = matrixCellFor(a, column, copy);
    const bCell = matrixCellFor(b, column, copy);
    const aPriority = PERMISSIONS_HARNESS_STATE_PRIORITY[aCell.state] ?? 4;
    const bPriority = PERMISSIONS_HARNESS_STATE_PRIORITY[bCell.state] ?? 4;
    const diff = aPriority - bPriority;
    if (diff !== 0) return diff * directionMultiplier;
    return comparePermissionsByName(a, b);
  });

  return next;
}
