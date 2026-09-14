import { Star } from "lucide-react";

import { HarnessAvatar } from "../../../components/harness/HarnessAvatar";
import { MatrixTable } from "../../../components/matrix";
import { OverflowTooltipText } from "../../../components/ui/OverflowTooltipText";
import { useCommonCopy } from "../../../i18n";
import { useFormatPath } from "../../../lib/paths";
import {
  useDisableConfigMutation,
  useEnableConfigMutation,
  useSetConfigTagsMutation,
} from "../api/queries";
import { useConfigsCopy } from "../i18n";
import { isStarred, type ConfigRowData, type ConfigStatus } from "../model/selectors";

const STATUS_TONE: Record<ConfigStatus, string> = {
  managed: "success",
  drifted: "warning",
  orphaned: "neutral",
  unmanaged: "muted",
};

interface ConfigsTableProps {
  rows: ConfigRowData[];
  selectedHarness: string | null;
  onSelect: (harness: string | null) => void;
}

export function ConfigsTable({ rows, selectedHarness, onSelect }: ConfigsTableProps) {
  const copy = useConfigsCopy();
  const common = useCommonCopy();
  const formatPath = useFormatPath();
  const tagsMutation = useSetConfigTagsMutation();
  const enable = useEnableConfigMutation();
  const disable = useDisableConfigMutation();

  const toggleStar = (row: ConfigRowData) => {
    const starred = isStarred(row);
    tagsMutation.mutate({
      harness: row.harness,
      tags: starred
        ? row.tags.filter((tag) => tag.toLowerCase() !== "starred")
        : ["starred", ...row.tags],
    });
  };

  return (
    <MatrixTable ariaLabel={copy.title} coverageColumnWidth="92px">
      <thead className="matrix-table__head">
        <tr>
          <th className="matrix-table__th matrix-table__th--identity">{copy.columns.harness}</th>
          <th className="matrix-table__th matrix-table__th--star">
            <span className="u-visually-hidden">{common.actions.star}</span>
          </th>
          <th className="matrix-table__th configs-table__th--status">{copy.columns.status}</th>
          <th className="matrix-table__th matrix-table__th--end">{copy.columns.keys}</th>
          <th className="matrix-table__th configs-table__th--captured">{copy.columns.captured}</th>
          <th className="matrix-table__th configs-table__th--actions">
            <span className="u-visually-hidden">{copy.columns.actions}</span>
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => {
          const starred = isStarred(row);
          const pending =
            (enable.isPending && enable.variables === row.harness) ||
            (disable.isPending && disable.variables === row.harness);

          return (
            <tr
              key={row.harness}
              className="matrix-table__row"
              data-selected={row.harness === selectedHarness}
              onClick={(event) => {
                if ((event.target as HTMLElement).closest("button, a")) return;
                onSelect(row.harness);
              }}
            >
              <td className="matrix-table__cell matrix-table__cell--identity">
                <div className="configs-table__identity">
                  <HarnessAvatar
                    harness={row.harness}
                    label={row.label}
                    logoKey={row.logoKey}
                    className={row.managed ? undefined : "configs-table__avatar--idle"}
                  />
                  <div className="configs-table__identity-copy">
                    <span className="matrix-table__name-text">{row.label}</span>
                    <OverflowTooltipText className="configs-table__path">
                      {formatPath(row.sourceFile)}
                    </OverflowTooltipText>
                  </div>
                </div>
              </td>

              <td className="matrix-table__cell matrix-table__cell--star">
                <button
                  type="button"
                  className={`asset-star-btn${starred ? " asset-star-btn--active" : ""}`}
                  aria-pressed={starred}
                  aria-label={starred ? common.actions.unstar : common.actions.star}
                  onClick={(event) => {
                    event.stopPropagation();
                    toggleStar(row);
                  }}
                >
                  <Star size={15} className="skill-star-icon" aria-hidden="true" />
                </button>
              </td>

              <td className="matrix-table__cell configs-table__cell--status">
                <span className={`ui-status-badge ui-status-badge--${STATUS_TONE[row.status]}`}>
                  {copy.status[row.status]}
                </span>
              </td>

              <td className="matrix-table__cell matrix-table__cell--coverage">
                <span className="configs-table__keys" data-empty={row.keyCount === 0}>
                  {row.keyCount === 0 ? copy.noKeys : row.keyCount}
                </span>
              </td>

              <td className="matrix-table__cell configs-table__cell--captured">
                <span className="configs-table__captured" title={row.capturedAt ?? undefined}>
                  {formatCapturedAt(row.capturedAt) ?? copy.never}
                </span>
              </td>

              <td className="matrix-table__cell configs-table__cell--actions">
                {row.managed ? (
                  <button
                    type="button"
                    className="action-pill"
                    disabled={pending}
                    data-pending={pending || undefined}
                    onClick={(event) => {
                      event.stopPropagation();
                      disable.mutate(row.harness);
                    }}
                  >
                    {copy.actions.stopManaging}
                  </button>
                ) : row.hasRecord ? (
                  <button
                    type="button"
                    className="action-pill"
                    onClick={(event) => {
                      event.stopPropagation();
                      onSelect(row.harness);
                    }}
                  >
                    {copy.actions.removeRecord}
                  </button>
                ) : (
                  <button
                    type="button"
                    className="action-pill action-pill--accent"
                    disabled={pending}
                    data-pending={pending || undefined}
                    onClick={(event) => {
                      event.stopPropagation();
                      enable.mutate(row.harness);
                    }}
                  >
                    {copy.actions.manage}
                  </button>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>
    </MatrixTable>
  );
}

const RELATIVE = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
const THRESHOLDS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["minute", 60_000],
  ["hour", 3_600_000],
  ["day", 86_400_000],
  ["week", 604_800_000],
  ["month", 2_629_800_000],
  ["year", 31_557_600_000],
];

function formatCapturedAt(value: string | null): string | null {
  if (!value) return null;
  const then = Date.parse(value);
  if (Number.isNaN(then)) return null;

  const elapsed = Date.now() - then;
  if (elapsed < 60_000) return RELATIVE.format(0, "minute");

  let unit: Intl.RelativeTimeFormatUnit = "minute";
  let size = 60_000;
  for (const [candidateUnit, candidateSize] of THRESHOLDS) {
    if (elapsed >= candidateSize) {
      unit = candidateUnit;
      size = candidateSize;
    }
  }
  return RELATIVE.format(-Math.floor(elapsed / size), unit);
}
