import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus, X } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import { ConfirmActionDialog } from "../../../components/ConfirmActionDialog";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { FilterBar } from "../../../components/FilterBar";
import { HarnessFilterChip } from "../../../components/HarnessFilterChip";
import { LoadingSpinner } from "../../../components/LoadingSpinner";
import { PageHeader } from "../../../components/PageHeader";
import { SelectionMenu } from "../../../components/ui/SelectionMenu";
import { useCommonCopy } from "../../../i18n";
import { SlashCommandFormDialog } from "../components/SlashCommandFormDialog";
import { SlashCommandMatrix } from "../components/SlashCommandMatrix";
import { SlashCommandDetailSheet } from "../components/detail/SlashCommandDetailSheet";
import { SlashCommandReviewDetailSheet } from "../components/detail/SlashCommandReviewDetailSheet";
import { useSlashCommandsCopy } from "../i18n";
import {
  filterSlashCommandEntries,
  primaryReviewAction,
  slashCommandStatusCounts,
  type SlashCommandsStatusFilter,
} from "../model/selectors";
import { useSlashCommandsController } from "../model/useSlashCommandsController";

const STATUS_LABELS: Record<SlashCommandsStatusFilter, string> = {
  all: "All",
  untracked: "Untracked",
};

export default function SlashCommandsPage() {
  const controller = useSlashCommandsController();
  const copy = useSlashCommandsCopy();
  const common = useCommonCopy();
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState("");
  const [selectedRefs, setSelectedRefs] = useState<ReadonlySet<string>>(() => new Set());
  const [adoptingSelected, setAdoptingSelected] = useState(false);
  const [addDialogOpen, setAddDialogOpen] = useState(false);

  const statusParam = searchParams.get("status");
  const statusFilter: SlashCommandsStatusFilter = statusParam === "untracked" ? "untracked" : "all";
  const setStatusFilter = useCallback(
    (next: SlashCommandsStatusFilter) => {
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

  const entries = useMemo(
    () => filterSlashCommandEntries(controller.entries, search, statusFilter, harnessParam),
    [controller.entries, search, statusFilter, harnessParam],
  );
  const counts = useMemo(() => slashCommandStatusCounts(controller.entries), [controller.entries]);
  const hasData = controller.entries.length > 0;
  const filtersActive = search !== "" || statusFilter !== "all" || harnessParam != null;

  useEffect(() => {
    setSelectedRefs((current) => {
      const visibleUntracked = new Set(
        entries.filter((entry) => entry.kind === "unmanaged").map((entry) => entry.id),
      );
      let changed = false;
      const next = new Set<string>();
      for (const ref of current) {
        if (visibleUntracked.has(ref)) next.add(ref);
        else changed = true;
      }
      return changed ? next : current;
    });
  }, [entries]);

  const clearFilters = useCallback(() => {
    setSearch("");
    setStatusFilter("all");
    clearHarnessFilter();
  }, [clearHarnessFilter, setStatusFilter]);

  const handleAdoptSelected = useCallback(async () => {
    const selectedRows = entries.flatMap((entry) => {
      if (entry.kind === "unmanaged" && selectedRefs.has(entry.id) && primaryReviewAction(entry.review) === "import") {
        return [entry.review];
      }
      return [];
    });
    if (selectedRows.length === 0) return;
    setAdoptingSelected(true);
    try {
      for (const row of selectedRows) await controller.handleReviewAction(row, "import");
      setSelectedRefs(new Set());
    } finally {
      setAdoptingSelected(false);
    }
  }, [controller, entries, selectedRefs]);

  const selectedCount = selectedRefs.size;
  const title = statusFilter === "untracked" ? copy.review.title : copy.inUse.title;
  const subtitle = statusFilter === "untracked" ? copy.review.subtitle(counts.untracked) : copy.inUse.subtitle;

  return (
    <>
      <div className="page-chrome">
        <PageHeader
          title={title}
          subtitle={subtitle}
          actions={
            <button type="button" className="action-pill action-pill--md" onClick={() => setAddDialogOpen(true)}>
              <Plus size={14} aria-hidden="true" />
              {copy.inUse.newCommand}
            </button>
          }
        />
        {hasData ? (
          <FilterBar
            searchValue={search}
            onSearchChange={setSearch}
            searchPlaceholder={statusFilter === "untracked" ? copy.review.searchPlaceholder : copy.inUse.searchPlaceholder}
            searchLabel={statusFilter === "untracked" ? copy.review.searchLabel : copy.inUse.searchLabel}
            trailing={
              <>
                {harnessParam ? (
                  <HarnessFilterChip label={harnessParam} onClear={clearHarnessFilter} />
                ) : null}
                <SelectionMenu
                  value={statusFilter}
                  options={(Object.keys(STATUS_LABELS) as SlashCommandsStatusFilter[]).map((value) => ({
                    value,
                    label: STATUS_LABELS[value],
                    meta: counts[value],
                  }))}
                  active={statusFilter !== "all"}
                  ariaLabel={`Filter: ${STATUS_LABELS[statusFilter]}`}
                  onChange={setStatusFilter}
                />
              </>
            }
          />
        ) : null}
      </div>

      {controller.actionError ? <ErrorBanner message={controller.actionError} onDismiss={() => controller.setActionError("")} /> : null}
      {controller.query.error ? <ErrorBanner message={controller.query.error instanceof Error ? controller.query.error.message : copy.inUse.unableToLoad} /> : null}

      {controller.query.isPending ? (
        <div className="panel-state"><LoadingSpinner label={statusFilter === "untracked" ? copy.review.loading : copy.inUse.loading} /></div>
      ) : entries.length > 0 ? (
        <SlashCommandMatrix
          entries={entries}
          targets={controller.data?.targets ?? []}
          pendingName={controller.pendingName}
          pendingTarget={controller.pendingTarget}
          pendingReviewKey={controller.pendingReviewKey}
          checkedRefs={selectedRefs}
          onOpenManaged={controller.openDetail}
          onOpenReview={controller.openReviewDetail}
          onToggleChecked={(ref) => {
            setSelectedRefs((current) => {
              const next = new Set(current);
              if (next.has(ref)) next.delete(ref);
              else next.add(ref);
              return next;
            });
          }}
          onToggleTarget={(command, target) => void controller.handleToggleTarget(command, target)}
          onReviewAction={(row) => void controller.handleReviewAction(row)}
        />
      ) : hasData ? (
        <div className="empty-panel">
          <h3 className="empty-panel__title">{statusFilter === "untracked" ? copy.review.emptyTitle : common.status.noMatches}</h3>
          <p className="empty-panel__body">{statusFilter === "untracked" ? copy.review.emptyBody : copy.inUse.unableToLoad}</p>
          <div className="empty-panel__actions">
            <button type="button" className="action-pill action-pill--md" onClick={clearFilters} disabled={!filtersActive}>
              {common.actions.clearFilters}
            </button>
          </div>
        </div>
      ) : (
        <div className="empty-panel">
          <h3 className="empty-panel__title">No slash commands yet</h3>
          <p className="empty-panel__body">{copy.inUse.subtitle}</p>
          <div className="empty-panel__actions">
            <button type="button" className="action-pill action-pill--md action-pill--accent" onClick={() => setAddDialogOpen(true)}>
              {copy.inUse.newCommand}
            </button>
          </div>
        </div>
      )}

      {controller.data ? (
        <SlashCommandDetailSheet
          command={controller.selectedCommand}
          targets={controller.data.targets}
          pendingName={controller.pendingName}
          pendingTarget={controller.pendingTarget}
          onClose={controller.closeDetail}
          onEdit={controller.openEdit}
          onDelete={controller.setDeleteCommand}
          onToggleTarget={(command, target) => void controller.handleToggleTarget(command, target)}
        />
      ) : null}

      {controller.data ? (
        <SlashCommandReviewDetailSheet
          row={controller.selectedReviewRow}
          canonicalCommand={controller.selectedCanonicalCommand}
          targets={controller.data.targets}
          pendingKey={controller.pendingReviewKey}
          actionError={controller.actionError}
          onClose={controller.closeReviewDetail}
          onAction={controller.handleReviewAction}
        />
      ) : null}

      {controller.data ? (
        <SlashCommandFormDialog
          open={controller.formMode !== null || addDialogOpen}
          mode={controller.formMode ?? "create"}
          command={controller.editingCommand}
          targets={controller.data.targets}
          defaultTargets={controller.data.defaultTargets}
          pending={controller.formPending}
          onOpenChange={(open) => {
            setAddDialogOpen(open);
            if (!open) controller.setFormMode(null);
          }}
          onSubmit={controller.handleSubmit}
        />
      ) : null}

      {selectedCount > 0 ? (
        <div className="bulk-dock">
          <div className="bulk-dock__fade" />
          <div className="bulk-bar" data-state="open" role="toolbar" aria-label="Bulk actions">
            <div className="bulk-bar__group">
              <span className="bulk-bar__count">{selectedCount} selected</span>
              <button type="button" className="bulk-bar__clear" onClick={() => setSelectedRefs(new Set())} disabled={adoptingSelected} aria-label="Clear selection">
                <X size={14} />
              </button>
            </div>
            <span className="bulk-bar__divider" aria-hidden="true" />
            <button type="button" className="bulk-bar__action" onClick={() => void handleAdoptSelected()} disabled={adoptingSelected}>
              {adoptingSelected ? <LoadingSpinner size="sm" label="Adopting selected commands..." /> : <Plus size={15} />}
              Adopt selected
            </button>
          </div>
        </div>
      ) : null}

      <ConfirmActionDialog
        open={controller.deleteCommand !== null}
        title={copy.inUse.deleteTitle(controller.deleteCommand?.name ?? "slash command")}
        description={copy.inUse.deleteDescription}
        confirmLabel={common.actions.delete}
        pendingLabel={copy.inUse.deleting}
        isPending={controller.deletePending}
        onOpenChange={(open) => {
          if (!open) controller.setDeleteCommand(null);
        }}
        onConfirm={controller.executeDeleteCommand}
      />
    </>
  );
}
