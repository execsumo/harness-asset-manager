import type { QueryClient } from "@tanstack/react-query";
import {
  invalidateAgentsQueries,
  agentsRoutes,
  useAgentsInventoryQuery,
  type AgentInventoryDto,
} from "../../features/agents/public";
import { useMemo } from "react";

import {
  invalidateMcpQueries,
  isMcpHarnessAddressable,
  mcpRoutes,
  useMcpInventoryQuery,
  type McpInventoryDto,
} from "../../features/mcp/public";
import {
  invalidateSkillsQueries,
  skillsRoutes,
  useSkillsListQuery,
  type SkillsWorkspaceData,
} from "../../features/skills/public";
import {
  invalidateSlashCommandQueries,
  slashCommandRoutes,
  useSlashCommandsQuery,
  type SlashCommandListDto,
} from "../../features/slash-commands/public";
import { marketplaceRoutes } from "../../features/marketplace/public";
import { overviewCopy, useOverviewCopy, type OverviewCopy } from "../../features/overview/i18n";
import {
  invalidateHooksQueries,
  hooksRoutes,
  useHooksInventoryQuery,
  type HookInventoryDto,
} from "../../features/hooks/public";
import {
  invalidatePermissionsQueries,
  permissionsRoutes,
  usePermissionsInventoryQuery,
  type PermissionInventoryDto,
} from "../../features/permissions/public";

export interface OverviewShortcut {
  key: string;
  label: string;
  to: string;
  group: "manage" | "discover";
}

export interface OverviewCoverageCell {
  /** Items actively managed / synced / enabled on this harness. */
  active: number;
  /** Items found on this harness that need a decision (unmanaged, drifted, …). */
  review: number;
}

export interface OverviewHarnessAvailabilityIssue {
  capability: "MCP" | "Hooks" | "Permissions";
  reason: string;
}

export interface OverviewReviewItem {
  key: string;
  label: string;
  description: string;
  count: number;
  to: string;
  tone: "neutral" | "warning" | "danger";
}

export type OverviewHarnessCellKey =
  | "skills"
  | "commands"
  | "mcp"
  | "hooks"
  | "permissions"
  | "agents";

export interface OverviewHarnessRow {
  harness: string;
  label: string;
  logoKey: string | null;
  cells: Record<OverviewHarnessCellKey, OverviewCoverageCell>;
  availabilityIssues: OverviewHarnessAvailabilityIssue[];
}

export interface OverviewModel {
  shortcuts: OverviewShortcut[];
  reviewItems: OverviewReviewItem[];
  /** Catalog-level totals per capability, agnostic of any single harness. */
  totalsRow: OverviewHarnessRow;
  harnessRows: OverviewHarnessRow[];
}

export function useOverviewData() {
  const skillsQuery = useSkillsListQuery();
  const slashCommandsQuery = useSlashCommandsQuery();
  const mcpQuery = useMcpInventoryQuery();
  const hooksQuery = useHooksInventoryQuery();
  const permissionsQuery = usePermissionsInventoryQuery();
  const agentsQuery = useAgentsInventoryQuery();
  const model = useOverviewModel(
    skillsQuery.data,
    slashCommandsQuery.data,
    mcpQuery.data,
    hooksQuery.data,
    permissionsQuery.data,
    agentsQuery.data,
  );

  return {
    skillsQuery,
    slashCommandsQuery,
    mcpQuery,
    hooksQuery,
    permissionsQuery,
    agentsQuery,
    model,
  };
}

export async function invalidateOverviewData(queryClient: QueryClient): Promise<void> {
  await Promise.all([
    invalidateSkillsQueries(queryClient),
    invalidateSlashCommandQueries(queryClient),
    invalidateMcpQueries(queryClient),
    invalidateHooksQueries(queryClient),
    invalidatePermissionsQueries(queryClient),
    invalidateAgentsQueries(queryClient),
  ]);
}

interface HarnessAccumulator extends OverviewHarnessRow {
  order: number;
}

