import type {
  HookBindingDto,
  HookInventoryColumnDto,
  HookInventoryDto,
  HookInventoryEntryDto,
} from "../api/management-types";
import { hooksCopy, type HooksCopy } from "../i18n";
import {
  extractAssetTagCounts,
  matchesAssetTags,
  type AssetTagCount,
} from "../../../components/tags/tag-counts";

export type HooksStatusFilter = "all" | "enabled" | "all-harnesses" | "unbound" | "drifted" | "untracked";
export type InUsePillValue = Exclude<HooksStatusFilter, "untracked">;

export type HookTagCount = AssetTagCount;

export interface HooksInUseFilters {
  search: string;
  pill: InUsePillValue;
  tags?: string[] | null;
}

export interface HooksFilters {
  search: string;
  status: HooksStatusFilter;
  /** Restrict to entries sighted on this harness (id). */
  harness?: string | null;
  tags?: string[] | null;
}

export function extractHookTagCounts(
  inventory: HookInventoryDto | null | undefined,
): HookTagCount[] {
  const managed = inventory?.entries.filter((entry) => entry.kind === "managed");
  return extractAssetTagCounts(managed);
}

export type HooksMatrixCellState = "enabled" | "disabled" | "different" | "unavailable" | "observed";

export interface HooksMatrixCellModel {
  state: HooksMatrixCellState;
  binding: HookBindingDto | null;
  writable: boolean;
  pendingKey: string;
  tooltip: string;
  ariaLabel: string;
  action: "enable" | "disable" | "resolve" | "open" | null;
}

export function isHooksHarnessAddressable(column: HookInventoryColumnDto): boolean {
  return column.hooksWritable !== false && (column.installed || column.configPresent);
}

function inUseBindingCount(
  entry: HookInventoryEntryDto,
  addressable?: ReadonlySet<string>,
): number {
  return entry.sightings.filter(
    (b) => b.state === "managed" && (!addressable || addressable.has(b.harness)),
  ).length;
}

function hasDrift(entry: HookInventoryEntryDto, addressable?: ReadonlySet<string>): boolean {
  return entry.sightings.some(
    (b) => b.state === "drifted" && (!addressable || addressable.has(b.harness)),
  );
}

function addressableHarnesses(inventory: HookInventoryDto): ReadonlySet<string> {
  return new Set(inventory.columns.filter(isHooksHarnessAddressable).map((column) => column.harness));
}

function matchesHarnessSighting(
  sightings: Array<{ harness: string }>,
  harness: string | null | undefined,
): boolean {
  if (!harness) return true;
  return sightings.some((sighting) => sighting.harness === harness);
}

function matchesSearch(entry: HookInventoryEntryDto, query: string): boolean {
  if (!query) return true;
  const needle = query.toLowerCase();
  if (entry.id.toLowerCase().includes(needle)) return true;
  if (entry.displayName.toLowerCase().includes(needle)) return true;
  if (entry.spec?.command && entry.spec.command.toLowerCase().includes(needle)) return true;
  if (entry.spec?.event && entry.spec.event.toLowerCase().includes(needle)) return true;
  return false;
}

export function filterHooksInUse(
  inventory: HookInventoryDto | null,
  filters: HooksInUseFilters,
): HookInventoryEntryDto[] {
  if (!inventory) return [];
  const addressable = addressableHarnesses(inventory);
  const harnessCount = addressable.size;
  return inventory.entries.filter((entry) => {
    if (entry.kind !== "managed") return false;
    if (filters.tags && filters.tags.length > 0 && !matchesAssetTags(entry, filters.tags)) return false;
    if (!matchesSearch(entry, filters.search.trim())) return false;
    const enabledCount = inUseBindingCount(entry, addressable);
    switch (filters.pill) {
      case "all":
        return true;
      case "enabled":
        return enabledCount > 0;
      case "all-harnesses":
        return harnessCount > 0 && enabledCount === harnessCount;
      case "unbound":
        return enabledCount === 0 && !hasDrift(entry, addressable);
      case "drifted":
        return hasDrift(entry, addressable);
      default:
        return true;
    }
  });
}

