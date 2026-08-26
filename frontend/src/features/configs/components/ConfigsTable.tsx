import { useState } from "react";
import { MatrixTable } from "../../../components/matrix";
import { StatusBadge } from "../../../components/ui/StatusBadge";
import type { ConfigRowData } from "../model/selectors";
import { ConfigsDrawer } from "./ConfigsDrawer";
import { useSetConfigTagsMutation } from "../api/queries";
import { Star } from "lucide-react";

export function ConfigsTable({ rows }: { rows: ConfigRowData[] }) {
  const [selectedHarness, setSelectedHarness] = useState<string | null>(null);
  const tagsMutation = useSetConfigTagsMutation();

  const toggleStar = (harness: string, currentTags: string[]) => {
    const isStarred = currentTags.includes("starred");
    const newTags = isStarred 
      ? currentTags.filter((t) => t !== "starred") 
      : ["starred", ...currentTags].sort();
    tagsMutation.mutate({ harness, tags: newTags });
  };

  return (
    <>
      <MatrixTable ariaLabel="Configs Matrix">
        <thead>
          <tr>
            <th className="matrix-table__th">Configs</th>
            <th className="matrix-table__th matrix-table__th--star"></th>
            <th className="matrix-table__th">Status</th>
            <th className="matrix-table__th">Keys</th>
            <th className="matrix-table__th">Drift</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const isStarred = row.tags.includes("starred");
            return (
              <tr 
                key={row.harness} 
                className="matrix-table__row"
                style={{ cursor: "pointer", opacity: row.managed ? 1 : 0.6 }}
                onClick={(e) => {
                  if ((e.target as HTMLElement).closest('button, a')) return;
                  setSelectedHarness(row.harness);
                }}
              >
                <td className="matrix-table__cell matrix-table__cell--identity">
                  <div className="matrix-table__identity-content">
                    <span className="matrix-table__identity-label">{row.harness}</span>
                  </div>
                </td>
                <td className="matrix-table__cell matrix-table__cell--star">
                  <button
                    type="button"
                    className="matrix-table__star-button"
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleStar(row.harness, row.tags);
                    }}
                  >
                    <Star
                      size={16}
                      className={`skill-star-icon ${isStarred ? "skill-star-icon--filled" : ""}`}
                    />
                  </button>
                </td>
                <td className="matrix-table__cell">
                  <StatusBadge 
                    label={row.managed ? "Managed" : "Not managed"} 
                    tone={row.managed ? "success" : "muted"} 
                  />
                </td>
                <td className="matrix-table__cell">{row.keyCount}</td>
                <td className="matrix-table__cell">{row.driftState}</td>
              </tr>
            );
          })}
        </tbody>
      </MatrixTable>
      
      <ConfigsDrawer 
        row={rows.find(r => r.harness === selectedHarness) || null}
        onClose={() => setSelectedHarness(null)}
      />
    </>
  );
}
