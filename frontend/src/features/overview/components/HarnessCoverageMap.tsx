import { AlertTriangle, Layers } from "lucide-react";
import { Link } from "react-router-dom";

import { HarnessAvatar } from "../../../components/harness/HarnessAvatar";
import type {
  OverviewHarnessAvailabilityIssue,
  OverviewHarnessCellKey,
  OverviewHarnessRow,
} from "../../../app/capability-registry";
import { coverageCellLinks } from "../../../app/capability-registry";
import { useOverviewCopy } from "../i18n";

const CELL_KEYS: OverviewHarnessCellKey[] = [
  "skills",
  "commands",
  "mcp",
  "hooks",
  "permissions",
  "agents",
];

interface HarnessCoverageMapProps {
  rows: OverviewHarnessRow[];
  totalsRow: OverviewHarnessRow;
  loading: boolean;
}

export function HarnessCoverageMap({ rows, totalsRow, loading }: HarnessCoverageMapProps) {
  const copy = useOverviewCopy();

  return (
    <section className="overview-coverage-map" aria-labelledby="overview-coverage-title">
      <div className="overview-section__head">
        <h2 id="overview-coverage-title">{copy.sections.activeHarnesses}</h2>
      </div>
      {loading && rows.length === 0 ? (
        <div className="overview-coverage-table" aria-hidden="true">
          <div className="overview-coverage-row overview-coverage-row--skeleton" />
          <div className="overview-coverage-row overview-coverage-row--skeleton" />
          <div className="overview-coverage-row overview-coverage-row--skeleton" />
        </div>
      ) : rows.length > 0 ? (
        <div className="overview-coverage-table">
          <div className="overview-coverage-row overview-coverage-row--head">
            <span>{copy.sections.harness}</span>
            {CELL_KEYS.map((key) => (
              <span key={key}>{copy.sections[key]}</span>
            ))}
            <span>{copy.sections.needsReview}</span>
          </div>
          <TotalsRow row={totalsRow} />
          {rows.map((row) => (
            <CoverageRow key={row.harness} row={row} />
          ))}
        </div>
      ) : (
        <p className="overview-empty-note">{copy.sections.noHarnesses}</p>
      )}
    </section>
  );
}

function TotalsRow({ row }: { row: OverviewHarnessRow }) {
  const copy = useOverviewCopy();

  return (
    <div className="overview-coverage-row overview-coverage-row--totals">
      <span className="overview-coverage-row__identity">
        <span className="overview-coverage-row__all-icon" aria-hidden="true">
          <Layers size={16} />
        </span>
        <span>
          <strong>{row.label || copy.sections.allHarnesses}</strong>
        </span>
      </span>
      {CELL_KEYS.map((key) => (
        <TotalsCell key={key} cellKey={key} row={row} />
      ))}
      <ReviewTotalCell row={row} />
    </div>
  );
}

function TotalsCell({
  cellKey,
  row,
}: {
  cellKey: OverviewHarnessCellKey;
  row: OverviewHarnessRow;
}) {
  const copy = useOverviewCopy();
  const cell = row.cells[cellKey];
  const links = coverageCellLinks(cellKey);

  return (
    <span className="overview-coverage-cell" data-active={cell.active > 0}>
      <span className="overview-coverage-cell__dot" aria-hidden="true" />
      {cell.active > 0 ? (
        <Link
          to={links.activeTo}
          className="overview-coverage-cell__link"
          aria-label={copy.sections.allCapabilityAria(copy.sections[cellKey])}
        >
          {cell.active.toLocaleString()}
        </Link>
      ) : (
        <span>{cell.active.toLocaleString()}</span>
      )}
      {cell.review > 0 ? (
        <Link
          to={links.reviewTo}
          className="overview-coverage-cell__detail overview-coverage-cell__link"
          aria-label={copy.sections.allReviewAria(cell.review, copy.sections[cellKey])}
        >
          +{cell.review.toLocaleString()}
        </Link>
      ) : null}
    </span>
  );
}

function CoverageRow({ row }: { row: OverviewHarnessRow }) {
  return (
    <div className="overview-coverage-row">
      <span className="overview-coverage-row__identity">
        <HarnessAvatar harness={row.harness} label={row.label} logoKey={row.logoKey} />
        <span>
          <strong>
            {row.label}
            {row.availabilityIssues.map((issue) => (
              <AvailabilityWarning key={issue.capability} issue={issue} />
            ))}
          </strong>
        </span>
      </span>
      {CELL_KEYS.map((key) => (
        <CoverageCell key={key} cellKey={key} row={row} />
      ))}
      <ReviewTotalCell row={row} />
    </div>
  );
}

function AvailabilityWarning({ issue }: { issue: OverviewHarnessAvailabilityIssue }) {
  const copy = useOverviewCopy();
  const message = copy.sections.capabilityIssue(issue.capability, issue.reason);

  return (
    <span
      className="overview-coverage-warning"
      title={message}
      aria-label={`${issue.capability}: ${issue.reason}`}
    >
      <AlertTriangle size={13} />
    </span>
  );
}

function CoverageCell({
  cellKey,
  row,
}: {
  cellKey: OverviewHarnessCellKey;
  row: OverviewHarnessRow;
}) {
  const copy = useOverviewCopy();
  const cell = row.cells[cellKey];

  return (
    <span className="overview-coverage-cell" data-active={cell.active > 0}>
      <span className="overview-coverage-cell__dot" aria-hidden="true" />
      {cell.active > 0 ? (
        <Link
          to={coverageCellLinks(cellKey, row.harness).activeTo}
          className="overview-coverage-cell__link"
          aria-label={copy.sections.capabilityOnHarness(copy.sections[cellKey], row.label)}
        >
          {cell.active.toLocaleString()}
        </Link>
      ) : (
        <span>{cell.active.toLocaleString()}</span>
      )}
      {cell.review > 0 ? (
        <Link
          to={coverageCellLinks(cellKey, row.harness).reviewTo}
          className="overview-coverage-cell__detail overview-coverage-cell__link"
          aria-label={copy.sections.reviewOnHarness(cell.review, copy.sections[cellKey], row.label)}
        >
          +{cell.review.toLocaleString()}
        </Link>
      ) : null}
    </span>
  );
}

function ReviewTotalCell({ row }: { row: OverviewHarnessRow }) {
  const total = CELL_KEYS.reduce((sum, key) => sum + row.cells[key].review, 0);

  return (
    <span className="overview-coverage-cell" data-tone="warning" data-active={total > 0}>
      <span className="overview-coverage-cell__dot" aria-hidden="true" />
      <span>{total.toLocaleString()}</span>
    </span>
  );
}
