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
  /** Restrict to rows that touch this harness (id). */
  harness?: string | null;
  /** Restrict to rows matching any of these tags (OR within tags). */
  tags?: string[] | null;
}

export interface AlignedHarnessCell {
  column: HarnessColumn;
  cell: SkillListRow["cells"][number] | null;
}

export interface SkillTagCount {
  tag: string;
  count: number;
  isStarred: boolean;
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
  const matchingRows = [...managedRows, ...untrackedRows].filter(
    (row) =>
      matchesSearch(row, filters.search, filters.status === "untracked" ? ["found"] : ["enabled", "disabled", "found"]) &&
      matchesHarness(row, filters.harness) &&
      matchesTags(row, filters.tags),
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

function matchesTags(row: SkillListRow, tags: string[] | null | undefined): boolean {
  if (!tags || tags.length === 0) return true;
  const rowTags = (row.tags || []).map((t) => t.toLowerCase());
  return tags.some((tag) => rowTags.includes(tag.toLowerCase()));
}

export function extractSkillTagCounts(data: SkillsWorkspaceData | null): SkillTagCount[] {
  if (!data) return [{ tag: "starred", count: 0, isStarred: true }];
  const countsMap = new Map<string, { display: string; count: number }>();
  let starredCount = 0;

  for (const row of data.rows) {
    const seenInRow = new Set<string>();
    for (const tag of row.tags || []) {
      const lower = tag.toLowerCase();
      if (seenInRow.has(lower)) continue;
      seenInRow.add(lower);

      if (lower === "starred") {
        starredCount += 1;
      } else {
        const existing = countsMap.get(lower);
        if (existing) {
          existing.count += 1;
        } else {
          countsMap.set(lower, { display: tag, count: 1 });
        }
      }
    }
  }

  const regularTags = Array.from(countsMap.values())
    .sort((a, b) => a.display.localeCompare(b.display, undefined, { sensitivity: "base" }))
    .map(({ display, count }) => ({ tag: display, count, isStarred: false }));

  return [
    { tag: "starred", count: starredCount, isStarred: true },
    ...regularTags,
  ];
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

function matchesHarness(row: SkillListRow, harness: string | null | undefined): boolean {
  if (!harness) return true;
  // Managed skills carry a "disabled" cell on every detected harness, so only
  // "enabled" (actively bound) / "found" (unadopted) count as touching it.
  return row.cells.some(
    (cell) => cell.harness === harness && (cell.state === "enabled" || cell.state === "found"),
  );
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
