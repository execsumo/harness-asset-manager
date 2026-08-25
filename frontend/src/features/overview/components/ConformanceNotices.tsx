import { AlertTriangle, CheckCircle2 } from "lucide-react";
import { Link } from "react-router-dom";

import type { OverviewConformanceNotice } from "../../../app/capability-registry";
import { useOverviewCopy } from "../i18n";

interface ConformanceNoticesProps {
  notices: OverviewConformanceNotice[];
  loading: boolean;
}

/**
 * One notice per thing that needs correcting, each linking to the asset.
 *
 * Deliberately not a summary table. A count tells you a number and leaves you to go
 * hunting; a notice names the asset, says what to fix, and takes you there.
 */
export function ConformanceNotices({ notices, loading }: ConformanceNoticesProps) {
  const copy = useOverviewCopy();

  return (
    <section className="overview-conformance" aria-labelledby="overview-conformance-title">
      <div className="overview-section__head">
        <h2 id="overview-conformance-title">{copy.sections.conformance}</h2>
        {notices.length > 0 ? (
          <span className="overview-conformance__count">{notices.length}</span>
        ) : null}
      </div>
      {loading ? (
        <div className="overview-conformance__list" aria-hidden="true">
          <div className="overview-conformance__row overview-conformance__row--skeleton" />
          <div className="overview-conformance__row overview-conformance__row--skeleton" />
        </div>
      ) : notices.length > 0 ? (
        <div className="overview-conformance__list ui-scrollbar">
          {notices.map((notice) => (
            <Link key={notice.key} to={notice.to} className="overview-conformance__row">
              <AlertTriangle size={14} aria-hidden="true" />
              <span className="overview-conformance__copy">
                <strong>{notice.asset}</strong>
                <span>{notice.message}</span>
              </span>
            </Link>
          ))}
        </div>
      ) : (
        <div className="overview-conformance__empty">
          <CheckCircle2 size={18} />
          <span>{copy.sections.noConformanceIssues}</span>
        </div>
      )}
    </section>
  );
}
