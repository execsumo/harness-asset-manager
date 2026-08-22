import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus, X } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import { ConfirmActionDialog } from "../../../components/ConfirmActionDialog";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { FilterBar } from "../../../components/FilterBar";
import { LoadingSpinner } from "../../../components/LoadingSpinner";
import { PageHeader } from "../../../components/PageHeader";
import { useCommonCopy } from "../../../i18n";
import { HooksMatrixView } from "../components/HooksMatrixView";
import { HookDetailSheet } from "../components/detail/HookDetailSheet";
import { HookFormDialog } from "../components/edit/HookFormDialog";
import { HooksFilterMenu } from "../components/HooksFilterMenu";
import { useHooksCopy } from "../i18n";
import { filterHooks, hooksStatusCounts, type HooksStatusFilter } from "../model/selectors";
import { useHooksManagementController } from "../model/use-hooks-management-controller";

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

  const entries = useMemo(
    () => filterHooks(inventory, { search, status: statusFilter }),
    [inventory, search, statusFilter],
  );
  const counts = useMemo(() => hooksStatusCounts(inventory), [inventory]);
  const hasData = (inventory?.entries.length ?? 0) > 0;
  const isReady = status === "ready" && Boolean(inventory);
  const filtersActive = search !== "" || statusFilter !== "all";

  // Keep only currently visible, untracked rows selected as filters or inventory change.
  useEffect(() => {
    setSelectedIds((current) => {
      const visibleUntracked = new Set(
        entries.filter((entry) => entry.kind === "unmanaged").map((entry) => entry.id),
      );
      let changed = false;
      const next = new Set<string>();
      for (const id of current) {
        if (visibleUntracked.has(id)) next.add(id);
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
    setStatusFilter("all");
  }, [setStatusFilter]);

  const selectedCount = selectedIds.size;

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
          <FilterBar
            searchValue={search}
            onSearchChange={setSearch}
            searchPlaceholder={copy.inUse.searchPlaceholder}
            searchLabel={copy.inUse.searchLabel}
            trailing={
              <HooksFilterMenu
                pill={statusFilter}
                counts={counts}
                onChange={setStatusFilter}
              />
            }
          />
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
        <div className="bulk-dock">
          <div className="bulk-dock__fade" />
          <div className="bulk-bar" data-state="open" role="toolbar" aria-label={common.bulk.ariaLabel}>
            <div className="bulk-bar__group">
              <span className="bulk-bar__count">{common.bulk.selected(selectedCount)}</span>
              <button
                type="button"
                className="bulk-bar__clear"
                onClick={clearSelected}
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
              {adoptingSelected ? (
                <LoadingSpinner size="sm" label={copy.inUse.adoptingSelected} />
              ) : (
                <Plus size={15} aria-hidden="true" />
              )}
              {copy.inUse.adoptSelected}
            </button>
          </div>
        </div>
      ) : null}
    </>
  );
}
