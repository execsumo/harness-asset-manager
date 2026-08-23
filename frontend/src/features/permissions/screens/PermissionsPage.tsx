import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus, X } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import { BulkActionBar, type MultiSelectAction } from "../../../components/BulkActionBar";
import { ConfirmActionDialog } from "../../../components/ConfirmActionDialog";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { FilterBar } from "../../../components/FilterBar";
import { HarnessFilterChip } from "../../../components/HarnessFilterChip";
import { LoadingSpinner } from "../../../components/LoadingSpinner";
import { PageHeader } from "../../../components/PageHeader";
import { TagFilterBar } from "../../../components/tags/TagFilterBar";
import { SelectionMenu } from "../../../components/ui/SelectionMenu";
import { useCommonCopy } from "../../../i18n";
import { usePermissionsCopy } from "../i18n";
import { PermissionsMatrixView } from "../components/PermissionsMatrixView";
import { PermissionDetailSheet } from "../components/detail/PermissionDetailSheet";
import { PermissionFormDialog } from "../components/edit/PermissionFormDialog";
import {
  extractPermissionsTagCounts,
  filterPermissions,
  permissionsSummary,
  type PermissionsStatusFilter,
} from "../model/selectors";
import { usePermissionsManagementController } from "../model/use-permissions-management-controller";
import { useSetPermissionTagsMutation } from "../api/management-queries";

const DETAIL_PARAM = "permission";

function statusLabels(copy: ReturnType<typeof usePermissionsCopy>): Record<PermissionsStatusFilter, string> {
  return {
    all: copy.inUse.filters.all,
    applied: copy.inUse.filters.applied,
    "not-applied": copy.inUse.filters.notApplied,
    differs: copy.inUse.filters.differs,
    untracked: copy.inUse.filters.untracked,
  };
}

