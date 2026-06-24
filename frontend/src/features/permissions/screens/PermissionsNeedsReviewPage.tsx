import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Loader2 } from "lucide-react";

import { ErrorBanner } from "../../../components/ErrorBanner";
import { FilterBar } from "../../../components/FilterBar";
import { LoadingSpinner } from "../../../components/LoadingSpinner";
import { PageHeader } from "../../../components/PageHeader";
import { getHarnessPresentation } from "../../../components/harness/harnessPresentation";
import { OverflowTooltipText } from "../../../components/ui/OverflowTooltipText";
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
  const labelByHarness = useMemo(() => new Map(columns.map((c) => [c.harness, c.label])), [columns]);
  const logoByHarness = useMemo(
    () => new Map(columns.map((c) => [c.harness, c.logoKey ?? c.harness])),
    [columns],
  );

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
          subtitle="Permission rules found in your harness configs that skill-manager does not yet track. Adopt the ones you want to manage centrally."
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
        <div className="skill-grid">
          {entries.map((entry) => {
            const observed = entry.sightings.filter((b) => b.state === "unmanaged");
            const pending = pendingId === entry.id;
            return (
              <article key={entry.id} className="skill-card permission-card">
                <div className="skill-card__head permission-card__head">
                  <OverflowTooltipText as="h3" className="skill-card__name">
                    {entry.displayName}
                  </OverflowTooltipText>
                  {entry.spec && (
                    <PermissionsStatusChip decision={entry.spec.decision} scope={entry.spec.scope} />
                  )}
                </div>

                <p className="permission-card__command">
                  <code>{entry.spec?.pattern ?? "—"}</code>
                </p>

                <div className="skill-card__footer">
                  <div className="harness-stack" aria-label={`Found on ${observed.length} harness(es)`}>
                    {observed.map((binding, index) => {
                      const presentation = getHarnessPresentation(
                        logoByHarness.get(binding.harness) ?? null,
                      );
                      const label = labelByHarness.get(binding.harness) ?? binding.harness;
                      return (
                        <UiTooltip key={binding.harness} content={`Found in ${label} config`}>
                          <span
                            className="harness-stack__item"
                            style={{ zIndex: observed.length - index }}
                          >
                            {presentation ? (
                              <img src={presentation.logoSrc} alt="" aria-hidden="true" />
                            ) : (
                              <span className="harness-stack__fallback">{label.slice(0, 1)}</span>
                            )}
                          </span>
                        </UiTooltip>
                      );
                    })}
                  </div>
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
                </div>
              </article>
            );
          })}
        </div>
      )}
    </>
  );
}