export function useOverviewModel(
  skills: SkillsWorkspaceData | null | undefined,
  slashCommands: SlashCommandListDto | null | undefined,
  mcp: McpInventoryDto | null | undefined,
  hooks: HookInventoryDto | null | undefined,
  permissions: PermissionInventoryDto | null | undefined,
  agents: AgentInventoryDto | null | undefined,
): OverviewModel {
  const copy = useOverviewCopy();
  return useMemo(
    () => buildOverviewModel(skills, slashCommands, mcp, hooks, permissions, agents, copy),
    [skills, slashCommands, mcp, hooks, permissions, agents, copy],
  );
}

export function buildOverviewModel(
  skills: SkillsWorkspaceData | null | undefined,
  slashCommands: SlashCommandListDto | null | undefined,
  mcp: McpInventoryDto | null | undefined,
  hooks: HookInventoryDto | null | undefined,
  permissions: PermissionInventoryDto | null | undefined,
  agents: AgentInventoryDto | null | undefined,
  copy: OverviewCopy = overviewCopy,
): OverviewModel {
  const skillsToReview = skills?.summary.unmanaged ?? null;
  const slashCommandsToReview = slashCommands?.reviewCommands?.length ?? null;
  const mcpConfigsToReview = mcp?.entries?.filter((entry) => entry.kind === "unmanaged").length ?? null;
  const differentConfigMcpServers =
    mcp?.entries?.filter(
      (entry) =>
        entry.kind === "managed" &&
        entry.sightings.some((sighting) => sighting.state === "drifted"),
    ).length ?? null;
  const inventoryIssues = mcp?.issues?.length ?? null;
  const unavailableHarnesses = mcp?.columns?.filter((column) => column.mcpWritable === false).length ?? null;
  const reviewItems = buildReviewItems({
    skillsToReview,
    slashCommandsToReview,
    mcpConfigsToReview,
    differentConfigMcpServers,
    inventoryIssues,
    unavailableHarnesses,
    copy,
  });

  return {
    shortcuts: buildShortcuts(copy),
    reviewItems,
    totalsRow: buildTotalsRow(skills, slashCommands, mcp, hooks, permissions, agents, copy),
    harnessRows: buildHarnessRows(skills, slashCommands, mcp, hooks, permissions, agents, copy),
  };
}

function buildTotalsRow(
  skills: SkillsWorkspaceData | null | undefined,
  slashCommands: SlashCommandListDto | null | undefined,
  mcp: McpInventoryDto | null | undefined,
  hooks: HookInventoryDto | null | undefined,
  permissions: PermissionInventoryDto | null | undefined,
  agents: AgentInventoryDto | null | undefined,
  copy: OverviewCopy,
): OverviewHarnessRow {
  const managedCount = (
    entries?: Array<{ kind: "managed" | "unmanaged" }> | null,
  ): number => entries?.filter((entry) => entry.kind === "managed").length ?? 0;
  const unmanagedCount = (
    entries?: Array<{ kind: "managed" | "unmanaged" }> | null,
  ): number => entries?.filter((entry) => entry.kind === "unmanaged").length ?? 0;
  const driftedCount = (
    entries?: Array<{ kind: "managed" | "unmanaged"; sightings?: Array<{ state: string }> }> | null,
  ): number =>
    entries?.filter((entry) =>
      entry.kind === "managed" && entry.sightings?.some((sighting) => sighting.state === "drifted"),
    ).length ?? 0;

  return {
    harness: "__all__",
    label: copy.sections.allHarnesses,
    logoKey: null,
    availabilityIssues: [],
    cells: {
      // Catalog totals: everything the store manages, regardless of which
      // harnesses have adopted it.
      skills: {
        active: skills?.summary.managed ?? 0,
        review: skills?.summary.unmanaged ?? 0,
      },
      commands: {
        active: slashCommands?.commands?.length ?? 0,
        review: slashCommands?.reviewCommands?.length ?? 0,
      },
      mcp: {
        active: managedCount(mcp?.entries),
        review: unmanagedCount(mcp?.entries) + driftedCount(mcp?.entries),
      },
      hooks: {
        active: managedCount(hooks?.entries),
        review: unmanagedCount(hooks?.entries) + driftedCount(hooks?.entries),
      },
      permissions: {
        active: managedCount(permissions?.entries),
        review: unmanagedCount(permissions?.entries) + driftedCount(permissions?.entries),
      },
      agents: {
        active: managedCount(agents?.entries),
        review: unmanagedCount(agents?.entries),
      },
    },
  };
}

