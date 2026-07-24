import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Loader2 } from "lucide-react";

import { ErrorBanner } from "../../../components/ErrorBanner";
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
import { permissionsRoutes } from "../public";
import {
  usePermissionsInventoryQuery,
  usePromotePermissionMutation,
} from "../api/management-queries";
import { filterPermissionsNeedsReview } from "../model/selectors";
import { PermissionsStatusChip } from "../components/PermissionsStatusChip";

export default function PermissionsNeedsReviewPage() {
  const inventoryQuery = usePermissionsInventoryQuery();
  const promoteMutation = usePromotePermissionMutation();

  const [search, setSearch] = useState("");
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState("");

  const inventory = inventoryQuery.data ?? null;
  const entries = useMemo(() => filterPermissionsNeedsReview(inventory, search), [inventory, search]);
  const totalReview = useMemo(() => filterPermissionsNeedsReview(inventory, "").length, [inventory]);
  const columns = inventory?.columns ?? [];

  const isInitialLoading = inventoryQuery.isPending && !inventory;
  const loadError = inventoryQuery.error instanceof Error ? inventoryQuery.error.message : "";

  const handlePromote = async (id: string) => {
    setPendingId(id);
    setErrorMessage("");
    try {
      await promoteMutation.mutateAsync({ id });
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Could not promote permission");
    } finally {
      setPendingId(null);
    }
  };

  return (
    <>
      <div className="page-chrome">
        <PageHeader
          title="Permissions to review"
          subtitle="Permission rules found in your harness configs that skill-manager does not yet track. Promote the ones you want to manage globally."
        />
        {totalReview > 0 ? (
          <FilterBar
            searchValue={search}
            onSearchChange={setSearch}
            searchPlaceholder="Search by decision, scope or pattern..."
            searchLabel="Search permissions to review"
          />
        ) : null}
      </div>

      {errorMessage ? <ErrorBanner message={errorMessage} onDismiss={() => setErrorMessage("")} /> : null}

      {isInitialLoading ? (
        <div className="panel-state">
          <LoadingSpinner size="md" label="Loading permissions" />
        </div>
      ) : loadError ? (
        <div className="panel-state">{loadError}</div>
      ) : totalReview === 0 ? (
        <div className="empty-panel">
          <h3 className="empty-panel__title">No permissions need review</h3>
          <p className="empty-panel__body">
            Your harness configs only reference permissions that skill-manager already tracks.
          </p>
          <div className="empty-panel__actions">
            <Link to={permissionsRoutes.inUse} className="action-pill action-pill--md action-pill--accent">
              View Permissions in Use
            </Link>
          </div>
        </div>
      ) : entries.length === 0 ? (
        <div className="empty-panel">
          <h3 className="empty-panel__title">No matches</h3>
          <p className="empty-panel__body">Adjust the search to see other permissions.</p>
          <div className="empty-panel__actions">
            <button type="button" className="action-pill action-pill--md" onClick={() => setSearch("")}>
              Clear search
            </button>
          </div>
        </div>
      ) : (
        <MatrixTable
          ariaLabel="Permissions to review"
          harnessColumnCount={columns.length}
          harnessColumnWidth="52px"
          compactColumnWidth="140px"
          coverageColumnWidth="120px"
        >
          <thead className="matrix-table__head">
            <tr>
              <th className="matrix-table__th matrix-table__th--identity">Permission ID</th>
              {columns.map((column) => (
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
            {entries.map((entry) => {
              const pending = pendingId === entry.id;
              return (
                <tr key={entry.id} className="matrix-table__row">
                  <td className="matrix-table__cell matrix-table__cell--identity">
                    <div className="mcp-matrix__server-button" style={{ cursor: "default" }}>
                      <span className="matrix-table__name-row">
                        <span className="matrix-table__name-text">{entry.displayName}</span>
                        {entry.spec && (
                          <PermissionsStatusChip decision={entry.spec.decision} scope={entry.spec.scope} />
                        )}
                      </span>
                      <span className="matrix-table__description">
                        <code>{entry.spec?.pattern ?? "—"}</code>
                      </span>
                    </div>
                  </td>
                  {columns.map((column) => {
                    const discovered = entry.sightings.some(
                      (b) => b.harness === column.harness && b.state === "unmanaged",
                    );
                    return (
                      <td key={column.harness} className="matrix-table__cell matrix-table__cell--harness">
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
                      disabled={pending}
                      onClick={() => void handlePromote(entry.id)}
                    >
                      {pending ? (
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
      )}
    </>
  );
}