/** Unified inventory filter for managed and unmanaged hooks. */
export function filterHooks(
  inventory: HookInventoryDto | null,
  filters: HooksFilters,
): HookInventoryEntryDto[] {
  if (!inventory) return [];
  const addressable = addressableHarnesses(inventory);
  const harnessCount = addressable.size;
  const needle = filters.search.trim();

  return inventory.entries.filter((entry) => {
    if (filters.tags && filters.tags.length > 0) {
      if (entry.kind !== "managed" || !matchesAssetTags(entry, filters.tags)) {
        return false;
      }
    }
    if (!matchesSearch(entry, needle)) return false;
    if (!matchesHarnessSighting(entry.sightings, filters.harness)) return false;
    if (filters.status === "untracked") return entry.kind === "unmanaged";
    if (entry.kind !== "managed") return filters.status === "all";

    const enabledCount = inUseBindingCount(entry, addressable);
    switch (filters.status) {
      case "all":
        return true;
      case "enabled":
        return enabledCount > 0;
      case "all-harnesses":
        return harnessCount > 0 && enabledCount === harnessCount;
      case "unbound":
        return enabledCount === 0 && !hasDrift(entry, addressable);
      case "drifted":
        return hasDrift(entry, addressable);
      default:
        return true;
    }
  });
}

export function filterHooksNeedsReview(
  inventory: HookInventoryDto | null,
  search = "",
): HookInventoryEntryDto[] {
  if (!inventory) return [];
  const needle = search.trim();
  return inventory.entries.filter(
    (entry) => entry.kind === "unmanaged" && matchesSearch(entry, needle),
  );
}

export function pillCounts(inventory: HookInventoryDto | null): Record<InUsePillValue, number> {
  if (!inventory) {
    return { all: 0, enabled: 0, "all-harnesses": 0, unbound: 0, drifted: 0 };
  }
  const addressable = addressableHarnesses(inventory);
  const harnessCount = addressable.size;
  const inUseEntries = inventory.entries.filter((e) => e.kind === "managed");
  return {
    all: inUseEntries.length,
    enabled: inUseEntries.filter((e) => inUseBindingCount(e, addressable) > 0).length,
    "all-harnesses": inUseEntries.filter(
      (e) => harnessCount > 0 && inUseBindingCount(e, addressable) === harnessCount,
    ).length,
    unbound: inUseEntries.filter(
      (e) => inUseBindingCount(e, addressable) === 0 && !hasDrift(e, addressable),
    ).length,
    drifted: inUseEntries.filter((entry) => hasDrift(entry, addressable)).length,
  };
}

export function hooksStatusCounts(inventory: HookInventoryDto | null): Record<HooksStatusFilter, number> {
  if (!inventory) {
    return { all: 0, enabled: 0, "all-harnesses": 0, unbound: 0, drifted: 0, untracked: 0 };
  }
  return {
    all: inventory.entries.length,
    enabled: filterHooks(inventory, { search: "", status: "enabled" }).length,
    "all-harnesses": filterHooks(inventory, { search: "", status: "all-harnesses" }).length,
    unbound: filterHooks(inventory, { search: "", status: "unbound" }).length,
    drifted: filterHooks(inventory, { search: "", status: "drifted" }).length,
    untracked: inventory.entries.filter((entry) => entry.kind === "unmanaged").length,
  };
}

export function matrixColumns(inventory: { columns: HookInventoryColumnDto[] } | null): HookInventoryColumnDto[] {
  return inventory?.columns ?? [];
}