export default function PermissionsPage() {
  const {
    status,
    inventory,
    isInitialLoading,
    pendingPermissionKeys,
    pendingPerHarnessKeys,
    queryErrorMessage,
    actionErrorMessage,
    clearActionError,
    handleUninstallPermission,
    handleToggleHarness,
    handleReconcilePermission,
    handleCreatePermission,
    handlePromotePermission,
    handleSetPermissionHarnesses,
  } = usePermissionsManagementController();

  const [searchParams, setSearchParams] = useSearchParams();
  const selectedId = searchParams.get(DETAIL_PARAM);
  const [confirmUninstallId, setConfirmUninstallId] = useState<string | null>(null);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [addPending, setAddPending] = useState(false);
  const setTagsMutation = useSetPermissionTagsMutation();

  const [search, setSearch] = useState("");
  const [checkedIds, setCheckedIds] = useState<ReadonlySet<string>>(() => new Set());
  const [bulkPending, setBulkPending] = useState<MultiSelectAction | null>(null);
  const [adoptingSelected, setAdoptingSelected] = useState(false);
  const [bulkErrorMessage, setBulkErrorMessage] = useState("");
  const copy = usePermissionsCopy();
  const common = useCommonCopy();
  const STATUS_LABELS = statusLabels(copy);

  // Status filter lives in the URL so sidebar deep-links (?status=untracked) work.
  const statusParam = searchParams.get("status");
  const statusFilter: PermissionsStatusFilter =
    statusParam && statusParam in STATUS_LABELS
      ? (statusParam as PermissionsStatusFilter)
      : "all";
  const setStatusFilter = useCallback(
    (next: PermissionsStatusFilter) => {
      const params = new URLSearchParams(searchParams);
      if (next === "all") {
        params.delete("status");
      } else {
        params.set("status", next);
      }
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
    () => extractPermissionsTagCounts(inventory),
    [inventory],
  );

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
      const permEntry = inventory?.entries.find((e) => e.id === id);
      if (!permEntry) return;
      const currentTags = permEntry.tags || [];
      const isStarred = currentTags.some((t) => t.toLowerCase() === "starred");
      const nextTags = isStarred
        ? currentTags.filter((t) => t.toLowerCase() !== "starred")
        : ["starred", ...currentTags.filter((t) => t.toLowerCase() !== "starred")];
      await setTagsMutation.mutateAsync({ id, tags: nextTags });
    },
    [inventory, setTagsMutation],
  );

  const entries = useMemo(
    () => filterPermissions(inventory, { search, decision: "deny", status: statusFilter, harness: harnessParam, tags: selectedTags }),
    [inventory, search, statusFilter, harnessParam, selectedTags],
  );
  const summary = useMemo(() => permissionsSummary(inventory), [inventory]);
  const statusCounts = useMemo<Record<PermissionsStatusFilter, number>>(
    () => ({
      all: summary.total,
      applied: filterPermissions(inventory, { search: "", decision: "deny", status: "applied" }).length,
      "not-applied": filterPermissions(inventory, { search: "", decision: "deny", status: "not-applied" }).length,
      differs: summary.differs,
      untracked: summary.untracked,
    }),
    [inventory, summary],
  );

  const hasData = summary.total > 0;
  const isReady = status === "ready" && Boolean(inventory);
  const filtersActive = search !== "" || statusFilter !== "all" || harnessParam != null || selectedTags.length > 0;

  // Keep only currently visible rows selected as filters or inventory change.
  useEffect(() => {
    setCheckedIds((current) => {
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

  const toggleChecked = useCallback((id: string) => {
    setCheckedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const clearChecked = useCallback(() => setCheckedIds(new Set()), []);

  const runBulkAction = useCallback(
    async (action: MultiSelectAction, fn: (id: string) => Promise<unknown>): Promise<void> => {
      if (checkedIds.size === 0) return;
      const ids = Array.from(checkedIds);
      setBulkPending(action);
      try {
        const results = await Promise.allSettled(ids.map((id) => fn(id)));
        const failures = results
          .map((result, i) => ({ id: ids[i], result }))
          .filter((x) => x.result.status === "rejected");
        if (failures.length > 0) {
          const detail = failures
            .map((f) => {
              const reason = (f.result as PromiseRejectedResult).reason;
              return `${f.id}: ${reason instanceof Error ? reason.message : reason}`;
            })
            .join("; ");
          setBulkErrorMessage(detail);
        } else {
          setCheckedIds(new Set());
        }
      } finally {
        setBulkPending(null);
      }
    },
    [checkedIds],
  );

  const handleBulkEnableAll = useCallback(
    () => runBulkAction("enable-all", (id) => handleSetPermissionHarnesses(id, "enabled")),
    [handleSetPermissionHarnesses, runBulkAction],
  );

  const handleBulkDisableAll = useCallback(
    () => runBulkAction("disable-all", (id) => handleSetPermissionHarnesses(id, "disabled")),
    [handleSetPermissionHarnesses, runBulkAction],
  );

  const handleBulkDelete = useCallback(
    () => runBulkAction("delete", (id) => handleUninstallPermission(id)),
    [handleUninstallPermission, runBulkAction],
  );

  const selectedManagedCount = useMemo(
    () => entries.filter((entry) => entry.kind === "managed" && checkedIds.has(entry.id)).length,
    [checkedIds, entries],
  );
  const selectedUntrackedCount = useMemo(
    () => entries.filter((entry) => entry.kind === "unmanaged" && checkedIds.has(entry.id)).length,
    [checkedIds, entries],
  );

  const handleAdoptSelected = useCallback(async () => {
    const ids = entries
      .filter((entry) => entry.kind === "unmanaged" && checkedIds.has(entry.id))
      .map((entry) => entry.id);
    if (ids.length === 0) return;
    setAdoptingSelected(true);
    try {
      for (const id of ids) await handlePromotePermission(id);
      clearChecked();
    } finally {
      setAdoptingSelected(false);
    }
  }, [checkedIds, clearChecked, entries, handlePromotePermission]);

  const setDetailId = useCallback(
    (id: string | null) => {
      const next = new URLSearchParams(searchParams);
      if (id) {
        next.set(DETAIL_PARAM, id);
      } else {
        next.delete(DETAIL_PARAM);
      }
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

  const isPermissionPendingSelected = selectedId !== null && pendingPermissionKeys.has(selectedId);

  const handleCreatePermissionSubmit = async (value: {
    id: string;
    decision: string;
    scope: string;
    pattern: string | null;
    description: string;
  }) => {
    setAddPending(true);
    try {
      await handleCreatePermission(value);
      setAddDialogOpen(false);
    } finally {
      setAddPending(false);
    }
  };

  const executeUninstall = useCallback(async () => {
    const target = confirmUninstallId;
    if (!target) return;
    setConfirmUninstallId(null);
    await handleUninstallPermission(target);
    if (selectedId === target) {
      setDetailId(null);
    }
  }, [confirmUninstallId, handleUninstallPermission, selectedId, setDetailId]);

  const clearFilters = useCallback(() => {
    setSearch("");
    const params = new URLSearchParams(searchParams);
    params.delete("status");
    params.delete("harness");
    params.delete("tag");
    setSearchParams(params, { replace: true });
  }, [searchParams, setSearchParams]);

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
              Add Permission
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
                  {harnessParam ? (
                    <HarnessFilterChip
                      label={inventory?.columns.find((column) => column.harness === harnessParam)?.label ?? harnessParam}
                      onClear={clearHarnessFilter}
                    />
                  ) : null}
                  <SelectionMenu
                  value={statusFilter}
                  options={(Object.keys(STATUS_LABELS) as PermissionsStatusFilter[]).map((value) => ({
                    value,
                    label: STATUS_LABELS[value],
                    meta: statusCounts[value],
                  }))}
                  active={statusFilter !== "all"}
                  ariaLabel={copy.inUse.filters.aria(STATUS_LABELS[statusFilter])}
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

      {actionErrorMessage ? (
        <ErrorBanner message={actionErrorMessage} onDismiss={clearActionError} />
      ) : null}
      {bulkErrorMessage ? (
        <ErrorBanner message={bulkErrorMessage} onDismiss={() => setBulkErrorMessage("")} />
      ) : null}

      {isInitialLoading ? (
        <div className="panel-state">
          <LoadingSpinner size="md" label={copy.inUse.loading} />
        </div>
      ) : status === "error" ? (
        <div className="panel-state">{queryErrorMessage || copy.inUse.unableToLoad}</div>
      ) : isReady && inventory ? (
        entries.length > 0 ? (
          <PermissionsMatrixView
            entries={entries}
            columns={inventory.columns}
            pendingPermissionKeys={pendingPermissionKeys}
            pendingPerHarnessKeys={pendingPerHarnessKeys}
            checkedIds={checkedIds}
            onOpenDetail={setDetailId}
            onToggleChecked={toggleChecked}
            onEnableHarness={(id, harness) => {
              void handleToggleHarness(id, harness, false);
            }}
            onDisableHarness={(id, harness) => {
              void handleToggleHarness(id, harness, true);
            }}
            onAdopt={(id) => {
              void handlePromotePermission(id);
            }}
            onToggleStar={handleToggleStar}
            starredFilterActive={starredFilterActive}
            onToggleStarredFilter={onToggleStarredFilter}
          />
        ) : hasData ? (
          <div className="empty-panel">
            <h3 className="empty-panel__title">{common.status.noMatches}</h3>
            <p className="empty-panel__body">{copy.inUse.noMatchesBody}</p>
            <div className="empty-panel__actions">
              <button type="button" className="action-pill action-pill--md" onClick={clearFilters} disabled={!filtersActive}>
                {common.actions.clearFilters}
              </button>
            </div>
          </div>
        ) : (
          <div className="empty-panel">
            <h3 className="empty-panel__title">{copy.inUse.emptyTitle}</h3>
            <p className="empty-panel__body">{copy.inUse.emptyBody}</p>
            <div className="empty-panel__actions">
              <button
                type="button"
                className="action-pill action-pill--md action-pill--accent"
                onClick={() => setAddDialogOpen(true)}
              >
                Add Permission
              </button>
            </div>
          </div>
        )
      ) : null}

      {inventory ? (
        <PermissionDetailSheet
          id={selectedId}
          columns={inventory.columns}
          pendingPerHarness={pendingForSelected}
          isServerPending={isPermissionPendingSelected}
          isUninstalling={isPermissionPendingSelected}
          onClose={() => setDetailId(null)}
          onEnableHarness={(harness) => {
            if (selectedId) void handleToggleHarness(selectedId, harness, false);
          }}
          onDisableHarness={(harness) => {
            if (selectedId) void handleToggleHarness(selectedId, harness, true);
          }}
          onResolveConfig={(args) => {
            if (!selectedId) return Promise.resolve();
            return handleReconcilePermission({ id: selectedId, ...args });
          }}
          onUninstall={() => {
            if (selectedId) setConfirmUninstallId(selectedId);
          }}
        />
      ) : null}

      <PermissionFormDialog
        open={addDialogOpen}
        pending={addPending}
        onOpenChange={setAddDialogOpen}
        onSubmit={handleCreatePermissionSubmit}
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

      {selectedManagedCount > 0 ? (
        <BulkActionBar
          selectedCount={selectedManagedCount}
          pending={bulkPending}
          onClear={clearChecked}
          onEnableAll={handleBulkEnableAll}
          onDisableAll={handleBulkDisableAll}
          onDelete={handleBulkDelete}
          destructive={{
            actionLabel: copy.inUse.uninstall.action,
            confirmTitle: copy.inUse.uninstall.bulkTitle(selectedManagedCount),
            confirmDescription: copy.inUse.uninstall.singleDescription,
          }}
        />
      ) : null}

      {selectedUntrackedCount > 0 ? (
        <div className="bulk-dock">
          <div className="bulk-dock__fade" />
          <div className="bulk-bar" data-state="open" role="toolbar" aria-label={common.bulk.ariaLabel}>
            <div className="bulk-bar__group">
              <span className="bulk-bar__count">{common.bulk.selected(selectedUntrackedCount)}</span>
              <button
                type="button"
                className="bulk-bar__clear"
                onClick={clearChecked}
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
