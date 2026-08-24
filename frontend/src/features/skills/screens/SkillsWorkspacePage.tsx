import { useCallback, useEffect, useMemo, useState } from "react";
import { FolderPlus, Plus, X } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import { BulkActionBar } from "../../../components/BulkActionBar";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { FilterBar } from "../../../components/FilterBar";
import { HarnessFilterChip } from "../../../components/HarnessFilterChip";
import { LoadingSpinner } from "../../../components/LoadingSpinner";
import { PageHeader } from "../../../components/PageHeader";
import { useToast } from "../../../components/Toast";
import { useCommonCopy } from "../../../i18n";
import { SelectionMenu } from "../../../components/ui/SelectionMenu";
import { SkillDetailModal } from "../components/detail/SkillDetailModal";
import { SkillTagFilterBar } from "../components/tags/SkillTagFilterBar";
import { MatrixView } from "../components/matrix/MatrixView";
import { SkillsEmptyState } from "../components/pane/SkillsEmptyState";
import { useSkillsCopy } from "../i18n";
import {
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
    onMultiSelectDelete,
    onMultiSelectStar,
    onMultiSelectTag,
    onToggleStar,
    onManageAll,
    onManageSkill,
  } = context;
  const [searchParams, setSearchParams] = useSearchParams();
  const { filters, updateFilters } = useSkillsInUseSession();
  const [selectedUntrackedRefs, setSelectedUntrackedRefs] = useState<ReadonlySet<string>>(() => new Set());
  const [adoptingSelected, setAdoptingSelected] = useState(false);
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
      }),
    [data, filters.search, statusFilter, harnessParam, selectedTags],
  );
  const sortedRows = rows;
  const counts = useMemo(() => skillsStatusCounts(data), [data]);
  const untrackedRefs = useMemo(
    () => new Set(sortedRows.filter((row) => skillStatusConcept(row.displayStatus) === "needsReview" && row.actions.canManage).map((row) => row.skillRef)),
    [sortedRows],
  );
  const managedCount = data?.summary.managed ?? 0;
  const untrackedCount = data?.summary.unmanaged ?? 0;
  const hasData = (data?.rows.length ?? 0) > 0;
  const isReady = controllerStatus === "ready" && Boolean(data);
  const hasActiveFilters =
    filters.search.trim() !== "" || statusFilter !== "all" || harnessParam != null || selectedTags.length > 0;

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
    setAdoptingSelected(true);
    try {
      for (const ref of refs) {
        try {
          await onManageSkill(ref);
        } catch {
          // The workspace error banner already surfaces the failure; continue with the rest.
        }
      }
      setSelectedUntrackedRefs(new Set());
    } finally {
      setAdoptingSelected(false);
    }
  }, [onManageSkill, selectedUntrackedRefs, sortedRows]);

  const clearFilters = useCallback(() => {
    updateFilters({ search: "" });
    const params = new URLSearchParams(searchParams);
    params.delete("status");
    params.delete("harness");
    params.delete("tag");
    setSearchParams(params, { replace: true });
  }, [searchParams, setSearchParams, updateFilters]);

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
            pendingStructuralActions={pendingStructuralActions}
            untrackedSelectionOnly
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

      {multiSelectedRefs.size > 0 ? (
        <BulkActionBar
          selectedCount={multiSelectedRefs.size}
          pending={multiSelectPending}
          onClear={onClearMultiSelect}
          onEnableAll={onMultiSelectEnableAll}
          onDisableAll={onMultiSelectDisableAll}
          onDelete={onMultiSelectDelete}
          onStarSelected={onMultiSelectStar}
          starLabel="Star selected"
          onTagSelected={onMultiSelectTag}
          knownTags={knownTagNames}
          destructive={{
            actionLabel: copy.bulk.delete,
            confirmTitle: copy.bulk.confirmTitle(multiSelectedRefs.size),
            confirmDescription: copy.bulk.confirmDescription,
            confirmNote: copy.bulk.confirmNote,
          }}
        />
      ) : null}

      {selectedUntrackedRefs.size > 0 ? (
        <div className="bulk-dock">
          <div className="bulk-dock__fade" />
          <div className="bulk-bar" data-state="open" role="toolbar" aria-label={common.bulk.ariaLabel}>
            <div className="bulk-bar__group">
              <span className="bulk-bar__count">{common.bulk.selected(selectedUntrackedRefs.size)}</span>
              <button
                type="button"
                className="bulk-bar__clear"
                onClick={() => setSelectedUntrackedRefs(new Set())}
                disabled={adoptingSelected}
                aria-label={common.actions.clearSelection}
              >
                <X size={14} />
              </button>
            </div>
            <span className="bulk-bar__divider" aria-hidden="true" />
            <button
              type="button"
              className="bulk-bar__action"
              onClick={() => void handleAdoptSelected()}
              disabled={adoptingSelected}
            >
              {adoptingSelected ? <LoadingSpinner size="sm" label={copy.review.adoptingSelected} /> : <Plus size={15} />}
              {copy.review.adoptSelected}
            </button>
          </div>
        </div>
      ) : null}

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
