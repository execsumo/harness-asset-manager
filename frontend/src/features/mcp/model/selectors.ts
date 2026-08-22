import type {
  McpBindingDto,
  McpEnvEntryDto,
  McpIdentitySightingDto,
  McpInventoryColumnDto,
  McpInventoryDto,
  McpInventoryEntryDto,
  McpServerSpecDto,
} from "../api/management-types";
import { mcpCopy, type McpCopy } from "../i18n";

export type InUsePillValue = "all" | "enabled" | "all-harnesses" | "unbound" | "drifted" | "untracked";

export interface McpInUseFilters {
  search: string;
  pill: InUsePillValue;
}

export type McpMatrixCellState = "enabled" | "disabled" | "different" | "unavailable" | "observed";

export interface McpMatrixCellModel {
  state: McpMatrixCellState;
  binding: McpBindingDto | null;
  writable: boolean;
  pendingKey: string;
  tooltip: string;
  ariaLabel: string;
  action: "enable" | "disable" | "resolve" | "open" | null;
}

/**
 * True when an MCP harness can receive Harness Asset Manager MCP writes on this system.
 * Discovery remains broader on the backend so stale/bad configs can still be
 * disabled, but frontend enable affordances must follow the verified write
 * capability exposed by the backend.
 *
 * Used by consumers (card footers, logo stacks, binding matrix) inline
 * where they need to count or filter per-harness state. Kept as a leaf
 * predicate rather than a data-shape filter so the inventory layer
 * stays a single source of truth, with no parallel filtered view to
 * reconcile.
 */
export function isMcpHarnessAddressable(column: McpInventoryColumnDto): boolean {
  return column.mcpWritable !== false && (column.installed || column.configPresent);
}

function inUseBindingCount(
  entry: McpInventoryEntryDto,
  addressable?: ReadonlySet<string>,
): number {
  return entry.sightings.filter(
    (b) => b.state === "managed" && (!addressable || addressable.has(b.harness)),
  ).length;
}

function hasDrift(entry: McpInventoryEntryDto, addressable?: ReadonlySet<string>): boolean {
  return entry.sightings.some(
    (b) => b.state === "drifted" && (!addressable || addressable.has(b.harness)),
  );
}

function addressableHarnesses(inventory: McpInventoryDto): ReadonlySet<string> {
  return new Set(inventory.columns.filter(isMcpHarnessAddressable).map((column) => column.harness));
}

function matchesSearch(entry: McpInventoryEntryDto, query: string): boolean {
  if (!query) return true;
  const needle = query.toLowerCase();
  if (entry.name.toLowerCase().includes(needle)) return true;
  if (entry.displayName.toLowerCase().includes(needle)) return true;
  if (entry.spec?.transport && entry.spec.transport.toLowerCase().includes(needle)) return true;
  return false;
}