/** Canonical capability surfaces with URL-backed harness filter targets. */
const COVERAGE_CELL_ROUTES: Record<OverviewHarnessCellKey, { active: string; review: string }> = {
  skills: { active: "/skills", review: "/skills?status=untracked" },
  commands: { active: "/slash-commands", review: "/slash-commands?status=untracked" },
  mcp: { active: "/mcp", review: "/mcp?status=untracked" },
  hooks: { active: "/hooks", review: "/hooks?status=untracked" },
  permissions: { active: "/permissions", review: "/permissions?status=untracked" },
  agents: { active: "/agents", review: "/agents?status=untracked" },
};

export interface CoverageCellLinks {
  /** Capability surface filtered to the harness (for cells with active items). */
  activeTo: string;
  /** Capability review surface filtered to the harness (for cells with review items). */
  reviewTo: string;
}

export function coverageCellLinks(
  cellKey: OverviewHarnessCellKey,
  harness?: string,
): CoverageCellLinks {
  const routes = COVERAGE_CELL_ROUTES[cellKey];
  const suffix = (route: string) =>
    harness ? `${route.includes("?") ? "&" : "?"}harness=${encodeURIComponent(harness)}` : "";
  return {
    activeTo: `${routes.active}${suffix(routes.active)}`,
    reviewTo: `${routes.review}${suffix(routes.review)}`,
  };
}

function buildShortcuts(copy: OverviewCopy): OverviewShortcut[] {
  return [
    { key: "manage-skills", label: copy.extensions.skills, to: skillsRoutes.inUse, group: "manage" },
    { key: "manage-slash-commands", label: copy.extensions.slashCommands, to: slashCommandRoutes.inUse, group: "manage" },
    { key: "manage-mcp", label: copy.extensions.mcpServers, to: mcpRoutes.inUse, group: "manage" },
    { key: "manage-hooks", label: "Hooks", to: hooksRoutes.inUse, group: "manage" },
    { key: "manage-permissions", label: "Permissions", to: permissionsRoutes.inUse, group: "manage" },
    { key: "manage-agents", label: "Agents", to: agentsRoutes.inUse, group: "manage" },
    { key: "discover-skills", label: copy.marketplace.skills, to: marketplaceRoutes.skills, group: "discover" },
    { key: "discover-mcp", label: copy.marketplace.mcp, to: marketplaceRoutes.mcp, group: "discover" },
    { key: "discover-clis", label: copy.marketplace.cli, to: marketplaceRoutes.clis, group: "discover" },
  ];
}


function buildReviewItems({
  skillsToReview,
  slashCommandsToReview,
  mcpConfigsToReview,
  differentConfigMcpServers,
  inventoryIssues,
  unavailableHarnesses,
  copy,
}: {
  skillsToReview: number | null;
  slashCommandsToReview: number | null;
  mcpConfigsToReview: number | null;
  differentConfigMcpServers: number | null;
  inventoryIssues: number | null;
  unavailableHarnesses: number | null;
  copy: OverviewCopy;
}): OverviewReviewItem[] {
  const items: OverviewReviewItem[] = [];
  if (skillsToReview && skillsToReview > 0) {
    items.push({
      key: "skills-review",
      label: copy.reviewItems.skillsLabel,
      description: copy.reviewItems.skillsDescription,
      count: skillsToReview,
      to: skillsRoutes.needsReview,
      tone: "neutral",
    });
  }
  if (slashCommandsToReview && slashCommandsToReview > 0) {
    items.push({
      key: "slash-commands-review",
      label: copy.reviewItems.slashCommandsLabel,
      description: copy.reviewItems.slashCommandsDescription,
      count: slashCommandsToReview,
      to: slashCommandRoutes.needsReview,
      tone: "warning",
    });
  }
  if (mcpConfigsToReview && mcpConfigsToReview > 0) {
    items.push({
      key: "mcp-review",
      label: copy.reviewItems.mcpConfigsLabel,
      description: copy.reviewItems.mcpConfigsDescription,
      count: mcpConfigsToReview,
      to: mcpRoutes.needsReview,
      tone: "neutral",
    });
  }
  if (differentConfigMcpServers && differentConfigMcpServers > 0) {
    items.push({
      key: "different-mcp-configs",
      label: copy.reviewItems.differentMcpLabel,
      description: copy.reviewItems.differentMcpDescription,
      count: differentConfigMcpServers,
      to: mcpRoutes.inUse,
      tone: "warning",
    });
  }
  if (inventoryIssues && inventoryIssues > 0) {
    items.push({
      key: "mcp-inventory-issues",
      label: copy.reviewItems.inventoryIssuesLabel,
      description: copy.reviewItems.inventoryIssuesDescription,
      count: inventoryIssues,
      to: mcpRoutes.inUse,
      tone: "danger",
    });
  }
  if (unavailableHarnesses && unavailableHarnesses > 0) {
    items.push({
      key: "unavailable-mcp-harnesses",
      label: copy.reviewItems.unavailableHarnessLabel,
      description: copy.reviewItems.unavailableHarnessDescription,
      count: unavailableHarnesses,
      to: "/settings",
      tone: "warning",
    });
  }
  return items;
}

