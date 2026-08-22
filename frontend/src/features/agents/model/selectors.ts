import type { AgentInventoryDto, AgentInventoryEntryDto } from "../api/types";

export type InUsePillValue = "all" | "enabled" | "all-harnesses" | "off";
export type AgentsStatusFilter = InUsePillValue | "untracked";

export interface AgentsFilters {
  search: string;
  status: AgentsStatusFilter;
  /** Restrict to entries bound on this harness (id). */
  harness?: string | null;
}

export type AgentMatrixCellState = "enabled" | "disabled" | "unavailable" | "observed" | "empty";

export interface AgentMatrixCellModel {
  state: AgentMatrixCellState;
  binding: AgentInventoryEntryDto["bindings"][number] | null;
  pendingKey: string;
  tooltip: string;
  ariaLabel: string;
  action: "enable" | "disable" | "open" | null;
}

export function countEnabledBindings(entry: AgentInventoryEntryDto): number {
  return entry.bindings.filter((b) => b.state === "enabled").length;
}

export function filterAgentsInUse(
  inventory: AgentInventoryDto | null,
  filters: { search: string; pill: InUsePillValue }
): AgentInventoryEntryDto[] {
  return filterAgents(inventory, { search: filters.search, status: filters.pill });
}

export function pillCounts(inventory: AgentInventoryDto | null): Record<InUsePillValue, number> {
  return {
    all: filterAgents(inventory, { search: "", status: "all" }).filter((e) => e.kind === "managed").length,
    enabled: filterAgents(inventory, { search: "", status: "enabled" }).length,
    "all-harnesses": filterAgents(inventory, { search: "", status: "all-harnesses" }).length,
    off: filterAgents(inventory, { search: "", status: "off" }).length,
  };
}

export function filterAgentsNeedsReview(
  inventory: AgentInventoryDto | null,
  search: string
): AgentInventoryEntryDto[] {
  return filterAgents(inventory, { search, status: "untracked" });
}

function matchesHarnessBinding(
  entry: AgentInventoryEntryDto,
  harness: string | null | undefined,
): boolean {
  if (!harness) return true;
  return entry.bindings.some((binding) => binding.harness === harness && binding.state !== "unsupported");
}

function matchesSearch(entry: AgentInventoryEntryDto, search: string): boolean {
  const query = search.trim().toLowerCase();
  return (
    query === "" ||
    entry.name.toLowerCase().includes(query) ||
    entry.description.toLowerCase().includes(query)
  );
}

/** Unified inventory filter for managed and unmanaged agents. */
export function filterAgents(
  inventory: AgentInventoryDto | null,
  filters: AgentsFilters,
): AgentInventoryEntryDto[] {
  if (!inventory) return [];

  return inventory.entries.filter((entry) => {
    if (!matchesSearch(entry, filters.search)) return false;
    if (!matchesHarnessBinding(entry, filters.harness)) return false;
    if (filters.status === "untracked") return entry.kind === "unmanaged";
    if (entry.kind !== "managed") return filters.status === "all";

    const enabled = countEnabledBindings(entry);
    switch (filters.status) {
      case "all":
        return true;
      case "enabled":
        return enabled > 0;
      case "all-harnesses":
        return inventory.columns.length > 0 && enabled === inventory.columns.length;
      case "off":
        return enabled === 0;
      default:
        return true;
    }
  });
}

export function agentsStatusCounts(
  inventory: AgentInventoryDto | null,
): Record<AgentsStatusFilter, number> {
  if (!inventory) {
    return { all: 0, enabled: 0, "all-harnesses": 0, off: 0, untracked: 0 };
  }
  return {
    all: inventory.entries.length,
    enabled: filterAgents(inventory, { search: "", status: "enabled" }).length,
    "all-harnesses": filterAgents(inventory, { search: "", status: "all-harnesses" }).length,
    off: filterAgents(inventory, { search: "", status: "off" }).length,
    untracked: filterAgents(inventory, { search: "", status: "untracked" }).length,
  };
}