export function filterMcpServersInUse(
  inventory: McpInventoryDto | null,
  filters: McpInUseFilters,
): McpInventoryEntryDto[] {
  if (!inventory) return [];
  const addressable = addressableHarnesses(inventory);
  const harnessCount = addressable.size;
  return inventory.entries.filter((entry) => {
    if (!matchesSearch(entry, filters.search.trim())) return false;
    if (filters.pill === "untracked") return entry.kind === "unmanaged";
    if (entry.kind !== "managed") return filters.pill === "all";

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

export function pillCounts(inventory: McpInventoryDto | null): Record<InUsePillValue, number> {
  if (!inventory) {
    return { all: 0, enabled: 0, "all-harnesses": 0, unbound: 0, drifted: 0, untracked: 0 };
  }
  const addressable = addressableHarnesses(inventory);
  const harnessCount = addressable.size;
  const inUseEntries = inventory.entries.filter((e) => e.kind === "managed");
  const untrackedEntries = inventory.entries.filter((e) => e.kind === "unmanaged");
  return {
    all: inventory.entries.length,
    enabled: inUseEntries.filter((e) => inUseBindingCount(e, addressable) > 0).length,
    "all-harnesses": inUseEntries.filter(
      (e) => harnessCount > 0 && inUseBindingCount(e, addressable) === harnessCount,
    ).length,
    unbound: inUseEntries.filter(
      (e) => inUseBindingCount(e, addressable) === 0 && !hasDrift(e, addressable),
    ).length,
    drifted: inUseEntries.filter((entry) => hasDrift(entry, addressable)).length,
    untracked: untrackedEntries.length,
  };
}

export function matrixColumns(inventory: { columns: McpInventoryColumnDto[] } | null): McpInventoryColumnDto[] {
  return inventory?.columns ?? [];
}

export function matrixCellFor(
  entry: McpInventoryEntryDto,
  column: McpInventoryColumnDto,
  copy: McpCopy = mcpCopy,
): McpMatrixCellModel {
  const binding = entry.sightings.find((candidate) => candidate.harness === column.harness) ?? null;
  const writable = isMcpHarnessAddressable(column);
  const pendingKey = `${entry.name}:${column.harness}`;
  const baseLabel = copy.detail.matrix.baseLabel(entry.displayName, column.label);

  if (binding?.state === "managed") {
    return {
      state: "enabled",
      binding,
      writable,
      pendingKey,
      tooltip: copy.detail.matrix.enabledTooltip(column.label),
      ariaLabel: copy.detail.matrix.disable(baseLabel),
      action: "disable",
    };
  }

  if (binding?.state === "drifted") {
    const detail = binding.driftDetail ? ` (${binding.driftDetail})` : "";
    return {
      state: "different",
      binding,
      writable,
      pendingKey,
      tooltip: copy.detail.matrix.differentTooltip(column.label, detail),
      ariaLabel: copy.detail.matrix.resolveConfigFor(baseLabel),
      action: "resolve",
    };
  }

  if (binding?.state === "unmanaged") {
    return {
      state: "observed",
      binding,
      writable,
      pendingKey,
      tooltip: copy.detail.matrix.foundTooltip(column.label),
      ariaLabel: copy.detail.matrix.openDetailFor(baseLabel),
      action: "open",
    };
  }

  if (!writable || !entry.canEnable) {
    return {
      state: "unavailable",
      binding,
      writable,
      pendingKey,
      tooltip: column.mcpUnavailableReason ?? "Unavailable",
      ariaLabel: copy.detail.matrix.unavailable(baseLabel),
      action: null,
    };
  }

  return {
    state: "disabled",
    binding,
    writable,
    pendingKey,
    tooltip: copy.detail.matrix.disabledTooltip(column.label),
    ariaLabel: copy.detail.matrix.enable(baseLabel),
    action: "enable",
  };
}

export function matrixCoverage(
  entry: McpInventoryEntryDto,
  columns: readonly McpInventoryColumnDto[],
): { enabled: number; writable: number } {
  const addressable = new Set(columns.filter(isMcpHarnessAddressable).map((column) => column.harness));
  return {
    enabled: entry.sightings.filter(
      (binding) => addressable.has(binding.harness) && binding.state === "managed",
    ).length,
    writable: addressable.size,
  };
}

// Choose-version dialog helpers -------------------------------------------

const URL_CREDENTIAL_RE = /[?&](api[_-]?key|token|secret|auth|authorization)=/i;

export interface SightingSummary {
  primary: string;
  envCount: number;
  envKeys: readonly string[];
  credentialInUrl: boolean;
}

export function urlHasEmbeddedCredential(url: string | undefined | null): boolean {
  return typeof url === "string" && URL_CREDENTIAL_RE.test(url);
}

function parseHost(url: string): string {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}

export function summarizeMcpConfig(
  spec: McpServerSpecDto,
  env: readonly McpEnvEntryDto[] = [],
): SightingSummary {
  const envKeys = env ? env.map((e) => e.key) : [];
  if (spec.transport === "stdio") {
    const raw = spec.command ?? "";
    const base = raw.split("/").pop() || raw;
    return {
      primary: `Local · ${base || "stdio"}`,
      envCount: envKeys.length,
      envKeys,
      credentialInUrl: false,
    };
  }
  const host = spec.url ? parseHost(spec.url) : "remote";
  const label = spec.transport === "sse" ? "SSE" : "HTTP";
  return {
    primary: `Remote ${label} · ${host}`,
    envCount: envKeys.length,
    envKeys,
    credentialInUrl: urlHasEmbeddedCredential(spec.url),
  };
}

export function summarizeSighting(sighting: McpIdentitySightingDto): SightingSummary {
  return summarizeMcpConfig(sighting.spec, sighting.env ?? []);
}

export function formatEnvKeyPreview(keys: readonly string[]): string {
  if (keys.length === 0) return "";
  if (keys.length <= 2) return keys.join(", ");
  return `${keys[0]}, ${keys[1]}, +${keys.length - 2} more`;
}

export function envChipLabel(count: number): string {
  return count === 1 ? "1 env var" : `${count} env vars`;
}

export type McpSortDirection = "asc" | "desc";
export type McpSortKey = "name" | "coverage" | { harness: string };

export interface McpSortState {
  key: McpSortKey;
  direction: McpSortDirection;
}

export function isMcpHarnessSortKey(key: McpSortKey): key is { harness: string } {
  return typeof key === "object" && key !== null && "harness" in key;
}

export function mcpSortKeysEqual(a: McpSortKey, b: McpSortKey): boolean {
  if (typeof a === "string" && typeof b === "string") return a === b;
  if (isMcpHarnessSortKey(a) && isMcpHarnessSortKey(b)) return a.harness === b.harness;
  return false;
}

const MCP_HARNESS_STATE_PRIORITY: Record<McpMatrixCellState, number> = {
  enabled: 0,
  disabled: 1,
  different: 2,
  observed: 2,
  unavailable: 3,
};

function compareMcpByName(a: McpInventoryEntryDto, b: McpInventoryEntryDto): number {
  const nameA = a.displayName || a.name;
  const nameB = b.displayName || b.name;
  return nameA.localeCompare(nameB, undefined, { sensitivity: "base" });
}

export function sortMcpRows(
  entries: McpInventoryEntryDto[],
  columns: McpInventoryColumnDto[],
  sort: McpSortState,
  copy: McpCopy = mcpCopy,
): McpInventoryEntryDto[] {
  const directionMultiplier = sort.direction === "asc" ? 1 : -1;
  const next = entries.slice();

  if (sort.key === "name") {
    next.sort((a, b) => compareMcpByName(a, b) * directionMultiplier);
    return next;
  }

  if (sort.key === "coverage") {
    next.sort((a, b) => {
      const aCoverage = matrixCoverage(a, columns).enabled;
      const bCoverage = matrixCoverage(b, columns).enabled;
      const diff = aCoverage - bCoverage;
      if (diff !== 0) return diff * directionMultiplier;
      return compareMcpByName(a, b);
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
    mcpWritable: true,
  };

  next.sort((a, b) => {
    const aCell = matrixCellFor(a, column, copy);
    const bCell = matrixCellFor(b, column, copy);
    const aPriority = MCP_HARNESS_STATE_PRIORITY[aCell.state] ?? 4;
    const bPriority = MCP_HARNESS_STATE_PRIORITY[bCell.state] ?? 4;
    const diff = aPriority - bPriority;
    if (diff !== 0) return diff * directionMultiplier;
    return compareMcpByName(a, b);
  });

  return next;
}

