import { useMemo } from "react";
import { Link } from "react-router-dom";
import { Loader2 } from "lucide-react";

import { FilterBar } from "../../../components/FilterBar";
import { LoadingSpinner } from "../../../components/LoadingSpinner";
import { PageHeader } from "../../../components/PageHeader";
import {
  MatrixHarnessCellTarget,
  MatrixHarnessHeader,
  MatrixHarnessIcon,
  MatrixTable,
} from "../../../components/matrix";
import { UiTooltip } from "../../../components/ui/UiTooltip";
import { useCommonCopy } from "../../../i18n";
import { SkillsEmptyState } from "../components/pane/SkillsEmptyState";
import { useSkillsCopy } from "../i18n";
import { useSkillsWorkspace } from "../model/workspace-context";
import {
  countAdoptableLocalSkillRows,
  countNeedsReviewRows,
  filterNeedsReviewRows,
  hasActiveNeedsReviewFilters,
} from "../model/selectors";
import { useSkillsNeedsReviewSession } from "../model/session";

export default function SkillsNeedsReviewPage() {
  const {
    data,
    status,
    pendingStructuralActions,
    pendingBulkAction,
    onManageAll,
    onManageSkill,
    onOpenSkill,
    isInitialLoading,
  } = useSkillsWorkspace();
  const { filters, updateFilters, resetFilters } = useSkillsNeedsReviewSession();
  const copy = useSkillsCopy();
  const common = useCommonCopy();

  const rows = useMemo(() => filterNeedsReviewRows(data, filters), [data, filters]);
  const hasActiveFilters = useMemo(() => hasActiveNeedsReviewFilters(filters), [filters]);
  const needsReviewCount = useMemo(() => countNeedsReviewRows(data), [data]);
  const adoptableCount = useMemo(() => countAdoptableLocalSkillRows(data), [data]);
  const isReady = status === "ready" && Boolean(data);
  const harnessColumns = data?.harnessColumns ?? [];

  return (
    <>
      <div className="page-chrome">
        <PageHeader
          title={copy.review.title}
          subtitle={copy.review.subtitle(needsReviewCount)}
          actions={
            <button
              type="button"
              className="action-pill action-pill--md action-pill--accent"
              disabled={pendingBulkAction !== null || adoptableCount === 0}
              onClick={onManageAll}
            >
              {pendingBulkAction === "manage-all" ? (
                <LoadingSpinner size="sm" label={copy.review.adoptingAllSkills} />
              ) : null}
              {copy.review.adoptAllEligible}
            </button>
          }
        />

        {needsReviewCount > 0 ? (
          <FilterBar
            searchValue={filters.search}
            onSearchChange={(search) => updateFilters({ search })}
            searchPlaceholder={copy.review.searchPlaceholder}
            searchLabel={copy.review.searchLabel}
          />
        ) : null}
      </div>

      {isInitialLoading ? (
        <div className="panel-state">
          <LoadingSpinner size="md" label={copy.review.loading} />
        </div>
      ) : status === "error" ? (
        <div className="panel-state">{copy.review.unableToLoad}</div>
      ) : isReady && data ? (
        rows.length > 0 ? (
          <MatrixTable
            ariaLabel="Skills to adopt"
            harnessColumnCount={harnessColumns.length}
            harnessColumnWidth="52px"
            compactColumnWidth="140px"
            coverageColumnWidth="120px"
          >
            <thead className="matrix-table__head">
              <tr>
                <th className="matrix-table__th matrix-table__th--identity">Skill</th>
                {harnessColumns.map((column) => (
                  <MatrixHarnessHeader
                    key={column.harness}
                    label={column.label}
                    logoKey={column.logoKey}
                    harness={column.harness}
                  />
                ))}
                <th className="matrix-table__th matrix-table__th--end">Action</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const managing = pendingStructuralActions.get(row.skillRef) === "manage";
                const actionDisabled =
                  pendingBulkAction !== null ||
                  pendingStructuralActions.get(row.skillRef) != null ||
                  !row.actions.canManage;
                return (
                  <tr key={row.skillRef} className="matrix-table__row">
                    <td className="matrix-table__cell matrix-table__cell--identity">
                      <button
                        type="button"
                        className="mcp-matrix__server-button"
                        aria-label={`Open ${row.name}`}
                        onClick={() => onOpenSkill(row.skillRef)}
                      >
                        <span className="matrix-table__name-row">
                          <span className="matrix-table__name-text">{row.name}</span>
                        </span>
                        {row.description ? (
                          <span className="matrix-table__description">{row.description}</span>
                        ) : null}
                      </button>
                    </td>
                    {harnessColumns.map((column) => {
                      const discovered = row.cells.some(
                        (cell) => cell.harness === column.harness && cell.state === "found",
                      );
                      return (
                        <td
                          key={column.harness}
                          className="matrix-table__cell matrix-table__cell--harness"
                        >
                          <UiTooltip
                            content={
                              discovered
                                ? `Found in ${column.label} config`
                                : `Not found in ${column.label}`
                            }
                          >
                            <MatrixHarnessCellTarget
                              state={discovered ? "observed" : "empty"}
                              ariaLabel={
                                discovered
                                  ? `Discovered in ${column.label}`
                                  : `Not found in ${column.label}`
                              }
                              disabled
                            >
                              {discovered ? (
                                <MatrixHarnessIcon
                                  label={column.label}
                                  logoKey={column.logoKey}
                                  harness={column.harness}
                                />
                              ) : (
                                "—"
                              )}
                            </MatrixHarnessCellTarget>
                          </UiTooltip>
                        </td>
                      );
                    })}
                    <td className="matrix-table__cell matrix-table__cell--end">
                      <button
                        type="button"
                        className="action-pill action-pill--accent"
                        disabled={actionDisabled}
                        title={
                          row.actions.canManage
                            ? "Add this skill to Skill Manager"
                            : "This skill cannot be adopted automatically"
                        }
                        onClick={() => void onManageSkill(row.skillRef)}
                      >
                        {managing ? (
                          <Loader2 size={12} className="card-action-spinner" aria-hidden="true" />
                        ) : null}
                        Adopt
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </MatrixTable>
        ) : needsReviewCount > 0 ? (
          <SkillsEmptyState copy={copy.filters} onResetFilters={resetFilters} />
        ) : (
          <div className="empty-panel">
            <h3 className="empty-panel__title">{copy.review.emptyTitle}</h3>
            <p className="empty-panel__body">
              {copy.review.emptyBody}
            </p>
            <div className="empty-panel__actions">
              <Link
                to="/marketplace/skills"
                className="action-pill action-pill--md action-pill--accent"
              >
                {common.actions.openMarketplace}
              </Link>
            </div>
          </div>
        )
      ) : null}

      {hasActiveFilters && rows.length === 0 ? null : null}
    </>
  );
}