export function matrixCellFor(
  entry: HookInventoryEntryDto,
  column: HookInventoryColumnDto,
  _copy: HooksCopy = hooksCopy,
): HooksMatrixCellModel {
  const binding = entry.sightings.find((candidate) => candidate.harness === column.harness) ?? null;
  const writable = isHooksHarnessAddressable(column);
  const pendingKey = `${entry.id}:${column.harness}`;
  const baseLabel = `${entry.displayName} on ${column.label}`;

  let cell: HooksMatrixCellModel;

  if (binding?.state === "managed") {
    cell = {
      state: "enabled",
      binding,
      writable,
      pendingKey,
      tooltip: `Enabled on ${column.label}`,
      ariaLabel: `Disable ${baseLabel}`,
      action: "disable",
    };
  } else if (binding?.state === "drifted") {
    const detail = binding.driftDetail ? ` (${binding.driftDetail})` : "";
    cell = {
      state: "different",
      binding,
      writable,
      pendingKey,
      tooltip: `Different config on ${column.label}${detail}`,
      ariaLabel: `Resolve config for ${baseLabel}`,
      action: "resolve",
    };
  } else if (binding?.state === "unmanaged") {
    cell = {
      state: "observed",
      binding,
      writable,
      pendingKey,
      tooltip: `Configured outside harness-asset-manager on ${column.label}`,
      ariaLabel: `Open details for ${baseLabel}`,
      action: "open",
    };
  } else if (!writable || !entry.canEnable) {
    cell = {
      state: "unavailable",
      binding,
      writable,
      pendingKey,
      tooltip: column.hooksUnavailableReason ?? "Unavailable",
      ariaLabel: `Unavailable for ${baseLabel}`,
      action: null,
    };
  } else {
    cell = {
      state: "disabled",
      binding,
      writable,
      pendingKey,
      tooltip: `Disabled on ${column.label}`,
      ariaLabel: `Enable ${baseLabel}`,
      action: "enable",
    };
  }

  if (binding?.caveat) {
    cell.tooltip = `${cell.tooltip} (Caveat: ${binding.caveat})`;
  }

  return cell;
}

export function matrixCoverage(
  entry: HookInventoryEntryDto,
  columns: readonly HookInventoryColumnDto[],
): { enabled: number; writable: number } {
  const addressable = new Set(columns.filter(isHooksHarnessAddressable).map((column) => column.harness));
  return {
    enabled: entry.sightings.filter(
      (binding) => addressable.has(binding.harness) && binding.state === "managed",
    ).length,
    writable: addressable.size,
  };
}

export type HooksSortDirection = "asc" | "desc";
export type HooksSortKey = "name" | "coverage" | { harness: string };

export interface HooksSortState {
  key: HooksSortKey;
  direction: HooksSortDirection;
}

export function isHooksHarnessSortKey(key: HooksSortKey): key is { harness: string } {
  return typeof key === "object" && key !== null && "harness" in key;
}

export function hooksSortKeysEqual(a: HooksSortKey, b: HooksSortKey): boolean {
  if (typeof a === "string" && typeof b === "string") return a === b;
  if (isHooksHarnessSortKey(a) && isHooksHarnessSortKey(b)) return a.harness === b.harness;
  return false;
}

const HOOKS_HARNESS_STATE_PRIORITY: Record<HooksMatrixCellState, number> = {
  enabled: 0,
  disabled: 1,
  different: 2,
  observed: 2,
  unavailable: 3,
};

function compareHooksByName(a: HookInventoryEntryDto, b: HookInventoryEntryDto): number {
  const nameA = a.displayName || a.id;
  const nameB = b.displayName || b.id;
  return nameA.localeCompare(nameB, undefined, { sensitivity: "base" });
}

export function sortHooksRows(
  entries: HookInventoryEntryDto[],
  columns: HookInventoryColumnDto[],
  sort: HooksSortState,
  copy: HooksCopy = hooksCopy,
): HookInventoryEntryDto[] {
  const directionMultiplier = sort.direction === "asc" ? 1 : -1;
  const next = entries.slice();

  if (sort.key === "name") {
    next.sort((a, b) => compareHooksByName(a, b) * directionMultiplier);
    return next;
  }

  if (sort.key === "coverage") {
    next.sort((a, b) => {
      const aCoverage = matrixCoverage(a, columns).enabled;
      const bCoverage = matrixCoverage(b, columns).enabled;
      const diff = aCoverage - bCoverage;
      if (diff !== 0) return diff * directionMultiplier;
      return compareHooksByName(a, b);
    });
    return next;
  }

  const harness = sort.key.harness;
  const column = columns.find((c) => c.harness === harness) ?? {
    harness,
    label: harness,
    logoKey: harness,
    installed: true,
    configPresent: true,
    hooksWritable: true,
  };

  next.sort((a, b) => {
    const aCell = matrixCellFor(a, column, copy);
    const bCell = matrixCellFor(b, column, copy);
    const aPriority = HOOKS_HARNESS_STATE_PRIORITY[aCell.state] ?? 4;
    const bPriority = HOOKS_HARNESS_STATE_PRIORITY[bCell.state] ?? 4;
    const diff = aPriority - bPriority;
    if (diff !== 0) return diff * directionMultiplier;
    return compareHooksByName(a, b);
  });

  return next;
}