export function matrixCellFor(
  entry: AgentInventoryEntryDto,
  column: AgentInventoryDto["columns"][number],
): AgentMatrixCellModel {
  const binding = entry.bindings.find((candidate) => candidate.harness === column.harness) ?? null;
  const pendingKey = `${entry.ref}:${column.harness}`;

  if (entry.kind === "unmanaged") {
    if (binding?.state === "enabled") {
      return {
        state: "observed",
        binding,
        pendingKey,
        tooltip: `Found in ${column.label} config`,
        ariaLabel: `Open details for ${entry.name}`,
        action: "open",
      };
    }
    return {
      state: "empty",
      binding,
      pendingKey,
      tooltip: `Not found in ${column.label}`,
      ariaLabel: `Not found in ${column.label}`,
      action: null,
    };
  }

  if (!column.installed) {
    return {
      state: "unavailable",
      binding,
      pendingKey,
      tooltip: `${column.label} is not detected`,
      ariaLabel: `${column.label} is not detected`,
      action: null,
    };
  }
  if (binding?.state === "unsupported") {
    return {
      state: "unavailable",
      binding,
      pendingKey,
      tooltip: `Not supported by ${column.label}`,
      ariaLabel: `Not supported by ${column.label}`,
      action: null,
    };
  }
  if (binding?.state === "enabled") {
    return {
      state: "enabled",
      binding,
      pendingKey,
      tooltip: `Disable for ${column.label}`,
      ariaLabel: `Disable for ${column.label}`,
      action: "disable",
    };
  }
  return {
    state: "disabled",
    binding,
    pendingKey,
    tooltip: `Enable for ${column.label}`,
    ariaLabel: `Enable for ${column.label}`,
    action: "enable",
  };
}

export type AgentSortDirection = "asc" | "desc";
export type AgentSortKey = "name" | "coverage" | { harness: string };

export interface AgentSortState {
  key: AgentSortKey;
  direction: AgentSortDirection;
}

export function isAgentHarnessSortKey(key: AgentSortKey): key is { harness: string } {
  return typeof key === "object" && key !== null && "harness" in key;
}

export function agentSortKeysEqual(a: AgentSortKey, b: AgentSortKey): boolean {
  if (typeof a === "string" && typeof b === "string") return a === b;
  if (isAgentHarnessSortKey(a) && isAgentHarnessSortKey(b)) return a.harness === b.harness;
  return false;
}

const AGENT_HARNESS_STATE_PRIORITY: Record<AgentMatrixCellState, number> = {
  enabled: 0,
  disabled: 1,
  observed: 2,
  unavailable: 3,
  empty: 4,
};

function compareAgentsByName(a: AgentInventoryEntryDto, b: AgentInventoryEntryDto): number {
  return a.name.localeCompare(b.name, undefined, { sensitivity: "base" });
}

export function sortAgentsRows(
  entries: AgentInventoryEntryDto[],
  columns: AgentInventoryDto["columns"],
  sort: AgentSortState,
): AgentInventoryEntryDto[] {
  const directionMultiplier = sort.direction === "asc" ? 1 : -1;
  const next = entries.slice();

  if (sort.key === "name") {
    next.sort((a, b) => compareAgentsByName(a, b) * directionMultiplier);
    return next;
  }

  if (sort.key === "coverage") {
    next.sort((a, b) => {
      const diff = countEnabledBindings(a) - countEnabledBindings(b);
      if (diff !== 0) return diff * directionMultiplier;
      return compareAgentsByName(a, b);
    });
    return next;
  }

  const harness = sort.key.harness;
  const column = columns.find((c) => c.harness === harness) ?? {
    harness,
    label: harness,
    logoKey: harness,
    installed: true,
    supported: true,
  };

  next.sort((a, b) => {
    const aCell = matrixCellFor(a, column);
    const bCell = matrixCellFor(b, column);
    const aPriority = AGENT_HARNESS_STATE_PRIORITY[aCell.state] ?? AGENT_HARNESS_STATE_PRIORITY.empty;
    const bPriority = AGENT_HARNESS_STATE_PRIORITY[bCell.state] ?? AGENT_HARNESS_STATE_PRIORITY.empty;
    const diff = aPriority - bPriority;
    if (diff !== 0) return diff * directionMultiplier;
    return compareAgentsByName(a, b);
  });

  return next;
}

