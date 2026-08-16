import type { AgentInventoryDto, AgentInventoryEntryDto } from "../api/types";

export type InUsePillValue = "all" | "enabled" | "all-harnesses" | "off";
export type AgentsStatusFilter = InUsePillValue | "untracked";

export interface AgentsFilters {
  search: string;
  status: AgentsStatusFilter;
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
