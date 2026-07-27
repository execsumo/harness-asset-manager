import { Camera, RefreshCw, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { useConfigSnapshotsQuery, useTriggerConfigSnapshotMutation } from "../queries";

export function ConfigSnapshotsSection() {
  const { data, isLoading, isError, refetch } = useConfigSnapshotsQuery();
  const triggerMutation = useTriggerConfigSnapshotMutation();
  const [feedback, setFeedback] = useState<string | null>(null);

  const handleTakeSnapshot = async () => {
    try {
      const res = await triggerMutation.mutateAsync();
      setFeedback(`Captured ${res.captured_count} harness config snapshot(s)`);
      setTimeout(() => setFeedback(null), 4000);
    } catch {
      setFeedback("Failed to capture snapshots");
      setTimeout(() => setFeedback(null), 4000);
    }
  };

  const snapshots = data?.snapshots ?? [];

  return (
    <section className="settings-section">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
        <div>
          <h2 className="settings-section__heading" style={{ margin: 0 }}>
            Native Config Snapshots
          </h2>
          <p className="muted-text" style={{ fontSize: "0.85rem", marginTop: "0.25rem" }}>
            Local canonical backups of native harness config files stored in <code>~/.harness-asset-manager/configs/</code>
          </p>
        </div>
        <button
          type="button"
          className="button button--secondary"
          onClick={handleTakeSnapshot}
          disabled={triggerMutation.isPending}
          style={{ display: "inline-flex", alignItems: "center", gap: "0.4rem" }}
        >
          {triggerMutation.isPending ? (
            <RefreshCw size={14} className="spin" />
          ) : (
            <Camera size={14} />
          )}
          Take Snapshot Now
        </button>
      </div>

      {feedback && (
        <div className="badge badge--success" style={{ marginBottom: "1rem", padding: "0.5rem 0.75rem" }}>
          <ShieldCheck size={14} style={{ marginRight: "0.3rem", inlineSize: "auto" }} />
          {feedback}
        </div>
      )}

      {isLoading ? (
        <p className="muted-text">Loading native config snapshots...</p>
      ) : isError ? (
        <p className="muted-text" style={{ color: "var(--color-error)" }}>
          Unable to load config snapshots.
        </p>
      ) : snapshots.length === 0 ? (
        <p className="muted-text">No config snapshots taken yet. Click "Take Snapshot Now" to capture initial baselines.</p>
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table className="matrix-table" style={{ width: "100%", fontSize: "0.85rem" }}>
            <thead>
              <tr>
                <th>Harness</th>
                <th>Config File</th>
                <th>Trigger</th>
                <th>SHA-256 Baseline</th>
                <th>Snapshot Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {snapshots.map((item) => (
                <tr key={item.snapshot_id}>
                  <td style={{ fontWeight: 600, textTransform: "capitalize" }}>{item.harness}</td>
                  <td><code>{item.config_name}</code></td>
                  <td>
                    <span className={`badge badge--${item.trigger === "manual" ? "info" : item.trigger === "pre_write" ? "warning" : "neutral"}`}>
                      {item.trigger}
                    </span>
                  </td>
                  <td><code style={{ fontSize: "0.78rem" }}>{item.sha256 ? item.sha256.substring(0, 10) : "N/A"}</code></td>
                  <td className="muted-text">{item.timestamp}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
