import { useCallback, useEffect, useMemo, useState } from "react";
import { FolderPlus, Plus } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import { BulkActionBar } from "../../../components/BulkActionBar";
import { ConfirmActionDialog } from "../../../components/ConfirmActionDialog";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { FilterBar } from "../../../components/FilterBar";
import { HarnessFilterChip } from "../../../components/HarnessFilterChip";
import { LoadingSpinner } from "../../../components/LoadingSpinner";
import { PageHeader } from "../../../components/PageHeader";
import { useToast } from "../../../components/Toast";
import { useCommonCopy } from "../../../i18n";
import { SelectionMenu } from "../../../components/ui/SelectionMenu";
import { SkillDetailModal } from "../components/detail/SkillDetailModal";
import { SkillAgentFilterBar } from "../components/tags/SkillAgentFilterBar";
import { SkillTagFilterBar } from "../components/tags/SkillTagFilterBar";
import { MatrixView } from "../components/matrix/MatrixView";
import { SkillsEmptyState } from "../components/pane/SkillsEmptyState";
import { useSkillsCopy } from "../i18n";
import {
  extractSkillAgentCounts,
  extractSkillTagCounts,
  filterSkills,
  skillsStatusCounts,
  type SkillsStatusFilter,
} from "../model/selectors";
import { useSkillsInUseSession } from "../model/session";
import { pendingToggleHarnessesForSkill } from "../model/pending";
import { useSkillsWorkspaceController } from "../model/use-skills-workspace-controller";
import { skillStatusConcept } from "../../../lib/product-language";

const STATUS_VALUES: SkillsStatusFilter[] = ["all", "enabled", "all-harnesses", "off", "untracked"];

function isSkillsStatusFilter(value: string | null): value is SkillsStatusFilter {
  return value !== null && STATUS_VALUES.includes(value as SkillsStatusFilter);
}

