import { useConfigsCopy } from "../i18n";
import type { ConfigsSummary, ConfigStatus } from "../model/selectors";

interface ConfigsSummaryStripProps {
  summary: ConfigsSummary;
  activeStatus: ConfigStatus | "all";
  onSelect: (status: ConfigStatus | "all") => void;
}

/** Counts that double as the status filter — clicking a tile scopes the table. */
export function ConfigsSummaryStrip({
  summary,
  activeStatus,
  onSelect,
}: ConfigsSummaryStripProps) {
  const copy = useConfigsCopy();

  const tiles: {
    status: ConfigStatus;
    label: string;
    hint: string;
    value: number;
    tone: "accent" | "warning" | "muted";
  }[] = [
    {
      status: "managed",
      label: copy.summary.inSync,
      hint: copy.summary.inSyncHint,
      value: summary.inSync,
      tone: "accent",
    },
    {
      status: "drifted",
      label: copy.summary.drifted,
      hint: copy.summary.driftedHint,
      value: summary.drifted,
      tone: "warning",
    },
    {
      status: "unmanaged",
      label: copy.summary.unmanaged,
      hint: copy.summary.unmanagedHint,
      value: summary.unmanaged,
      tone: "muted",
    },
  ];

  return (
    <div className="configs-summary" role="group" aria-label={copy.title}>
      {tiles.map((tile) => {
        const active = activeStatus === tile.status;
        return (
          <button
            key={tile.status}
            type="button"
            className="configs-summary__tile"
            data-tone={tile.tone}
            data-active={active}
            aria-pressed={active}
            disabled={tile.value === 0 && !active}
            title={tile.hint}
            onClick={() => onSelect(active ? "all" : tile.status)}
          >
            <span className="configs-summary__value" data-empty={tile.value === 0}>
              {tile.value}
            </span>
            <span className="configs-summary__label">{tile.label}</span>
          </button>
        );
      })}
    </div>
  );
}
