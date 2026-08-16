import { skillStatusConcept } from "../../../lib/product-language";
import type { HarnessCellState, HarnessColumn, SkillListRow, SkillsWorkspaceData } from "./types";

export interface SkillsInUseFilterState {
  search: string;
}

export interface SkillsNeedsReviewFilterState {
  search: string;
}

export type SkillsStatusFilter = "all" | "enabled" | "all-harnesses" | "off" | "untracked";

export interface SkillsFilters {
  search: string;
  status: SkillsStatusFilter;
}

export interface AlignedHarnessCell {
  column: HarnessColumn;
  cell: SkillListRow["cells"][number] | null;
}

export function hasActiveSkillsInUseFilters(filters: SkillsInUseFilterState): boolean {
  return filters.search.trim() !== "";
}

export function hasActiveNeedsReviewFilters(filters: SkillsNeedsReviewFilterState): boolean {
  return filters.search.trim() !== "";
}

export function resetSkillsInUseFilters(): SkillsInUseFilterState {
  return {
    search: "",
  };
}

export function resetSkillsNeedsReviewFilters(): SkillsNeedsReviewFilterState {
  return {
    search: "",
  };
}

export function filterSkillsInUseRows(data: SkillsWorkspaceData | null, filters: SkillsInUseFilterState): SkillListRow[] {
  return selectSkillsInUseRows(data).filter((row) => matchesSearch(row, filters.search, ["enabled", "disabled"]));
}

export function filterNeedsReviewRows(data: SkillsWorkspaceData | null, filters: SkillsNeedsReviewFilterState): SkillListRow[] {
  return selectNeedsReviewRows(data).filter((row) => matchesSearch(row, filters.search, ["found"]));
}

/** Unified inventory filter for managed and unmanaged skills. */
export function filterSkills(data: SkillsWorkspaceData | null, filters: SkillsFilters): SkillListRow[] {
  if (!data) return [];

  const managedRows = data.rows.filter((row) => skillStatusConcept(row.displayStatus) === "inUse");
  const untrackedRows = data.rows.filter((row) => skillStatusConcept(row.displayStatus) === "needsReview");
  const matchingRows = [...managedRows, ...untrackedRows].filter((row) =>
    matchesSearch(row, filters.search, filters.status === "untracked" ? ["found"] : ["enabled", "disabled", "found"]),
  );

  if (filters.status === "untracked") return matchingRows.filter((row) => untrackedRows.includes(row));
  if (filters.status === "all") return matchingRows;

  return matchingRows.filter((row) => {
    if (!managedRows.includes(row)) return false;
    const enabledCount = countEnabledCells(row);
    switch (filters.status) {
      case "enabled":
        return enabledCount > 0;
      case "all-harnesses":
        return data.harnessColumns.length > 0 && enabledCount === data.harnessColumns.length;
      case "off":
        return enabledCount === 0;
      default:
        return true;
    }
  });
}

export function skillsStatusCounts(data: SkillsWorkspaceData | null): Record<SkillsStatusFilter, number> {
  if (!data) {
    return { all: 0, enabled: 0, "all-harnesses": 0, off: 0, untracked: 0 };
  }
  return {
    all: data.rows.length,
    enabled: filterSkills(data, { search: "", status: "enabled" }).length,
    "all-harnesses": filterSkills(data, { search: "", status: "all-harnesses" }).length,
    off: filterSkills(data, { search: "", status: "off" }).length,
    untracked: data.rows.filter((row) => skillStatusConcept(row.displayStatus) === "needsReview").length,
  };
}

export function countNeedsReviewRows(data: SkillsWorkspaceData | null): number {
  return selectNeedsReviewRows(data).length;
}

export function countAdoptableLocalSkillRows(data: SkillsWorkspaceData | null): number {
  return selectNeedsReviewRows(data).filter((row) => row.actions.canManage).length;
}

export function alignHarnessCells(row: SkillListRow, columns: HarnessColumn[]): AlignedHarnessCell[] {
  return columns.map((column) => ({
    column,
    cell: row.cells.find((item) => item.harness === column.harness) ?? null,
  }));
}

function selectSkillsInUseRows(data: SkillsWorkspaceData | null): SkillListRow[] {
  if (!data) {
    return [];
  }
  return data.rows.filter((row) => skillStatusConcept(row.displayStatus) === "inUse");
}

function selectNeedsReviewRows(data: SkillsWorkspaceData | null): SkillListRow[] {
  if (!data) {
    return [];
  }
  return data.rows.filter((row) => skillStatusConcept(row.displayStatus) === "needsReview");
}

function matchesSearch(
  row: SkillListRow,
  search: string,
  searchableCellStates: readonly HarnessCellState[],
): boolean {
  const normalizedSearch = search.trim().toLowerCase();
  if (!normalizedSearch) {
    return true;
  }

  const harnessLabels = row.cells
    .filter((cell) => searchableCellStates.includes(cell.state))
    .map((cell) => cell.label);

  const searchHaystack = [
    row.name,
    row.description,
    ...harnessLabels,
  ].join(" ").toLowerCase();

  return searchHaystack.includes(normalizedSearch);
}

function countEnabledCells(row: SkillListRow): number {
  return row.cells.filter((cell) => cell.state === "enabled").length;
}
