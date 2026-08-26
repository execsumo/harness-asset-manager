import { useCaptureConfigsMutation, useConfigsQuery, useDiffConfigMutation, useRestoreConfigMutation } from "../queries";
import { StatusBadge } from "../../../components/ui/StatusBadge";
import { LoadingSpinner } from "../../../components/LoadingSpinner";
import { useEffect, useState } from "react";
import type { ConfigRecordResponse } from "../api/types";
import { Download } from "lucide-react";

export function ConfigsSection() {
  const { data, isLoading } = useConfigsQuery();
  const capture = useCaptureConfigsMutation();
  const restore = useRestoreConfigMutation();

  if (isLoading) {
    return <LoadingSpinner label="Loading configs..." />;
  }

  if (!data) return null;

  return (
    <section className="settings-section">
      <h2 className="settings-section__heading" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        Configuration Preferences
        <button
          className="btn btn--primary"
          onClick={() => capture.mutate(false)}
          disabled={capture.isPending}
        >
          {capture.isPending ? "Syncing..." : "Sync All"}
        </button>
      </h2>
      <p className="muted-text" style={{ marginBottom: "1rem" }}>
        Manage synced config preferences across your harnesses.
      </p>

      {Object.entries(data).length === 0 ? (
        <p className="muted-text">No preferences synced.</p>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          {Object.entries(data).map(([harness, record]) => (
            <ConfigRow
              key={harness}
              harness={harness}
              record={record}
              onRestore={() => restore.mutate(harness)}
              isRestoring={restore.isPending}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function ConfigRow({ harness, record, onRestore, isRestoring }: { harness: string; record: ConfigRecordResponse; onRestore: () => void; isRestoring: boolean }) {
  const diff = useDiffConfigMutation();
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (isOpen && !diff.data && !diff.isPending) {
      diff.mutate(harness);
    }
  }, [isOpen, harness, diff]);

  const state = diff.data?.state || "managed";
  const tone = state === "drifted" ? "warning" : state === "unmanaged" ? "muted" : "success";

  return (
    <details
      className="settings-card"
      style={{ padding: "1rem", border: "1px solid var(--border-color)", borderRadius: "6px" }}
      onToggle={(e) => setIsOpen(e.currentTarget.open)}
    >
      <summary style={{ display: "flex", justifyContent: "space-between", alignItems: "center", cursor: "pointer", listStyle: "none" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <strong style={{ textTransform: "capitalize" }}>{harness}</strong>
          {diff.isPending ? (
            <StatusBadge label="checking..." tone="muted" />
          ) : (
            <StatusBadge label={state} tone={tone} />
          )}
        </div>
      </summary>

      <div style={{ marginTop: "1rem", paddingTop: "1rem", borderTop: "1px solid var(--border-color)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "1rem" }}>
          <span className="muted-text">Last captured: {new Date(record.capturedAt).toLocaleString()}</span>
          <div style={{ display: "flex", gap: "0.5rem" }}>
            <button className="btn" onClick={onRestore} disabled={isRestoring}>
              <Download size={14} /> Restore
            </button>
          </div>
        </div>

        {diff.data?.state === "drifted" && (
          <div style={{ marginBottom: "1rem", padding: "0.5rem", backgroundColor: "var(--bg-warning-muted)", borderRadius: "4px" }}>
            <p><strong>Drift detected!</strong></p>
            {diff.data.missing.length > 0 && <p>Missing: {diff.data.missing.join(", ")}</p>}
            {diff.data.extra.length > 0 && <p>Extra: {diff.data.extra.join(", ")}</p>}
            {diff.data.changed.length > 0 && <p>Changed: {diff.data.changed.join(", ")}</p>}
          </div>
        )}

        <div>
          <strong>Preferences:</strong>
          <pre style={{ background: "var(--bg-secondary)", padding: "1rem", borderRadius: "4px", marginTop: "0.5rem", fontSize: "0.85em", overflowX: "auto" }}>
            {JSON.stringify(record.preferences, null, 2)}
          </pre>
        </div>
      </div>
    </details>
  );
}
