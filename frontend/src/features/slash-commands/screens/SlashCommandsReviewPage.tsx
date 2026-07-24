import { ErrorBanner } from "../../../components/ErrorBanner";
import { FilterBar } from "../../../components/FilterBar";
import { LoadingSpinner } from "../../../components/LoadingSpinner";
import { PageHeader } from "../../../components/PageHeader";
import { MatrixTable } from "../../../components/matrix";
import { SlashCommandReviewDetailSheet } from "../components/detail/SlashCommandReviewDetailSheet";
import { SlashCommandReviewMatrixView } from "../components/SlashCommandReviewMatrixView";
import { useSlashCommandsCopy } from "../i18n";
import { useSlashCommandsReviewController } from "../model/useSlashCommandsReviewController";

export default function SlashCommandsReviewPage() {
  const controller = useSlashCommandsReviewController();
  const copy = useSlashCommandsCopy();
  const {
    actionError,
    eligibleImportRows,
    importAllPending,
    pendingKey,
    query,
    rows,
    search,
    selectedCanonicalCommand,
    selectedRow,
    closeReviewDetail,
    openReviewDetail,
    setActionError,
    setSearch,
    handleAction,
    handleImportAll,
  } = controller;

  const total = query.data?.reviewCommands.length ?? 0;

  return (
    <>
      <div className="page-chrome">
        <PageHeader
          title={copy.review.title}
          subtitle={copy.review.subtitle(total)}
          actions={
            <button
              type="button"
              className="action-pill action-pill--md action-pill--accent"
              disabled={eligibleImportRows.length === 0 || importAllPending}
              onClick={() => {
                void handleImportAll();
              }}
            >
              {importAllPending ? <LoadingSpinner size="sm" label={copy.review.adoptingAllCommands} /> : null}
              {copy.review.adoptAllEligible}
            </button>
          }
        />
        {total > 0 ? (
          <FilterBar
            searchValue={search}
            onSearchChange={setSearch}
            searchPlaceholder={copy.review.searchPlaceholder}
            searchLabel={copy.review.searchLabel}
          />
        ) : null}
      </div>

      {actionError ? <ErrorBanner message={actionError} onDismiss={() => setActionError("")} /> : null}
      {query.error ? (
        <ErrorBanner message={query.error instanceof Error ? query.error.message : copy.inUse.unableToLoad} />
      ) : null}

      {query.isPending ? (
        <div className="panel-state">
          <LoadingSpinner label={copy.review.loading} />
        </div>
      ) : rows.length > 0 ? (
        <SlashCommandReviewMatrixView
          rows={rows}
          targets={query.data?.targets ?? []}
          pendingKey={pendingKey}
          onAction={handleAction}
          onOpen={openReviewDetail}
        />
      ) : (
        <div className="empty-panel">
          <h3 className="empty-panel__title">{copy.review.emptyTitle}</h3>
          <p className="empty-panel__body">
            {copy.review.emptyBody}
          </p>
        </div>
      )}

      <SlashCommandReviewDetailSheet
        row={selectedRow}
        canonicalCommand={selectedCanonicalCommand}
        targets={query.data?.targets ?? []}
        pendingKey={pendingKey}
        actionError={actionError}
        onClose={closeReviewDetail}
        onAction={handleAction}
      />
    </>
  );
}