function emptyCells(): Record<OverviewHarnessCellKey, OverviewCoverageCell> {
  const cell = (): OverviewCoverageCell => ({ active: 0, review: 0 });
  return {
    skills: cell(),
    commands: cell(),
    mcp: cell(),
    hooks: cell(),
    permissions: cell(),
    agents: cell(),
  };
}

function buildHarnessRows(
  skills: SkillsWorkspaceData | null | undefined,
  slashCommands: SlashCommandListDto | null | undefined,
  mcp: McpInventoryDto | null | undefined,
  hooks: HookInventoryDto | null | undefined,
  permissions: PermissionInventoryDto | null | undefined,
  agents: AgentInventoryDto | null | undefined,
  copy: OverviewCopy,
): OverviewHarnessRow[] {
  const harnesses = new Map<string, HarnessAccumulator>();
  let nextOrder = 0;

  const ensureHarness = (args: {
    harness: string;
    label?: string | null;
    logoKey?: string | null;
  }): HarnessAccumulator => {
    const existing = harnesses.get(args.harness);
    if (existing) {
      if (!existing.logoKey && args.logoKey) existing.logoKey = args.logoKey;
      if (existing.label === args.harness && args.label) existing.label = args.label;
      return existing;
    }
    const row: HarnessAccumulator = {
      harness: args.harness,
      label: args.label ?? args.harness,
      logoKey: args.logoKey ?? null,
      cells: emptyCells(),
      availabilityIssues: [],
      order: nextOrder,
    };
    nextOrder += 1;
    harnesses.set(args.harness, row);
    return row;
  };

  // Skills coverage.
  for (const column of skills?.harnessColumns ?? []) {
    ensureHarness({
      harness: column.harness,
      label: column.label,
      logoKey: column.logoKey ?? column.harness,
    });
  }
  for (const row of skills?.rows ?? []) {
    for (const cell of row.cells) {
      const harness = ensureHarness({
        harness: cell.harness,
        label: cell.label,
        logoKey: cell.logoKey ?? cell.harness,
      });
      if (cell.state === "enabled") harness.cells.skills.active += 1;
      if (cell.state === "found") harness.cells.skills.review += 1;
    }
  }

  // Slash command sync coverage.
  for (const command of slashCommands?.commands ?? []) {
    for (const syncTarget of command.syncTargets) {
      if (syncTarget.status !== "synced") continue;
      const target = slashCommands?.targets.find((candidate) => candidate.id === syncTarget.target);
      ensureHarness({
        harness: syncTarget.target,
        label: target?.label,
        logoKey: target?.id ?? syncTarget.target,
      }).cells.commands.active += 1;
    }
  }
  for (const reviewCommand of slashCommands?.reviewCommands ?? []) {
    const target = slashCommands?.targets.find((candidate) => candidate.id === reviewCommand.target);
    ensureHarness({
      harness: reviewCommand.target,
      label: target?.label ?? reviewCommand.targetLabel,
      logoKey: reviewCommand.target,
    }).cells.commands.review += 1;
  }

  // MCP server coverage + writability.
  for (const column of mcp?.columns ?? []) {
    const harness = ensureHarness({
      harness: column.harness,
      label: column.label,
      logoKey: column.logoKey ?? column.harness,
    });
    if (column.mcpWritable === false) {
      harness.availabilityIssues.push({
        capability: "MCP",
        reason: column.mcpUnavailableReason ?? copy.sections.unavailableFallback,
      });
    }
  }
  accumulateSightings(ensureHarness, mcp, "mcp");

  // Hooks coverage + writability.
  for (const column of hooks?.columns ?? []) {
    ensureHarness({
      harness: column.harness,
      label: column.label,
      logoKey: column.logoKey ?? column.harness,
    });
    if (column.hooksWritable === false) {
      harnesses.get(column.harness)?.availabilityIssues.push({
        capability: "Hooks",
        reason: column.hooksUnavailableReason ?? copy.sections.unavailableFallback,
      });
    }
  }
  accumulateSightings(ensureHarness, hooks, "hooks");

  // Permissions coverage + writability.
  for (const column of permissions?.columns ?? []) {
    ensureHarness({
      harness: column.harness,
      label: column.label,
      logoKey: column.logoKey ?? column.harness,
    });
    if (column.permissionsWritable === false) {
      harnesses.get(column.harness)?.availabilityIssues.push({
        capability: "Permissions",
        reason: column.permissionsUnavailableReason ?? copy.sections.unavailableFallback,
      });
    }
  }
  accumulateSightings(ensureHarness, permissions, "permissions");

  // Agents coverage (bindings; no writable concept).
  for (const column of agents?.columns ?? []) {
    if (!column.installed) continue;
    ensureHarness({
      harness: column.harness,
      label: column.label,
      logoKey: column.logoKey ?? column.harness,
    });
  }
  for (const entry of agents?.entries ?? []) {
    for (const binding of entry.bindings) {
      if (binding.state === "unsupported") continue;
      const harness = ensureHarness({ harness: binding.harness, label: binding.harness });
      if (entry.kind === "managed" && binding.state === "enabled") {
        harness.cells.agents.active += 1;
      }
      if (entry.kind === "unmanaged") {
        harness.cells.agents.review += 1;
      }
    }
  }

  return Array.from(harnesses.values())
    .sort((a, b) => a.order - b.order)
    .map(({ order: _order, ...row }) => row);
}

