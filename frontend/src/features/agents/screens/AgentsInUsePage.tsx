import "../agents.css";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Plus, X } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import { ErrorBanner } from "../../../components/ErrorBanner";
import { FilterBar } from "../../../components/FilterBar";
import { HarnessFilterChip } from "../../../components/HarnessFilterChip";
import { LoadingSpinner } from "../../../components/LoadingSpinner";
import { PageHeader } from "../../../components/PageHeader";
import { useCommonCopy } from "../../../i18n";
import { useToast } from "../../../components/Toast";
import { AdoptConflictDialog } from "../components/AdoptConflictDialog";
import { AgentsMatrixView } from "../components/AgentsMatrixView";
import { CreateAgentDialog } from "../components/CreateAgentDialog";
import { AgentDetailModal } from "../components/detail/AgentDetailModal";
import { TagFilterBar } from "../../../components/tags/TagFilterBar";
import {
  agentsStatusCounts,
  extractAgentTagCounts,
  filterAgents,
  type AgentsStatusFilter,
} from "../model/selectors";
import { useAgentsController } from "../model/use-agents-controller";
import { useSetAgentTagsMutation } from "../api/queries";
import type { AgentAdoptConflict } from "../api/types";
import { SelectionMenu } from "../../../components/ui/SelectionMenu";

const STATUS_VALUES: AgentsStatusFilter[] = ["all", "enabled", "all-harnesses", "off", "untracked"];

function isAgentsStatusFilter(value: string | null): value is AgentsStatusFilter {
  return value !== null && STATUS_VALUES.includes(value as AgentsStatusFilter);
}

function statusLabel(status: AgentsStatusFilter): string {
  switch (status) {
    case "enabled":
      return "In use";
    case "all-harnesses":
      return "All harnesses";
    case "off":
      return "Off";
    case "untracked":
      return "Needs review";
    default:
      return "All agents";
  }
}