export default function SkillsWorkspacePage() {
  const controller = useSkillsWorkspaceController();
  const {
    context,
    selectedSkillRef,
    isDesktopDetailOpen,
    closeSelectedSkill,
    handleManageSkill,
    handleToggleSkill,
    handleUpdateSkill,
    handleRemoveSkill,
    handleDeleteSkill,
    actionErrorMessage,
    queryErrorMessage,
    dismissActionError,
  } = controller;
  const {
    data,
    status: controllerStatus,
    isInitialLoading,
    pendingToggleKeys,
    pendingStructuralActions,
    pendingBulkAction,
    multiSelectedRefs,
    multiSelectPending,
    selectedSkillRef: selectedRef,
    onOpenSkill,
    onToggleCell,
    onToggleMultiSelect,
    onClearMultiSelect,
    onMultiSelectEnableAll,
    onMultiSelectDisableAll,
    onMultiSelectEnableHarness,
    onMultiSelectDisableHarness,
    onMultiSelectDelete,
    onMultiSelectStar,
    onMultiSelectTag,
    onMultiSelectAgent,
    attachAgentsState,
    onConfirmAttachAgents,
    onCancelAttachAgents,
    onDeleteSkill,
    onToggleStar,
    onManageAll,
    onManageSkill,
  } = context;
  const [searchParams, setSearchParams] = useSearchParams();
  const { filters, updateFilters } = useSkillsInUseSession();
  const [selectedUntrackedRefs, setSelectedUntrackedRefs] = useState<ReadonlySet<string>>(() => new Set());
  const [pendingUntrackedAction, setPendingUntrackedAction] = useState<"adopt" | "delete" | null>(null);
  const copy = useSkillsCopy();
  const common = useCommonCopy();
  const { toast } = useToast();

  const statusParam = searchParams.get("status");
  const statusFilter: SkillsStatusFilter = isSkillsStatusFilter(statusParam) ? statusParam : "all";
  const setStatusFilter = useCallback(
    (next: SkillsStatusFilter) => {
      const params = new URLSearchParams(searchParams);
      if (next === "all") params.delete("status");
      else params.set("status", next);
      setSearchParams(params, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  // URL-backed agent filters (?agent=)
  const selectedAgents = useMemo(() => searchParams.getAll("agent"), [searchParams]);
  // Filter options: only agents that actually carry a skill (with counts).
  const knownAgents = useMemo(() => extractSkillAgentCounts(data), [data]);
  // Bulk attach/detach vocabulary: every adopted agent. Deliberately NOT the
  // filter options above - those only list agents that already carry a skill,
  // so reusing them here left the popover empty until something was already
  // attached, which made the first attach impossible.
  const agentOptions = useMemo(() => data?.agentOptions ?? [], [data]);

  const toggleAgentFilter = useCallback(
    (agentRef: string) => {
      const params = new URLSearchParams(searchParams);
      const currentAgents = params.getAll("agent");
      const hasAgent = currentAgents.includes(agentRef);
      params.delete("agent");
      if (!hasAgent) {
        for (const a of currentAgents) {
          params.append("agent", a);
        }
        params.append("agent", agentRef);
      } else {
        for (const a of currentAgents) {
          if (a !== agentRef) {
            params.append("agent", a);
          }
        }
      }
      setSearchParams(params, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const clearAgentFilters = useCallback(() => {
    const params = new URLSearchParams(searchParams);
    params.delete("agent");
    setSearchParams(params, { replace: true });
  }, [searchParams, setSearchParams]);

  // URL-backed tag filters (?tag=)
  const selectedTags = useMemo(() => searchParams.getAll("tag"), [searchParams]);
  const knownTags = useMemo(() => extractSkillTagCounts(data), [data]);
  const knownTagNames = useMemo(() => knownTags.map((t) => t.tag), [knownTags]);

  const toggleTagFilter = useCallback(
    (tagToToggle: string) => {
      const params = new URLSearchParams(searchParams);
      const currentTags = params.getAll("tag");
      const normalized = tagToToggle.toLowerCase();
      const hasTag = currentTags.some((t) => t.toLowerCase() === normalized);
      params.delete("tag");
      if (!hasTag) {
        for (const t of currentTags) {
          params.append("tag", t);
        }
        params.append("tag", tagToToggle);
      } else {
        for (const t of currentTags) {
          if (t.toLowerCase() !== normalized) {
            params.append("tag", t);
          }
        }
      }
      setSearchParams(params, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const clearTagFilters = useCallback(() => {
    const params = new URLSearchParams(searchParams);
    params.delete("tag");
    setSearchParams(params, { replace: true });
  }, [searchParams, setSearchParams]);

  // URL-backed harness deep-link filter (from Overview coverage cells).
  const harnessParam = searchParams.get("harness");
  const clearHarnessFilter = useCallback(() => {
    const params = new URLSearchParams(searchParams);
    params.delete("harness");
    setSearchParams(params, { replace: true });
  }, [searchParams, setSearchParams]);

  const rows = useMemo(
    () =>
      filterSkills(data, {
        search: filters.search,
        status: statusFilter,
        harness: harnessParam,
        tags: selectedTags,
        agents: selectedAgents,
      }),
    [data, filters.search, statusFilter, harnessParam, selectedTags, selectedAgents],
  );
  const sortedRows = rows;
  const counts = useMemo(() => skillsStatusCounts(data), [data]);
  const untrackedRefs = useMemo(
    () => new Set(sortedRows.filter((row) => skillStatusConcept(row.displayStatus) === "needsReview").map((row) => row.skillRef)),
    [sortedRows],
  );
  const managedCount = data?.summary.managed ?? 0;
  const untrackedCount = data?.summary.unmanaged ?? 0;
  const hasData = (data?.rows.length ?? 0) > 0;
  const isReady = controllerStatus === "ready" && Boolean(data);
  const hasActiveFilters =
    filters.search.trim() !== "" || statusFilter !== "all" || harnessParam != null || selectedTags.length > 0 || selectedAgents.length > 0;

  useEffect(() => {
    setSelectedUntrackedRefs((current) => {
      let changed = false;
      const next = new Set<string>();
      for (const ref of current) {
        if (untrackedRefs.has(ref)) next.add(ref);
        else changed = true;
      }
      return changed ? next : current;
    });
  }, [untrackedRefs]);

  // Match the other inventory pages: changing filters drops managed rows that
  // are no longer represented by the matrix.
  useEffect(() => {
    const visibleManagedRefs = new Set(
      sortedRows
        .filter((row) => skillStatusConcept(row.displayStatus) === "inUse")
        .map((row) => row.skillRef),
    );
    for (const ref of multiSelectedRefs) {
      if (!visibleManagedRefs.has(ref)) onToggleMultiSelect(ref);
    }
  }, [multiSelectedRefs, onToggleMultiSelect, sortedRows]);

  const toggleChecked = useCallback(
    (skillRef: string) => {
      const row = data?.rows.find((candidate) => candidate.skillRef === skillRef);
      if (row && skillStatusConcept(row.displayStatus) === "needsReview") {
        setSelectedUntrackedRefs((current) => {
          const next = new Set(current);
          if (next.has(skillRef)) next.delete(skillRef);
          else next.add(skillRef);
          return next;
        });
      } else {
        onToggleMultiSelect(skillRef);
      }
    },
    [data, onToggleMultiSelect],
  );

  const checkedRefs = useMemo(
    () => new Set([...multiSelectedRefs, ...selectedUntrackedRefs]),
    [multiSelectedRefs, selectedUntrackedRefs],
  );

  const handleAdoptSelected = useCallback(async () => {
    const refs = sortedRows
      .filter((row) => selectedUntrackedRefs.has(row.skillRef) && row.actions.canManage)
      .map((row) => row.skillRef);
    if (refs.length === 0) return;
    setPendingUntrackedAction("adopt");
    try {
      for (const ref of refs) {
        try {
          await onManageSkill(ref);
        } catch {
          // The workspace error banner already surfaces the failure; continue with the rest.
        }
      }
      setSelectedUntrackedRefs((current) => new Set([...current].filter((ref) => !refs.includes(ref))));
    } finally {
      setPendingUntrackedAction(null);
    }
  }, [onManageSkill, selectedUntrackedRefs, sortedRows]);

  const handleDeleteSelectedUntracked = useCallback(async () => {
    const refs = sortedRows
      .filter((row) => selectedUntrackedRefs.has(row.skillRef) && row.actions.canDelete)
      .map((row) => row.skillRef);
    if (refs.length === 0) return;
    setPendingUntrackedAction("delete");
    const failed = new Set<string>();
    try {
      for (const ref of refs) {
        try {
          await onDeleteSkill(ref);
        } catch {
          failed.add(ref);
        }
      }
      setSelectedUntrackedRefs((current) => new Set([...current].filter((ref) => failed.has(ref))));
    } finally {
      setPendingUntrackedAction(null);
    }
  }, [onDeleteSkill, selectedUntrackedRefs, sortedRows]);

  const hasDeletableUntrackedSelection = useMemo(
    () => sortedRows.some((row) => selectedUntrackedRefs.has(row.skillRef) && row.actions.canDelete),
    [selectedUntrackedRefs, sortedRows],
  );
  const selectedAdoptableUntrackedCount = useMemo(
    () => sortedRows.filter((row) => selectedUntrackedRefs.has(row.skillRef) && row.actions.canManage).length,
    [selectedUntrackedRefs, sortedRows],
  );
  const selectedManagedCount = multiSelectedRefs.size;
  const selectedCount = checkedRefs.size;
  const selectedDeletableCount = selectedManagedCount + (hasDeletableUntrackedSelection ?
    sortedRows.filter((row) => selectedUntrackedRefs.has(row.skillRef) && row.actions.canDelete).length : 0);
  const bulkHarnessOptions = data?.harnessColumns
    .filter((column) => column.installed)
    .map((column) => ({ harness: column.harness, label: column.label }));

  const handleDeleteSelected = useCallback(async (): Promise<void> => {
    const tasks: Promise<void>[] = [];
    if (selectedManagedCount > 0) tasks.push(onMultiSelectDelete());
    if (selectedUntrackedRefs.size > 0) tasks.push(handleDeleteSelectedUntracked());
    await Promise.all(tasks);
  }, [handleDeleteSelectedUntracked, onMultiSelectDelete, selectedManagedCount, selectedUntrackedRefs.size]);

  const clearFilters = useCallback(() => {
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete("tag");
        next.delete("agent");
        next.delete("status");
        next.delete("harness");
        return next;
      },
      { replace: true },
    );
    updateFilters({ search: "" });
  }, [setSearchParams, updateFilters]);

  const statusOptions = useMemo(
    () => STATUS_VALUES.map((value) => ({ value, label: statusLabel(copy, value), meta: counts[value] })),
    [copy, counts],
  );
  const selectedPendingToggleHarnesses = selectedSkillRef
    ? pendingToggleHarnessesForSkill(pendingToggleKeys, selectedSkillRef)
    : EMPTY_PENDING_TOGGLE_HARNESSES;

  return (
    <>
      {actionErrorMessage ? <ErrorBanner message={actionErrorMessage} onDismiss={dismissActionError} /> : null}
      {!actionErrorMessage && hasData && queryErrorMessage ? <ErrorBanner message={queryErrorMessage} /> : null}

      <div className="page-chrome">
        <PageHeader
          title={statusFilter === "untracked" ? copy.review.title : copy.inUse.title}
          subtitle={
            statusFilter === "untracked"
              ? copy.review.subtitle(untrackedCount)
              : copy.inUse.subtitle(managedCount + untrackedCount)
          }
          actions={
            statusFilter === "untracked" ? (
              <button
                type="button"
                className="action-pill action-pill--md action-pill--accent"
                disabled={pendingBulkAction !== null || untrackedCount === 0}
                onClick={onManageAll}
              >
                {pendingBulkAction === "manage-all" ? <LoadingSpinner size="sm" label={copy.review.adoptingAllSkills} /> : null}
                {copy.review.adoptAllEligible}
              </button>
            ) : (
              <button
                type="button"
                className="action-pill action-pill--md"
                onClick={() => toast(copy.inUse.importFolderComingSoon)}
              >
                <FolderPlus size={14} />
                {copy.inUse.importFolder}
              </button>
            )
          }
        />
        {hasData ? (
          <>
            <FilterBar
              searchValue={filters.search}
              onSearchChange={(search) => updateFilters({ search })}
              searchPlaceholder={statusFilter === "untracked" ? copy.review.searchPlaceholder : copy.inUse.searchPlaceholder}
              searchLabel={statusFilter === "untracked" ? copy.review.searchLabel : copy.inUse.searchLabel}
              trailing={
                <>
                  {harnessParam ? (
                    <HarnessFilterChip
                      label={data?.harnessColumns.find((column) => column.harness === harnessParam)?.label ?? harnessParam}
                      onClear={clearHarnessFilter}
                    />
                  ) : null}
                  <SelectionMenu
                    value={statusFilter}
                    options={statusOptions}
                    active={statusFilter !== "all"}
                    ariaLabel={statusLabel(copy, statusFilter)}
                    onChange={setStatusFilter}
                  />
                </>
              }
            />
            <SkillTagFilterBar
              tags={knownTags}
              selectedTags={selectedTags}
              onToggleTag={toggleTagFilter}
              onClearTags={clearTagFilters}
            />
            <SkillAgentFilterBar
              agents={knownAgents}
              selectedAgents={selectedAgents}
              onToggleAgent={toggleAgentFilter}
              onClearAgents={clearAgentFilters}
            />
          </>
        ) : null}
      </div>

      {isInitialLoading ? (
        <div className="panel-state"><LoadingSpinner size="md" label={copy.inUse.loading} /></div>
      ) : controllerStatus === "error" ? (
        <div className="panel-state">{queryErrorMessage || copy.inUse.unableToLoad}</div>
      ) : isReady && data ? (
        sortedRows.length > 0 ? (
          <MatrixView
            rows={sortedRows}
            harnessColumns={data.harnessColumns}
            checkedRefs={checkedRefs}
            selectedSkillRef={selectedRef}
            pendingToggleKeys={pendingToggleKeys}
            onOpenSkill={onOpenSkill}
            onToggleChecked={toggleChecked}
            onToggleCell={onToggleCell}
            onToggleStar={onToggleStar}
            onManageSkill={(ref) => void onManageSkill(ref)}
            onToggleAgent={toggleAgentFilter}
            pendingStructuralActions={pendingStructuralActions}
            starredFilterActive={selectedTags.some((t) => t.toLowerCase() === "starred")}
            onToggleStarredFilter={() => toggleTagFilter("starred")}
          />
        ) : hasData || hasActiveFilters ? (
          <SkillsEmptyState copy={copy.filters} onResetFilters={clearFilters} />
        ) : (
          <div className="empty-panel">
            <h3 className="empty-panel__title">{copy.inUse.emptyTitle}</h3>
            <p className="empty-panel__body">{copy.inUse.emptyBody}</p>
            <div className="empty-panel__actions">
              <button type="button" className="action-pill action-pill--md" onClick={clearFilters} disabled={!hasActiveFilters}>
                {common.actions.clearFilters}
              </button>
            </div>
          </div>
        )
      ) : null}

      {selectedCount > 0 ? (
        <BulkActionBar
          selectedCount={selectedCount}
          pending={multiSelectPending ?? pendingUntrackedAction}
          onClear={() => {
            onClearMultiSelect();
            setSelectedUntrackedRefs(new Set());
          }}
          showHarnessActions={selectedManagedCount > 0}
          onEnableAll={onMultiSelectEnableAll}
          onDisableAll={onMultiSelectDisableAll}
          harnessOptions={bulkHarnessOptions}
          onEnableHarness={onMultiSelectEnableHarness}
          onDisableHarness={onMultiSelectDisableHarness}
          onDelete={handleDeleteSelected}
          showDestructiveAction={selectedDeletableCount > 0}
          onStarSelected={selectedManagedCount > 0 ? onMultiSelectStar : undefined}
          starLabel="Star selected"
          onTagSelected={selectedManagedCount > 0 ? onMultiSelectTag : undefined}
          knownTags={knownTagNames}
          onAgentSelected={selectedManagedCount > 0 ? onMultiSelectAgent : undefined}
          knownAgents={agentOptions}
          extraActions={
            selectedAdoptableUntrackedCount > 0 ? (
              <button
                type="button"
                className="bulk-bar__action"
                onClick={() => void handleAdoptSelected()}
                disabled={pendingUntrackedAction !== null || multiSelectPending !== null}
              >
                {pendingUntrackedAction === "adopt" ? <LoadingSpinner size="sm" label={copy.review.adoptingSelected} /> : <Plus size={15} />}
                {selectedAdoptableUntrackedCount === selectedCount
                  ? copy.review.adoptSelected
                  : `${copy.review.adoptSelected} (${selectedAdoptableUntrackedCount})`}
              </button>
            ) : null
          }
          destructive={{
            actionLabel: selectedManagedCount === 0 ? copy.review.deleteSelected : copy.bulk.delete,
            confirmTitle: selectedManagedCount === 0
              ? copy.review.deleteConfirmTitle(selectedDeletableCount)
              : copy.bulk.confirmTitle(selectedDeletableCount),
            confirmDescription: selectedManagedCount === 0
              ? copy.review.deleteConfirmDescription
              : copy.bulk.confirmDescription,
            confirmNote: selectedManagedCount === 0 ? copy.review.deleteConfirmNote : copy.bulk.confirmNote,
          }}
        />
      ) : null}

      
      <ConfirmActionDialog
        open={attachAgentsState !== null}
        onOpenChange={(open) => {
          if (!open) onCancelAttachAgents();
        }}
        title={attachAgentsState?.mode === "attach" ? "Attach agents?" : "Detach agents?"}
        description={
          attachAgentsState ? (
            <span>
              {formatAttachAgentPreview(
                attachAgentsState,
                data?.harnessColumns ?? [],
                selectedUntrackedRefs.size,
              )}
            </span>
          ) : ""
        }
        note={attachAgentsState?.mode === "detach" ? "Detaching leaves the skill installed on its harnesses." : undefined}
        confirmLabel={attachAgentsState?.mode === "attach" ? "Attach" : "Detach"}
        pendingLabel={attachAgentsState?.mode === "attach" ? "Attaching" : "Detaching"}
        confirmTone={attachAgentsState?.mode === "attach" ? "primary" : "danger"}
        onConfirm={onConfirmAttachAgents}
        isPending={multiSelectPending === "attach-agents"}
      />

      <SkillDetailModal
        open={isDesktopDetailOpen || Boolean(selectedSkillRef)}
        skillRef={selectedSkillRef}
        knownTags={knownTagNames}
        pendingToggleHarnesses={selectedPendingToggleHarnesses}
        pendingStructuralAction={selectedSkillRef ? pendingStructuralActions.get(selectedSkillRef) ?? null : null}
        onClose={closeSelectedSkill}
        onManageSkill={handleManageSkill}
        onToggleSkill={handleToggleSkill}
        onUpdateSkill={handleUpdateSkill}
        onRemoveSkill={handleRemoveSkill}
        onDeleteSkill={handleDeleteSkill}
      />
    </>
  );
}

const EMPTY_PENDING_TOGGLE_HARNESSES = new Set<string>();

function statusLabel(copy: ReturnType<typeof useSkillsCopy>, value: SkillsStatusFilter): string {
  if (value === "all") return copy.inUse.pills.all;
  if (value === "enabled") return copy.inUse.pills.enabled;
  if (value === "all-harnesses") return copy.inUse.pills.allHarnesses;
  if (value === "off") return copy.inUse.pills.off;
  return copy.review.title;
}

type AttachAgentsState = NonNullable<ReturnType<typeof useSkillsWorkspaceController>["context"]["attachAgentsState"]>;

function formatAttachAgentPreview(
  state: AttachAgentsState,
  harnessColumns: readonly { harness: string; label: string }[],
  skippedUnmanagedCount: number,
): string {
  const action = state.mode === "attach" ? "attach" : "detach";
  const changedCount = state.projection.changed.length;
  const bindingCount = state.projection.autoEnabled.length;
  const harnessLabels = formatHarnessNames(state.projection.autoEnabled.map((item) => item.harness), harnessColumns);
  const bindingText = state.mode === "attach"
    ? bindingCount > 0
      ? `creating ${bindingCount} new harness binding${bindingCount === 1 ? "" : "s"} on ${harnessLabels}`
      : "creating no new harness bindings"
    : "removing no harness bindings";
  const skippedRows = skippedUnmanagedCount > 0
    ? ` ${skippedUnmanagedCount} unmanaged selected row${skippedUnmanagedCount === 1 ? " is" : "s are"} skipped because only managed skills can be attached to agents.`
    : "";
  const skippedAgents = state.projection.skipped.length > 0
    ? ` ${state.projection.skipped.length} agent${state.projection.skipped.length === 1 ? " is" : "s are"} skipped: ${state.projection.skipped
        .map((item) => `${item.ref} (${item.reason})`)
        .join(", ")}.`
    : "";

  return `You are about to ${action} ${state.agentRefs.length} agent${state.agentRefs.length === 1 ? "" : "s"} across ${state.skillRefs.length} managed skill${state.skillRefs.length === 1 ? "" : "s"}. ${changedCount} agent${changedCount === 1 ? "" : "s"} will change, ${bindingText}.${skippedRows}${skippedAgents}`;
}

function formatHarnessNames(harnesses: string[], harnessColumns: readonly { harness: string; label: string }[]): string {
  const labelsByHarness = new Map(harnessColumns.map((column) => [column.harness, column.label]));
  const labels = Array.from(new Set(harnesses)).map((harness) => labelsByHarness.get(harness) ?? harness);
  if (labels.length === 0) return "no harnesses";
  if (labels.length === 1) return labels[0];
  return `${labels.slice(0, -1).join(", ")} and ${labels[labels.length - 1]}`;
}
