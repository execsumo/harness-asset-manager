import { useCallback, useMemo, useState } from "react";
import { SlidersHorizontal, Upload } from "lucide-react";
import { useSearchParams } from "react-router-dom";

import { ErrorBanner } from "../../../components/ErrorBanner";
import { FilterBar } from "../../../components/FilterBar";
import { LoadingSpinner } from "../../../components/LoadingSpinner";
import { PageHeader } from "../../../components/PageHeader";
import { TagFilterBar } from "../../../components/tags/TagFilterBar";
import { extractAssetTagCounts } from "../../../components/tags/tag-counts";
import { useSettingsQuery } from "../../settings/public";
import { useCaptureConfigsMutation, useConfigsListQuery } from "../api/queries";
import { ConfigsSummaryStrip } from "../components/ConfigsSummaryStrip";
import { ConfigsTable } from "../components/ConfigsTable";
import { ConfigsDrawer } from "../components/ConfigsDrawer";
import { useConfigsCopy } from "../i18n";
import {
  filterConfigsRows,
  selectConfigsRows,
  sortConfigsRows,
  summarizeConfigs,
  type ConfigStatus,
} from "../model/selectors";

const DETAIL_PARAM = "harness";
const STATUS_PARAM = "status";

const STATUSES: ReadonlySet<string> = new Set<ConfigStatus>([
  "managed",
  "drifted",
  "unmanaged",
  "orphaned",
]);

export default function ConfigsPage() {
  const copy = useConfigsCopy();
  const [searchParams, setSearchParams] = useSearchParams();
  const [search, setSearch] = useState("");

  const configsQuery = useConfigsListQuery();
  // Harness labels and logos live on the settings payload; the configs endpoint
  // only keys by harness id.
  const settingsQuery = useSettingsQuery();
  const capture = useCaptureConfigsMutation();

  const statusParam = searchParams.get(STATUS_PARAM);
  const status: ConfigStatus | "all" = STATUSES.has(statusParam ?? "")
    ? (statusParam as ConfigStatus)
    : "all";
  const selectedTags = useMemo(() => searchParams.getAll("tag"), [searchParams]);
  const selectedHarness = searchParams.get(DETAIL_PARAM);

  const patchParams = useCallback(
    (mutate: (params: URLSearchParams) => void) => {
      const params = new URLSearchParams(searchParams);
      mutate(params);
      setSearchParams(params, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const setStatus = useCallback(
    (next: ConfigStatus | "all") =>
      patchParams((params) => {
        if (next === "all") params.delete(STATUS_PARAM);
        else params.set(STATUS_PARAM, next);
      }),
    [patchParams],
  );

  const toggleTag = useCallback(
    (tag: string) =>
      patchParams((params) => {
        const current = params.getAll("tag");
        params.delete("tag");
        let removed = false;
        for (const value of current) {
          if (value.toLowerCase() === tag.toLowerCase()) removed = true;
          else params.append("tag", value);
        }
        if (!removed) params.append("tag", tag);
      }),
    [patchParams],
  );

  const clearTags = useCallback(
    () => patchParams((params) => params.delete("tag")),
    [patchParams],
  );

  const setSelectedHarness = useCallback(
    (harness: string | null) =>
      patchParams((params) => {
        if (harness) params.set(DETAIL_PARAM, harness);
        else params.delete(DETAIL_PARAM);
      }),
    [patchParams],
  );

  const clearFilters = useCallback(() => {
    setSearch("");
    patchParams((params) => {
      params.delete(STATUS_PARAM);
      params.delete("tag");
    });
  }, [patchParams]);

  const rows = useMemo(
    () => sortConfigsRows(selectConfigsRows(configsQuery.data, settingsQuery.data?.harnesses ?? [])),
    [configsQuery.data, settingsQuery.data],
  );
  const summary = useMemo(() => summarizeConfigs(rows), [rows]);
  const tagCounts = useMemo(() => extractAssetTagCounts(rows), [rows]);
  const visibleRows = useMemo(
    () => filterConfigsRows(rows, { search, status, tags: selectedTags }),
    [rows, search, status, selectedTags],
  );

  const selectedRow = rows.find((row) => row.harness === selectedHarness) ?? null;
  const filtersActive = search !== "" || status !== "all" || selectedTags.length > 0;

  return (
    <>
      <div className="page-chrome">
        <PageHeader
          title={copy.title}
          subtitle={copy.subtitle}
          actions={
            summary.managed > 0 ? (
              <button
                type="button"
                className="action-pill action-pill--md action-pill--accent"
                onClick={() => capture.mutate(true)}
                disabled={capture.isPending}
                data-pending={capture.isPending || undefined}
                title={copy.captureAllHint}
              >
                <Upload size={15} aria-hidden="true" />
                {capture.isPending ? copy.capturing : copy.captureAll}
              </button>
            ) : null
          }
        />
        {configsQuery.data ? (
          <>
            <ConfigsSummaryStrip summary={summary} activeStatus={status} onSelect={setStatus} />
            <FilterBar
              searchValue={search}
              onSearchChange={setSearch}
              searchPlaceholder={copy.searchPlaceholder}
              searchLabel={copy.searchLabel}
              trailing={
                <TagFilterBar
                  tags={tagCounts}
                  selectedTags={selectedTags}
                  onToggleTag={toggleTag}
                  onClearTags={clearTags}
                />
              }
            />
          </>
        ) : null}
      </div>

      {capture.isError ? <ErrorBanner message={String(capture.error)} /> : null}

      {configsQuery.isLoading ? (
        <div className="panel-state">
          <LoadingSpinner label={copy.loading} />
        </div>
      ) : configsQuery.isError ? (
        <ErrorBanner message={copy.unableToLoad} />
      ) : rows.length === 0 ? (
        <EmptyConfigs title={copy.emptyTitle} body={copy.emptyBody} />
      ) : visibleRows.length === 0 ? (
        <EmptyConfigs
          title={copy.noMatchesTitle}
          body={copy.noMatchesBody}
          action={
            filtersActive ? (
              <button type="button" className="action-pill action-pill--md" onClick={clearFilters}>
                {copy.clearFilters}
              </button>
            ) : null
          }
        />
      ) : (
        <ConfigsTable
          rows={visibleRows}
          selectedHarness={selectedHarness}
          onSelect={setSelectedHarness}
        />
      )}

      <ConfigsDrawer row={selectedRow} onClose={() => setSelectedHarness(null)} />
    </>
  );
}

function EmptyConfigs({
  title,
  body,
  action,
}: {
  title: string;
  body: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty-panel">
      <div className="empty-panel__header">
        <span className="empty-panel__icon">
          <SlidersHorizontal size={22} aria-hidden="true" />
        </span>
        <h2 className="empty-panel__title">{title}</h2>
      </div>
      <p className="empty-panel__body">{body}</p>
      {action ? <div className="empty-panel__actions">{action}</div> : null}
    </div>
  );
}