/** Unified Agents inventory. The status filter is URL-backed for deep links. */
export default function AgentsInUsePage() {
  const {
    status,
    inventory,
    isInitialLoading,
    queryErrorMessage,
    actionErrorMessage,
    clearActionError,
    pendingPerHarnessKeys,
    handleToggleHarness,
    adoptMutation,
    adoptAllMutation,
  } = useAgentsController();
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState("");
  const [selectedRefs, setSelectedRefs] = useState<ReadonlySet<string>>(() => new Set());
  const [adoptingSelected, setAdoptingSelected] = useState(false);
  const [pendingRef, setPendingRef] = useState<string | null>(null);
  const [conflict, setConflict] = useState<AgentAdoptConflict | null>(null);
  const [conflictPending, setConflictPending] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [detailRef, setDetailRef] = useState<string | null>(null);
  const common = useCommonCopy();
  const { toast } = useToast();
  const setTagsMutation = useSetAgentTagsMutation();

  const statusParam = searchParams.get("status");
  const statusFilter: AgentsStatusFilter = isAgentsStatusFilter(statusParam) ? statusParam : "all";
  const setStatusFilter = useCallback(
    (next: AgentsStatusFilter) => {
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
  const knownTags = useMemo(() => extractAgentTagCounts(inventory?.entries), [inventory?.entries]);
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
    async (ref: string) => {
      const entry = inventory?.entries.find((e) => e.ref === ref);
      if (!entry) return;
      const currentTags = entry.tags || [];
      const isStarred = currentTags.some((t) => t.toLowerCase() === "starred");
      const nextTags = isStarred
        ? currentTags.filter((t) => t.toLowerCase() !== "starred")
        : ["starred", ...currentTags.filter((t) => t.toLowerCase() !== "starred")];
      try {
        await setTagsMutation.mutateAsync({ ref, tags: nextTags });
      } catch (err) {
        toast(err instanceof Error ? err.message : "Failed to toggle star.");
      }
    },
    [inventory, setTagsMutation, toast],
  );

  const entries = useMemo(
    () => filterAgents(inventory, { search, status: statusFilter, harness: harnessParam, tags: selectedTags }),
    [inventory, search, statusFilter, harnessParam, selectedTags],
  );
  const counts = useMemo(() => agentsStatusCounts(inventory), [inventory]);
  const hasData = (inventory?.entries.length ?? 0) > 0;
  const totalManaged = inventory?.entries.filter((entry) => entry.kind === "managed").length ?? 0;
  const isReady = status === "success" && Boolean(inventory);
  const filtersActive = search !== "" || statusFilter !== "all" || harnessParam != null || selectedTags.length > 0;
  const isReviewView = statusFilter === "untracked";

  useEffect(() => {
    setSelectedRefs((current) => {
      const visibleUntracked = new Set(
        entries.filter((entry) => entry.kind === "unmanaged").map((entry) => entry.ref),
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

  const toggleSelected = useCallback((ref: string) => {
    setSelectedRefs((current) => {
      const next = new Set(current);
      if (next.has(ref)) next.delete(ref);
      else next.add(ref);
      return next;
    });
  }, []);

  const clearSelected = useCallback(() => setSelectedRefs(new Set()), []);

  const handleAdopt = useCallback(async (ref: string) => {
    setPendingRef(ref);
    setErrorMessage("");
    try {
      const result = await adoptMutation.mutateAsync({ ref });
      if (result && "conflict" in result) setConflict(result);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Could not adopt agent");
    } finally {
      setPendingRef(null);
    }
  }, [adoptMutation]);

  const handleAdoptSelected = useCallback(async () => {
    const refs = entries
      .filter((entry) => entry.kind === "unmanaged" && selectedRefs.has(entry.ref))
      .map((entry) => entry.ref);
    if (refs.length === 0) return;
    setAdoptingSelected(true);
    try {
      for (const ref of refs) {
        try {
          const result = await adoptMutation.mutateAsync({ ref });
          if (result && "conflict" in result) toast(`Skipped ${ref}: conflict`);
        } catch {
          toast(`Skipped ${ref}: adoption failed`);
        }
      }
      clearSelected();
    } finally {
      setAdoptingSelected(false);
    }
  }, [adoptMutation, clearSelected, entries, selectedRefs, toast]);

  const handleAdoptAll = useCallback(async () => {
    setAdoptingSelected(true);
    try {
      const result = await adoptAllMutation.mutateAsync();
      if (result.skipped.length > 0) {
        toast(`Skipped ${result.skipped.length} agents due to conflicts. Resolve them individually.`);
      } else {
        toast(`Adopted ${result.adopted.length} agents.`);
      }
      clearSelected();
    } finally {
      setAdoptingSelected(false);
    }
  }, [adoptAllMutation, clearSelected, toast]);

  const handleResolveConflict = useCallback(async (onConflict: "keep_store" | "replace_store") => {
    if (!conflict) return;
    setConflictPending(true);
    try {
      await adoptMutation.mutateAsync({ ref: conflict.slug, onConflict });
      setConflict(null);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Could not resolve conflict");
      setConflict(null);
    } finally {
      setConflictPending(false);
    }
  }, [adoptMutation, conflict]);

  const clearFilters = useCallback(() => {
    setSearch("");
    const params = new URLSearchParams(searchParams);
    params.delete("status");
    params.delete("harness");
    params.delete("tag");
    setSearchParams(params, { replace: true });
  }, [searchParams, setSearchParams]);

  const issueCount = inventory?.issues?.length ?? 0;
  const inventoryIssueMessage = issueCount
    ? `${issueCount} agent binding${issueCount === 1 ? "" : "s"} need${issueCount === 1 ? "s" : ""} attention. Use the "Needs review" filter to see them.`
    : "";
  const selectedCount = selectedRefs.size;
  const adoptableCount = entries.filter((entry) => entry.kind === "unmanaged" && entry.actions.canAdopt).length;

  return (
    <>
      <div className="page-chrome">
        <PageHeader
          title="Agents"
          subtitle={isReviewView
            ? "Agents found in your harness configs that harness-asset-manager does not yet track."
            : totalManaged > 0
              ? `Managing ${totalManaged} agent${totalManaged === 1 ? "" : "s"}`
              : "Browse, enable, and adopt agents across your harnesses."}
          actions={
            <>
              {isReviewView ? (
                <button
                  type="button"
                  className="action-pill action-pill--md action-pill--accent"
                  disabled={adoptingSelected || adoptableCount === 0}
                  onClick={() => void handleAdoptAll()}
                >
                  <Plus size={16} className="agent-icon-margin" />
                  Adopt all eligible
                </button>
              ) : (
                <button
                  type="button"
                  className="action-pill action-pill--md action-pill--accent"
                  onClick={() => setCreateDialogOpen(true)}
                >
                  <Plus size={16} className="agent-icon-margin" />
                  Add Agent
                </button>
              )}
            </>
          }
        />
        {hasData ? (
          <>
            <FilterBar
              searchPlaceholder="Search agents by name or description..."
              searchValue={search}
              onSearchChange={setSearch}
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
                    options={STATUS_VALUES.map((value) => ({
                      value,
                      label: statusLabel(value),
                      meta: counts[value],
                    }))}
                    active={statusFilter !== "all"}
                    ariaLabel={`Filter: ${statusLabel(statusFilter)}`}
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
      {errorMessage ? <ErrorBanner message={errorMessage} onDismiss={() => setErrorMessage("")} /> : null}
      {!isReviewView && inventoryIssueMessage ? <ErrorBanner message={inventoryIssueMessage} /> : null}

      {isReviewView && inventory?.issues?.length ? (
        <div className="agent-issues">
          <h3 className="agent-issues__title">Bindings that need attention</h3>
          <ul className="agent-issues__list">
            {inventory.issues.map((issue, index) => (
              <li key={`${issue.name}:${index}`} className="agent-issues__item">
                <span className="agent-issues__name">{issue.name}</span>
                <p className="agent-issues__reason">{issue.reason}</p>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {isReviewView && inventory?.recentRepairs?.length ? (
        <div className="agent-issues agent-repairs">
          <h3 className="agent-issues__title">Recent automatic repairs</h3>
          <ul className="agent-issues__list">
            {inventory.recentRepairs.slice(0, 10).map((repair, index) => (
              <li key={`${repair.ref}:${repair.harness}:${repair.at}:${index}`} className="agent-issues__item">
                <div className="agent-repairs__header">
                  <span className="agent-issues__name">
                    {repair.ref}{repair.harness ? ` (${repair.harness})` : ""}
                  </span>
                  <span className="agent-repairs__time">{new Date(repair.at * 1000).toLocaleString()}</span>
                </div>
                <p className="agent-repairs__reason">{repair.detail}</p>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {isInitialLoading ? (
        <div className="panel-state"><LoadingSpinner size="md" label="Loading agents" /></div>
      ) : status === "error" ? (
        <div className="panel-state">{queryErrorMessage || "Unable to load agents"}</div>
      ) : isReady && inventory ? (
        entries.length > 0 ? (
          <AgentsMatrixView
            entries={entries}
            columns={inventory.columns}
            pendingAgentKeys={new Set(pendingRef ? [pendingRef] : [])}
            pendingPerHarnessKeys={pendingPerHarnessKeys}
            checkedRefs={selectedRefs}
            onOpenDetail={setDetailRef}
            onToggleChecked={toggleSelected}
            onEnableHarness={(ref, harness) => void handleToggleHarness(ref, harness, false)}
            onDisableHarness={(ref, harness) => void handleToggleHarness(ref, harness, true)}
            onAdopt={(ref) => void handleAdopt(ref)}
            onToggleStar={handleToggleStar}
            starredFilterActive={starredFilterActive}
            onToggleStarredFilter={onToggleStarredFilter}
          />
        ) : hasData ? (
          <div className="empty-panel">
            <h3 className="empty-panel__title">{isReviewView ? "No agents need review" : common.status.noMatches}</h3>
            <p className="empty-panel__body">
              {isReviewView
                ? "Your harness configs only reference agents that harness-asset-manager already tracks."
                : "Adjust the search or filter to see other agents."}
            </p>
            <div className="empty-panel__actions">
              <button type="button" className="action-pill action-pill--md" onClick={clearFilters} disabled={!filtersActive}>
                {common.actions.clearFilters}
              </button>
            </div>
          </div>
        ) : (
          <div className="empty-panel">
            <h3 className="empty-panel__title">No agents found</h3>
            <p className="empty-panel__body">Create your first agent to get started.</p>
            <div className="empty-panel__actions">
              <button type="button" className="action-pill action-pill--md action-pill--accent" onClick={() => setCreateDialogOpen(true)}>
                Add Agent
              </button>
            </div>
          </div>
        )
      ) : null}

      <CreateAgentDialog open={createDialogOpen} onOpenChange={setCreateDialogOpen} />
      <AgentDetailModal
        open={Boolean(detailRef)}
        agentRef={detailRef}
        knownTags={knownTagNames}
        pendingPerHarnessKeys={pendingPerHarnessKeys}
        onToggleHarness={handleToggleHarness}
        onClose={() => setDetailRef(null)}
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
              {adoptingSelected ? <LoadingSpinner size="sm" label="Adopting selected agents..." /> : <Plus size={15} />}
              Adopt selected
            </button>
          </div>
        </div>
      ) : null}

      <AdoptConflictDialog
        open={conflict !== null}
        slug={conflict?.slug ?? ""}
        storePath={conflict?.storePath ?? ""}
        harnessPath={conflict?.harnessPath ?? ""}
        isPending={conflictPending}
        onOpenChange={(open) => {
          if (!open) setConflict(null);
        }}
        onConfirm={handleResolveConflict}
      />
    </>
  );
}
