import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { ErrorBanner } from "../../../components/ErrorBanner";
import { PageHeader } from "../../../components/PageHeader";
import { useCommonCopy } from "../../../i18n";
import {
  invalidateOverviewData,
  useOverviewData,
} from "../../../app/capability-registry";
import { HarnessCoverageMap } from "../components/HarnessCoverageMap";
import { QuickLinks } from "../components/QuickLinks";
import { ReviewQueue } from "../components/ReviewQueue";
import { useOverviewCopy } from "../i18n";

export default function OverviewPage() {
  const queryClient = useQueryClient();
  const {
    skillsQuery,
    slashCommandsQuery,
    mcpQuery,
    hooksQuery,
    permissionsQuery,
    agentsQuery,
    model,
  } = useOverviewData();
  const [refreshing, setRefreshing] = useState(false);
  const copy = useOverviewCopy();
  const common = useCommonCopy();

  const queries = [
    skillsQuery,
    slashCommandsQuery,
    mcpQuery,
    hooksQuery,
    permissionsQuery,
    agentsQuery,
  ];
  const loading = queries.some((query) => query.isPending && !query.data);
  const allFailed =
    queries.every((query) => query.isError && !query.data);

  async function refreshOverview() {
    setRefreshing(true);
    try {
      await invalidateOverviewData(queryClient);
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <>
      <div className="page-chrome">
        <PageHeader title={copy.screen.title} />
      </div>

      {allFailed ? (
        <div className="panel-state overview-error-state">
          <span>{copy.screen.unableToLoadOverview}</span>
          <button
            type="button"
            className="action-pill action-pill--md action-pill--accent"
            onClick={() => void refreshOverview()}
            disabled={refreshing}
          >
            {refreshing ? `${common.actions.refreshing}...` : common.actions.refresh}
          </button>
        </div>
      ) : (
        <div className="overview-page">
          <ErrorBanners
            errors={[
              { query: skillsQuery, message: copy.screen.unableToLoadSkills },
              { query: slashCommandsQuery, message: copy.screen.unableToLoadSlashCommands },
              { query: mcpQuery, message: copy.screen.unableToLoadMcpServers },
              { query: hooksQuery, message: copy.screen.unableToLoadHooks },
              { query: permissionsQuery, message: copy.screen.unableToLoadPermissions },
              { query: agentsQuery, message: copy.screen.unableToLoadAgents },
            ]}
          />

          <HarnessCoverageMap rows={model.harnessRows} totalsRow={model.totalsRow} loading={loading} />
          <div className="overview-dashboard-grid">
            <ReviewQueue items={model.reviewItems} loading={loading} />
            <QuickLinks shortcuts={model.shortcuts} />
          </div>
        </div>
      )}
    </>
  );
}

interface QueryErrorSource {
  isError: boolean;
  data?: unknown;
  error: unknown;
}

function ErrorBanners({
  errors,
}: {
  errors: Array<{ query: QueryErrorSource; message: (text: string) => string }>;
}) {
  return (
    <>
      {errors.map(({ query, message }, index) =>
        query.isError && !query.data ? (
          <ErrorBanner key={index} message={message(errorMessage(query.error))} />
        ) : null,
      )}
    </>
  );
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown error";
}
