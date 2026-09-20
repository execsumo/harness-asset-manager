import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import { BulkActionBar, type BulkHarnessState, type MultiSelectAction } from "../../../components/BulkActionBar";
import { ConfirmActionDialog } from "../../../components/ConfirmActionDialog";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { FilterBar } from "../../../components/FilterBar";
import { HarnessFilterChip } from "../../../components/HarnessFilterChip";
import { LoadingSpinner } from "../../../components/LoadingSpinner";
import { PageHeader } from "../../../components/PageHeader";
import { TagFilterBar } from "../../../components/tags/TagFilterBar";
import { useCommonCopy } from "../../../i18n";
import { HooksMatrixView } from "../components/HooksMatrixView";
import { HookDetailSheet } from "../components/detail/HookDetailSheet";
import { HookFormDialog } from "../components/edit/HookFormDialog";
import { HooksFilterMenu } from "../components/HooksFilterMenu";
import { useHooksCopy } from "../i18n";
import {
  extractHookTagCounts,
  filterHooks,
  hooksStatusCounts,
  isHooksHarnessAddressable,
  matrixCellFor,
  type HooksStatusFilter,
} from "../model/selectors";
import { useHooksManagementController } from "../model/use-hooks-management-controller";
import { useSetHookTagsMutation } from "../api/management-queries";

const DETAIL_PARAM = "hook";
const STATUS_VALUES: HooksStatusFilter[] = [
  "all",
  "enabled",
  "all-harnesses",
  "unbound",
  "drifted",
  "untracked",
];

function isHooksStatusFilter(value: string | null): value is HooksStatusFilter {
  return value !== null && STATUS_VALUES.includes(value as HooksStatusFilter);
}