interface SightingsSource {
  columns?: Array<{ harness: string; label: string; logoKey?: string | null }> | null;
  entries?:
    | Array<{
        kind: "managed" | "unmanaged";
        sightings: Array<{ harness: string; state: string }>;
      }>
    | null;
}

function accumulateSightings(
  ensureHarness: (args: { harness: string; label?: string | null; logoKey?: string | null }) => HarnessAccumulator,
  source: SightingsSource | null | undefined,
  cellKey: "mcp" | "hooks" | "permissions",
): void {
  for (const entry of source?.entries ?? []) {
    for (const sighting of entry.sightings) {
      if (sighting.state === "unsupported" || sighting.state === "missing") continue;
      const column = source?.columns?.find((candidate) => candidate.harness === sighting.harness);
      const harness = ensureHarness({
        harness: sighting.harness,
        label: column?.label,
        logoKey: column?.logoKey ?? sighting.harness,
      });
      if (entry.kind === "managed" && sighting.state === "managed") {
        harness.cells[cellKey].active += 1;
      }
      if (
        (entry.kind === "managed" && sighting.state === "drifted") ||
        (entry.kind === "unmanaged" && sighting.state === "unmanaged")
      ) {
        harness.cells[cellKey].review += 1;
      }
    }
  }
}

export function inUseMcpHarnessCount(mcp: McpInventoryDto | null | undefined): number | null {
  if (!mcp) return null;
  return mcp.columns.filter(isMcpHarnessAddressable).length;
}
