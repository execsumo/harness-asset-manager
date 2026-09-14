import { matchesAssetTags } from "../../../components/tags/tag-counts";
import type { ConfigsPayload } from "../api/types";

/** Row state, derived once so the table, filters, and summary all agree. */
export type ConfigStatus = "drifted" | "managed" | "orphaned" | "unmanaged";

export interface ConfigRowData {
  harness: string;
  label: string;
  logoKey: string | null;
  status: ConfigStatus;
  managed: boolean;
  hasRecord: boolean;
  keyCount: number;
  driftState: string;
  sourceFile: string;
  capturedAt: string | null;
  preferences: Record<string, unknown>;
  tags: string[];
}

export interface HarnessIdentity {
  harness: string;
  label: string;
  logoKey?: string | null;
}

function statusOf(record: { managed: boolean; hasRecord: boolean; driftState: string }): ConfigStatus {
  if (!record.managed) {
    // A record with no local config file is managed from another machine, or
    // left behind — either way it is not actionable here the way a fresh
    // harness is, so it gets its own state rather than "unmanaged".
    return record.hasRecord ? "orphaned" : "unmanaged";
  }
  return record.driftState === "drifted" ? "drifted" : "managed";
}

export function selectConfigsRows(
  data: ConfigsPayload | undefined,
  identities: readonly HarnessIdentity[] = [],
): ConfigRowData[] {
  if (!data) return [];

  const identityByHarness = new Map(identities.map((item) => [item.harness, item]));

  return Object.entries(data).map(([harness, record]) => {
    const identity = identityByHarness.get(harness);
    return {
      harness,
      label: identity?.label ?? harness,
      logoKey: identity?.logoKey ?? harness,
      status: statusOf(record),
      ...record,
      tags: record.tags || [],
    };
  });
}

export interface ConfigsSummary {
  total: number;
  /** Harnesses with a snapshot, drifted or not — drives the page-level actions. */
  managed: number;
  /** Counts below are per-status so a summary tile and its filter always agree. */
  inSync: number;
  drifted: number;
  unmanaged: number;
}

export function summarizeConfigs(rows: readonly ConfigRowData[]): ConfigsSummary {
  const countOf = (status: ConfigStatus) => rows.filter((row) => row.status === status).length;
  return {
    total: rows.length,
    managed: rows.filter((row) => row.managed).length,
    inSync: countOf("managed"),
    drifted: countOf("drifted"),
    unmanaged: countOf("unmanaged"),
  };
}

export interface ConfigsFilter {
  search: string;
  status: ConfigStatus | "all";
  tags: readonly string[];
}

export function filterConfigsRows(
  rows: readonly ConfigRowData[],
  { search, status, tags }: ConfigsFilter,
): ConfigRowData[] {
  const needle = search.trim().toLowerCase();

  return rows.filter((row) => {
    if (status !== "all" && row.status !== status) return false;
    if (!matchesAssetTags(row, [...tags])) return false;
    if (needle) {
      const haystack = `${row.harness} ${row.label} ${row.sourceFile}`.toLowerCase();
      if (!haystack.includes(needle)) return false;
    }
    return true;
  });
}

/** Managed harnesses first, drifted ahead of clean, then alphabetically. */
const STATUS_ORDER: Record<ConfigStatus, number> = {
  drifted: 0,
  managed: 1,
  orphaned: 2,
  unmanaged: 3,
};

export function sortConfigsRows(rows: readonly ConfigRowData[]): ConfigRowData[] {
  return [...rows].sort((a, b) => {
    const starred = Number(isStarred(b)) - Number(isStarred(a));
    if (starred !== 0) return starred;
    const byStatus = STATUS_ORDER[a.status] - STATUS_ORDER[b.status];
    if (byStatus !== 0) return byStatus;
    return a.label.localeCompare(b.label);
  });
}

export function isStarred(row: ConfigRowData): boolean {
  return row.tags.some((tag) => tag.toLowerCase() === "starred");
}