/** Unified Hooks inventory. The status filter is URL-backed for deep links. */
export default function HooksInUsePage() {
  const {
    status,
    inventory,
    isInitialLoading,
    pendingHookKeys,
    pendingPerHarnessKeys,
    queryErrorMessage,
    actionErrorMessage,
    clearActionError,
    handleUninstallHook,
    handleToggleHarness,
    handleReconcileHook,
    handleCreateHook,
    handlePromoteHook,
  } = useHooksManagementController();

  const [searchParams, setSearchParams] = useSearchParams();
  const selectedId = searchParams.get(DETAIL_PARAM);
  const [confirmUninstallId, setConfirmUninstallId] = useState<string | null>(null);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [addPending, setAddPending] = useState(false);
  const [search, setSearch] = useState("");
  const [selectedIds, setSelectedIds] = useState<ReadonlySet<string>>(() => new Set());
  const [adoptingSelected, setAdoptingSelected] = useState(false);
  const [pendingSelectedAction, setPendingSelectedAction] = useState<MultiSelectAction | null>(null);
  const setTagsMutation = useSetHookTagsMutation();
  const copy = useHooksCopy();
  const common = useCommonCopy();

  const statusParam = searchParams.get("status");
  const statusFilter: HooksStatusFilter = isHooksStatusFilter(statusParam) ? statusParam : "all";
  const setStatusFilter = useCallback(
    (next: HooksStatusFilter) => {
      const params = new URLSearchParams(searchParams);
      if (next === "all") params.delete("status");
      else params.set("status", next);
      setSearchParams(params, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  // URL-backed harness deep-link filter (from Overview coverage cells).
  const harnessParam = searchParams.get("harness");
  const clearHarnessFilter = useCallback(() => {
    const params = new URLSearchParams(searchParams);
    params.delete("harness");
    setSearchParams(params, { replace: true });
  }, [searchParams, setSearchParams]);

  // URL-backed tag filters (?tag=)
  const selectedTags = useMemo(() => searchParams.getAll("tag"), [searchParams]);
  const knownTags = useMemo(
    () => extractHookTagCounts(inventory),
    [inventory],
  );
  const knownTagNames = useMemo(() => knownTags.map((t) => t.tag), [knownTags]);

  const toggleTagFilter = useCallback(
    (tagToToggle: string) => {
      const params = new URLSearchParams(searchParams);
      const current = params.getAll("tag");
      const normalizedToggle = tagToToggle.toLowerCase();
      params.delete("tag");
      let found = false;
      for (const t of current) {
        if (t.toLowerCase() === normalizedToggle) {
          found = true;
        } else {
          params.append("tag", t);
        }
      }
      if (!found) {
        params.append("tag", tagToToggle);
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

  const starredFilterActive = selectedTags.some((t) => t.toLowerCase() === "starred");
  const onToggleStarredFilter = useCallback(() => {
    toggleTagFilter("starred");
  }, [toggleTagFilter]);

  const handleToggleStar = useCallback(
    async (id: string) => {
      const hookEntry = inventory?.entries.find((e) => e.id === id);
      if (!hookEntry) return;
      const currentTags = hookEntry.tags || [];
      const isStarred = currentTags.some((t) => t.toLowerCase() === "starred");
      const nextTags = isStarred
        ? currentTags.filter((t) => t.toLowerCase() !== "starred")
        : ["starred", ...currentTags.filter((t) => t.toLowerCase() !== "starred")];
      await setTagsMutation.mutateAsync({ id, tags: nextTags });
    },
    [inventory, setTagsMutation],
  );

  const entries = useMemo(
    () => filterHooks(inventory, { search, status: statusFilter, harness: harnessParam, tags: selectedTags }),
    [inventory, search, statusFilter, harnessParam, selectedTags],
  );
  const counts = useMemo(() => hooksStatusCounts(inventory), [inventory]);
  const hasData = (inventory?.entries.length ?? 0) > 0;
  const isReady = status === "ready" && Boolean(inventory);
  const filtersActive = search !== "" || statusFilter !== "all" || harnessParam != null || selectedTags.length > 0;

  // Keep only currently visible rows selected as filters or inventory change.
  useEffect(() => {
    setSelectedIds((current) => {
      const visible = new Set(entries.map((entry) => entry.id));
      let changed = false;
      const next = new Set<string>();
      for (const id of current) {
        if (visible.has(id)) next.add(id);
        else changed = true;
      }
      return changed ? next : current;
    });
  }, [entries]);

  const setDetailId = useCallback(
    (id: string | null) => {
      const next = new URLSearchParams(searchParams);
      if (id) next.set(DETAIL_PARAM, id);
      else next.delete(DETAIL_PARAM);
      setSearchParams(next, { replace: !id });
    },
    [searchParams, setSearchParams],
  );

  const pendingForSelected = useMemo(() => {
    if (!selectedId) return new Set<string>();
    const result = new Set<string>();
    for (const key of pendingPerHarnessKeys) {
      const [id, harness] = key.split(":", 2);
      if (id === selectedId) result.add(harness);
    }
    return result;
  }, [pendingPerHarnessKeys, selectedId]);

  const isHookPendingSelected = selectedId !== null && pendingHookKeys.has(selectedId);

  const handleCreateHookSubmit = async (value: {
    id: string;
    event: string;
    command: string;
    match?: string | null;
    timeout?: number | null;
    description?: string;
  }) => {
    setAddPending(true);
    try {
      await handleCreateHook(value);
      setAddDialogOpen(false);
    } finally {
      setAddPending(false);
    }
  };

  const executeUninstall = useCallback(async () => {
    const target = confirmUninstallId;
    if (!target) return;
    setConfirmUninstallId(null);
    await handleUninstallHook(target);
    if (selectedId === target) setDetailId(null);
  }, [confirmUninstallId, handleUninstallHook, selectedId, setDetailId]);

  const toggleSelected = useCallback((id: string) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const clearSelected = useCallback(() => setSelectedIds(new Set()), []);

  const handleAdoptSelected = useCallback(async () => {
    const ids = entries
      .filter((entry) => entry.kind === "unmanaged" && selectedIds.has(entry.id))
      .map((entry) => entry.id);
    if (ids.length === 0) return;
    setAdoptingSelected(true);
    try {
      for (const id of ids) await handlePromoteHook(id);
      clearSelected();
    } finally {
      setAdoptingSelected(false);
    }
  }, [clearSelected, entries, handlePromoteHook, selectedIds]);

  const clearFilters = useCallback(() => {
    setSearch("");
    const params = new URLSearchParams(searchParams);
    params.delete("status");
    params.delete("harness");
    params.delete("tag");
    setSearchParams(params, { replace: true });
  }, [searchParams, setSearchParams]);

  const harnessFilterLabel = harnessParam
    ? inventory?.columns.find((column) => column.harness === harnessParam)?.label ?? harnessParam
    : null;

  const selectedCount = selectedIds.size;
  const adoptableSelectedCount = useMemo(
    () => entries.filter((entry) => entry.kind === "unmanaged" && selectedIds.has(entry.id)).length,
    [entries, selectedIds],
  );
  const selectedManagedEntries = useMemo(
    () => entries.filter((entry) => entry.kind === "managed" && selectedIds.has(entry.id)),
    [entries, selectedIds],
  );
  const selectedManagedCount = selectedManagedEntries.length;
  const bulkHarnessOptions = inventory?.columns
    .filter(isHooksHarnessAddressable)
    .map((column) => ({
      harness: column.harness,
      label: column.label,
      state: aggregateBulkHarnessState(
        selectedManagedEntries.map((entry) => {
          const action = matrixCellFor(entry, column, copy).action;
          if (action === "disable") return true;
          if (action === "enable") return false;
          return null;
        }),
      ),
    }));

  const handleBulkHarness = useCallback(
    async (harness: string, disable: boolean): Promise<void> => {
      const ids = entries
        .filter((entry) => {
          if (entry.kind !== "managed" || !selectedIds.has(entry.id)) return false;
          const column = inventory?.columns.find((candidate) => candidate.harness === harness);
          return column
            ? matrixCellFor(entry, column, copy).action === (disable ? "disable" : "enable")
            : false;
        })
        .map((entry) => entry.id);
      if (ids.length === 0) return;
      setPendingSelectedAction(disable ? "disable-all" : "enable-all");
      try {
        await Promise.all(ids.map((id) => handleToggleHarness(id, harness, disable, true)));
      } catch {
        // The controller has already surfaced the mutation failure.
      } finally {
        setPendingSelectedAction(null);
      }
    },
    [copy, entries, handleToggleHarness, inventory?.columns, selectedIds],
  );

  return (
    <>
      <div className="page-chrome">
        <PageHeader
          title={copy.inUse.title}
          subtitle={copy.inUse.subtitle}
          actions={
            <button
              type="button"
              className="action-pill action-pill--md action-pill--accent"
              onClick={() => setAddDialogOpen(true)}
            >
              <Plus size={16} />
              Add Hook
            </button>
          }
        />
        {hasData ? (
          <>
            <FilterBar
              searchValue={search}
              onSearchChange={setSearch}
              searchPlaceholder={copy.inUse.searchPlaceholder}
              searchLabel={copy.inUse.searchLabel}
              trailing={
                <>
                  {harnessFilterLabel ? (
                    <HarnessFilterChip label={harnessFilterLabel} onClear={clearHarnessFilter} />
                  ) : null}
                  <HooksFilterMenu
                    pill={statusFilter}
                    counts={counts}
                    onChange={setStatusFilter}
                  />
                </>
              }
            />
            <TagFilterBar
              tags={knownTags}
              selectedTags={selectedTags}
              onToggleTag={toggleTagFilter}
              onClearTags={clearTagFilters}
            />
          </>
        ) : null}
      </div>

      {actionErrorMessage ? <ErrorBanner message={actionErrorMessage} onDismiss={clearActionError} /> : null}

      {isInitialLoading ? (
        <div className="panel-state">
          <LoadingSpinner size="md" label={copy.inUse.loading} />
        </div>
      ) : status === "error" ? (
        <div className="panel-state">{queryErrorMessage || copy.inUse.unableToLoad}</div>
      ) : isReady && inventory ? (
        entries.length > 0 ? (
          <HooksMatrixView
            entries={entries}
            columns={inventory.columns}
            pendingHookKeys={pendingHookKeys}
            pendingPerHarnessKeys={pendingPerHarnessKeys}
            checkedIds={selectedIds}
            onOpenDetail={setDetailId}
            onToggleChecked={toggleSelected}
            onEnableHarness={(id, harness) => void handleToggleHarness(id, harness, false)}
            onDisableHarness={(id, harness) => void handleToggleHarness(id, harness, true)}
            onAdopt={(id) => void handlePromoteHook(id)}
            onToggleStar={handleToggleStar}
            starredFilterActive={starredFilterActive}
            onToggleStarredFilter={onToggleStarredFilter}
          />
        ) : hasData ? (
          <div className="empty-panel">
            <h3 className="empty-panel__title">
              {statusFilter === "untracked" ? "No hooks need review" : common.status.noMatches}
            </h3>
            <p className="empty-panel__body">
              {statusFilter === "untracked"
                ? "Your harness configs only reference hooks that harness-asset-manager already tracks."
                : copy.inUse.noMatchesBody}
            </p>
            <div className="empty-panel__actions">
              <button type="button" className="action-pill action-pill--md" onClick={clearFilters} disabled={!filtersActive}>
                {common.actions.clearFilters}
              </button>
            </div>
          </div>
        ) : (
          <div className="empty-panel">
            <h3 className="empty-panel__title">
              {statusFilter === "untracked" ? "No hooks need review" : copy.inUse.emptyTitle}
            </h3>
            <p className="empty-panel__body">
              {statusFilter === "untracked"
                ? "Your harness configs only reference hooks that harness-asset-manager already tracks."
                : copy.inUse.emptyBody}
            </p>
            <div className="empty-panel__actions">
              <button
                type="button"
                className="action-pill action-pill--md action-pill--accent"
                onClick={() => setAddDialogOpen(true)}
              >
                Add Hook
              </button>
            </div>
          </div>
        )
      ) : null}

      {inventory ? (
        <HookDetailSheet
          id={selectedId}
          knownTags={knownTagNames}
          columns={inventory.columns}
          pendingPerHarness={pendingForSelected}
          isServerPending={isHookPendingSelected}
          isUninstalling={isHookPendingSelected}
          onClose={() => setDetailId(null)}
          onEnableHarness={(harness) => {
            if (selectedId) void handleToggleHarness(selectedId, harness, false);
          }}
          onDisableHarness={(harness) => {
            if (selectedId) void handleToggleHarness(selectedId, harness, true);
          }}
          onResolveConfig={(args) => {
            if (!selectedId) return Promise.resolve();
            return handleReconcileHook({ id: selectedId, ...args });
          }}
          onUninstall={() => {
            if (selectedId) setConfirmUninstallId(selectedId);
          }}
        />
      ) : null}

      <HookFormDialog
        open={addDialogOpen}
        pending={addPending}
        onOpenChange={setAddDialogOpen}
        onSubmit={handleCreateHookSubmit}
      />

      <ConfirmActionDialog
        open={confirmUninstallId !== null}
        title={copy.inUse.uninstall.title(confirmUninstallId ?? "")}
        description={copy.inUse.uninstall.singleDescription}
        confirmLabel={copy.inUse.uninstall.action}
        pendingLabel={copy.inUse.uninstall.pending}
        isPending={false}
        onOpenChange={(open) => {
          if (!open) setConfirmUninstallId(null);
        }}
        onConfirm={executeUninstall}
      />

      {selectedCount > 0 ? (
        <BulkActionBar
          selectedCount={selectedCount}
          pending={pendingSelectedAction}
          onClear={clearSelected}
          showHarnessActions={selectedManagedCount > 0}
          harnessOptions={bulkHarnessOptions}
          onEnableHarness={(harness) => handleBulkHarness(harness, false)}
          onDisableHarness={(harness) => handleBulkHarness(harness, true)}
          onDelete={async () => undefined}
          showDestructiveAction={false}
          extraActions={
            adoptableSelectedCount > 0 ? (
              <button
                type="button"
                className="bulk-bar__action"
                onClick={() => void handleAdoptSelected()}
                disabled={adoptingSelected || pendingSelectedAction !== null}
              >
                {adoptingSelected ? (
                  <LoadingSpinner size="sm" label={copy.inUse.adoptingSelected} />
                ) : (
                  <Plus size={15} aria-hidden="true" />
                )}
                {adoptableSelectedCount === selectedCount
                  ? copy.inUse.adoptSelected
                  : `${copy.inUse.adoptSelected} (${adoptableSelectedCount})`}
              </button>
            ) : null
          }
          destructive={{
            actionLabel: "Delete",
            confirmTitle: "Delete selected hooks?",
            confirmDescription: "This action cannot be undone.",
          }}
        />
      ) : null}
    </>
  );
}

function aggregateBulkHarnessState(values: readonly (boolean | null)[]): BulkHarnessState {
  if (values.length === 0) return "mixed";
  if (values.every((value) => value === true)) return "all";
  if (values.every((value) => value === false)) return "none";
  return "mixed";
}
