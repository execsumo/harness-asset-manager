import { useCallback, useMemo, useState } from "react";
import { Plus } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import { ConfirmActionDialog } from "../../../components/ConfirmActionDialog";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { FilterBar } from "../../../components/FilterBar";
import { LoadingSpinner } from "../../../components/LoadingSpinner";
import { PageHeader } from "../../../components/PageHeader";
import { SelectionMenu } from "../../../components/ui/SelectionMenu";
import { useCommonCopy } from "../../../i18n";
import { usePermissionsCopy } from "../i18n";
import { PermissionsMatrixView } from "../components/PermissionsMatrixView";
import { PermissionDetailSheet } from "../components/detail/PermissionDetailSheet";
import { PermissionFormDialog } from "../components/edit/PermissionFormDialog";
import {
  filterPermissions,
  permissionsSummary,
  type PermissionsDecisionFilter,
  type PermissionsStatusFilter,
} from "../model/selectors";
import { usePermissionsManagementController } from "../model/use-permissions-management-controller";

const DETAIL_PARAM = "permission";



const STATUS_LABELS: Record<PermissionsStatusFilter, string> = {
  all: "All",
  applied: "Applied",
  "not-applied": "Not applied",
  differs: "Differs",
  untracked: "Untracked",
};

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
  } = usePermissionsManagementController();

  const [searchParams, setSearchParams] = useSearchParams();
  const selectedId = searchParams.get(DETAIL_PARAM);
  const [confirmUninstallId, setConfirmUninstallId] = useState<string | null>(null);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [addPending, setAddPending] = useState(false);

  const [search, setSearch] = useState("");
  const [decision, setDecision] = useState<PermissionsDecisionFilter>("all");
  const copy = usePermissionsCopy();
  const common = useCommonCopy();

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

  const entries = useMemo(
    () => filterPermissions(inventory, { search, decision: "deny", status: statusFilter }),
    [inventory, search, statusFilter],
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
  const filtersActive = search !== "" || statusFilter !== "all";

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
    setStatusFilter("all");
  }, []);

  return (
    <>
      <div className="page-chrome">
        <PageHeader
          title="Permissions"
          subtitle="Define denylist rules to restrict shell commands, file paths, and web domains across your harnesses."
          actions={
            <button
              type="button"
              className="action-pill action-pill--md action-pill--accent"
              onClick={() => setAddDialogOpen(true)}
            >
              <Plus size={16} style={{ marginRight: "4px" }} />
              Add Permission
            </button>
          }
        />
        {hasData ? (
          <FilterBar
            searchValue={search}
            onSearchChange={setSearch}
            searchPlaceholder="Search pattern or scope..."
            searchLabel="Search permissions"
            trailing={
              <SelectionMenu
                value={statusFilter}
                options={(Object.keys(STATUS_LABELS) as PermissionsStatusFilter[]).map((value) => ({
                  value,
                  label: STATUS_LABELS[value],
                  meta: statusCounts[value],
                }))}
                active={statusFilter !== "all"}
                ariaLabel={`Filter: ${STATUS_LABELS[statusFilter]}`}
                onChange={setStatusFilter}
              />
            }
          />
        ) : null}
      </div>

      {actionErrorMessage ? (
        <ErrorBanner message={actionErrorMessage} onDismiss={clearActionError} />
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
            onOpenDetail={setDetailId}
            onEnableHarness={(id, harness) => {
              void handleToggleHarness(id, harness, false);
            }}
            onDisableHarness={(id, harness) => {
              void handleToggleHarness(id, harness, true);
            }}
            onAdopt={(id) => {
              void handlePromotePermission(id);
            }}
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
    </>
  );
}
