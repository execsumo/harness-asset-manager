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
import { TagFilterBar } from "../../../components/tags/TagFilterBar";
import { useCommonCopy } from "../../../i18n";
import { SlashCommandFormDialog } from "../components/SlashCommandFormDialog";
import { SlashCommandMatrix } from "../components/SlashCommandMatrix";
import { SlashCommandDetailSheet } from "../components/detail/SlashCommandDetailSheet";
import { SlashCommandReviewDetailSheet } from "../components/detail/SlashCommandReviewDetailSheet";
import { useSlashCommandsCopy } from "../i18n";
import {
  extractSlashCommandTagCounts,
  filterSlashCommandEntries,
  primaryReviewAction,
  slashCommandStatusCounts,
  type SlashCommandsStatusFilter,
} from "../model/selectors";
import { useSlashCommandsController } from "../model/useSlashCommandsController";
import { useSetSlashCommandTagsMutation } from "../api/queries";

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
  const setTagsMutation = useSetSlashCommandTagsMutation();

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

  // URL-backed tag filters (?tag=)
  const selectedTags = useMemo(() => searchParams.getAll("tag"), [searchParams]);
  const knownTags = useMemo(
    () => extractSlashCommandTagCounts(controller.data?.commands),
    [controller.data?.commands],
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
    async (name: string) => {
      const cmd = controller.data?.commands.find((c) => c.name === name);
      const reviewCmd = !cmd ? controller.data?.reviewCommands.find((r) => r.reviewRef === name || r.name === name) : null;
      if (!cmd && !reviewCmd) return;
      const currentTags = cmd?.tags || reviewCmd?.tags || [];
      const isStarred = currentTags.some((t) => t.toLowerCase() === "starred");
      const nextTags = isStarred
        ? currentTags.filter((t) => t.toLowerCase() !== "starred")
        : ["starred", ...currentTags.filter((t) => t.toLowerCase() !== "starred")];
      try {
        await setTagsMutation.mutateAsync({ name, tags: nextTags });
      } catch (err) {
        controller.setActionError(err instanceof Error ? err.message : "Failed to toggle star.");
      }
    },
    [controller, setTagsMutation],
  );

  const entries = useMemo(
    () => filterSlashCommandEntries(controller.entries, search, statusFilter, harnessParam, selectedTags),
    [controller.entries, search, statusFilter, harnessParam, selectedTags],
  );
  const counts = useMemo(() => slashCommandStatusCounts(controller.entries), [controller.entries]);
  const hasData = controller.entries.length > 0;
  const filtersActive = search !== "" || statusFilter !== "all" || harnessParam != null || selectedTags.length > 0;

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
    const params = new URLSearchParams(searchParams);
    params.delete("status");
    params.delete("harness");
    params.delete("tag");
    setSearchParams(params, { replace: true });
  }, [searchParams, setSearchParams]);

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
          <>
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
            <TagFilterBar
              tags={knownTags}
              selectedTags={selectedTags}
              onToggleTag={toggleTagFilter}
              onClearTags={clearTagFilters}
            />
          </>
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
          onToggleStar={handleToggleStar}
          starredFilterActive={starredFilterActive}
          onToggleStarredFilter={onToggleStarredFilter}
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
          knownTags={knownTagNames}
          targets={controller.data.targets}
          pendingName={controller.pendingName}
          pendingTarget={controller.pendingTarget}
          onClose={controller.closeDetail}
          onDelete={controller.setDeleteCommand}
          onToggleTarget={(command, target) => void controller.handleToggleTarget(command, target)}
        />
      ) : null}

      {controller.data ? (
        <SlashCommandReviewDetailSheet
          row={controller.selectedReviewRow}
          canonicalCommand={controller.selectedCanonicalCommand}
          knownTags={knownTagNames}
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
