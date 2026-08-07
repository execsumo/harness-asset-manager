import { FileClock, RefreshCw } from "lucide-react";

import { ErrorBanner } from "../../../components/ErrorBanner";
import { LoadingSpinner } from "../../../components/LoadingSpinner";
import { PageHeader } from "../../../components/PageHeader";
import { StatusBadge, type StatusBadgeTone } from "../../../components/ui/StatusBadge";
import { useCommonCopy, useLocale } from "../../../i18n";
import { useFormatPath } from "../../../lib/paths";
import type { ActivityEvent } from "../api/types";
import { useActivityCopy } from "../i18n";
import { useActivityQuery } from "../queries";

import "../styles/activity.css";

export default function ActivityPage() {
  const query = useActivityQuery();
  const copy = useActivityCopy();
  const common = useCommonCopy();
  const { locale } = useLocale();
  const formatPath = useFormatPath();
  const events = query.data?.events ?? [];

  return (
    <>
      <div className="page-chrome">
        <PageHeader
          title={copy.title}
          subtitle={copy.subtitle}
          actions={
            <button
              type="button"
              className="action-pill action-pill--md"
              onClick={() => void query.refetch()}
              disabled={query.isFetching}
              aria-busy={query.isFetching}
            >
              {query.isFetching ? (
                <LoadingSpinner size="sm" label={common.actions.refreshing} />
              ) : (
                <RefreshCw size={15} />
              )}
              <span>{query.isFetching ? common.actions.refreshing : common.actions.refresh}</span>
            </button>
          }
        />
      </div>

      {query.isError ? <ErrorBanner message={copy.unableToLoad} /> : null}

      {query.isPending && !query.data ? (
        <div className="panel-state">
          <LoadingSpinner label={copy.loading} />
        </div>
      ) : query.isError && !query.data ? null : events.length === 0 ? (
        <section className="empty-panel activity-empty">
          <div className="empty-panel__header">
            <span className="empty-panel__icon" aria-hidden="true">
              <FileClock size={24} />
            </span>
            <h3 className="empty-panel__title">{copy.emptyTitle}</h3>
          </div>
          <p className="empty-panel__body">{copy.emptyBody}</p>
        </section>
      ) : (
        <ol className="activity-list" aria-label={copy.title}>
          {events.map((event, index) => (
            <ActivityRow
              key={`${event.timestamp}-${event.family}-${event.operation}-${index}`}
              event={event}
              locale={locale}
              formatPath={formatPath}
            />
          ))}
        </ol>
      )}
    </>
  );
}

function ActivityRow({
  event,
  locale,
  formatPath,
}: {
  event: ActivityEvent;
  locale: string;
  formatPath: (path: string) => string;
}) {
  const copy = useActivityCopy();
  const subject = activitySubject(event);
  const hasDetails =
    Object.keys(event.parameters).length > 0 ||
    event.targetPaths.length > 0 ||
    Boolean(event.errorType);

  return (
    <li className="activity-list__item">
      <article className="activity-event">
        <div className="activity-event__main">
          <span className="activity-event__family">{humanize(event.family)}</span>
          <div className="activity-event__description">
            <h3>{humanize(event.operation)}</h3>
            {subject ? <p>{subject}</p> : null}
          </div>
        </div>
        <time className="activity-event__time" dateTime={event.timestamp} title={event.timestamp}>
          {formatTimestamp(event.timestamp, locale)}
        </time>
        <StatusBadge label={copy.outcomes[event.outcome]} tone={outcomeTone(event.outcome)} />

        {hasDetails ? (
          <details className="activity-event__details">
            <summary>{copy.details}</summary>
            <div className="activity-event__detail-grid">
              {Object.keys(event.parameters).length > 0 ? (
                <section>
                  <h4>{copy.parameters}</h4>
                  <dl className="activity-event__parameters">
                    {Object.entries(event.parameters).map(([name, value]) => (
                      <div key={name}>
                        <dt>{humanize(name)}</dt>
                        <dd>{formatParameter(value)}</dd>
                      </div>
                    ))}
                  </dl>
                </section>
              ) : null}
              <section>
                <h4>{copy.changedPaths}</h4>
                {event.targetPaths.length > 0 ? (
                  <ul className="activity-event__paths">
                    {event.targetPaths.map((path) => (
                      <li key={path}>
                        <code title={path}>{formatPath(path)}</code>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="muted-text">{copy.noPathsChanged}</p>
                )}
              </section>
              {event.errorType ? (
                <section>
                  <h4>{copy.errorType}</h4>
                  <code>{event.errorType}</code>
                </section>
              ) : null}
            </div>
          </details>
        ) : null}
      </article>
    </li>
  );
}

function humanize(value: string): string {
  const words = value.replaceAll("_", " ").replaceAll("-", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

function activitySubject(event: ActivityEvent): string | null {
  const parameters = event.parameters;
  for (const key of ["subject", "name", "skill_ref", "ref", "id", "qualified_name", "harness"]) {
    const value = parameters[key];
    if (typeof value === "string" && value) return value;
  }
  return null;
}

function formatParameter(value: ActivityEvent["parameters"][string]): string {
  if (Array.isArray(value)) return value.join(", ");
  if (value == null) return "—";
  return String(value);
}

function formatTimestamp(value: string, locale: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function outcomeTone(outcome: ActivityEvent["outcome"]): StatusBadgeTone {
  if (outcome === "succeeded") return "success";
  if (outcome === "partial" || outcome === "failed") return "warning";
  return "muted";
}
