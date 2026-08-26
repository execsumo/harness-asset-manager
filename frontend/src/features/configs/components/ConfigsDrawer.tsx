import * as Dialog from "@radix-ui/react-dialog";
import { useEffect } from "react";
import { DetailHeader } from "../../../components/detail/DetailHeader";
import { DetailSection } from "../../../components/detail/DetailSection";
import type { ConfigRowData } from "../model/selectors";
import { useConfigDiffMutation, useEnableConfigMutation, useDisableConfigMutation, useRestoreConfigMutation, useCaptureConfigsMutation } from "../api/queries";
import { Download, Power, PowerOff, Upload } from "lucide-react";
import { StatusBadge } from "../../../components/ui/StatusBadge";

export function ConfigsDrawer({ row, onClose }: { row: ConfigRowData | null; onClose: () => void }) {
  const diff = useConfigDiffMutation();
  const enable = useEnableConfigMutation();
  const disable = useDisableConfigMutation();
  const restore = useRestoreConfigMutation();
  const capture = useCaptureConfigsMutation();
  
  useEffect(() => {
    if (row && row.managed) {
      diff.mutate(row.harness);
    }
  }, [row, diff.mutate]);

  const handleEnable = () => {
    if (row) enable.mutate(row.harness, { onSuccess: () => diff.mutate(row.harness) });
  };
  const handleDisable = () => {
    if (row) disable.mutate(row.harness);
  };
  const handleRestore = () => {
    if (row) restore.mutate(row.harness, { onSuccess: () => diff.mutate(row.harness) });
  };
  const handleCapture = () => {
    if (row) capture.mutate(true, { onSuccess: () => diff.mutate(row.harness) });
  };

  return (
    <Dialog.Root open={!!row} onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="detail-sheet__overlay" />
        <Dialog.Content className="detail-sheet" aria-describedby={undefined}>
          {row ? (
            <>
              <DetailHeader
                title={<h2 className="skill-detail__title-text">Configs: {row.harness}</h2>}
                onClose={onClose}
              />
              <div className="detail-sheet__body">
                <DetailSection heading="Status">
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <StatusBadge 
                      label={row.managed ? "Managed" : "Not managed"} 
                      tone={row.managed ? "success" : "muted"} 
                    />
                    <div>
                      {row.managed ? (
                        <button className="action-pill action-pill--danger" onClick={handleDisable} disabled={disable.isPending}>
                          <PowerOff size={14} className="action-pill__icon" /> Stop Managing
                        </button>
                      ) : (
                        <button className="action-pill action-pill--accent" onClick={handleEnable} disabled={enable.isPending}>
                          <Power size={14} className="action-pill__icon" /> Enable
                        </button>
                      )}
                    </div>
                  </div>
                  
                  {!row.managed && row.hasRecord && (
                    <div style={{ marginTop: "1rem", padding: "0.75rem", backgroundColor: "var(--bg-warning-muted)", borderRadius: "6px" }}>
                      <p style={{ margin: "0 0 0.5rem 0" }}><strong>Stale Record Detected</strong></p>
                      <p style={{ margin: "0 0 0.75rem 0", fontSize: "0.9em" }}>
                        A record exists in your manifest, but the config file is absent on this machine. If this harness is managed on another machine, leave this alone. If this is a stale record, you can remove it.
                      </p>
                      <button className="action-pill action-pill--danger" onClick={handleDisable} disabled={disable.isPending}>
                        <PowerOff size={14} className="action-pill__icon" /> Remove Record
                      </button>
                    </div>
                  )}
                </DetailSection>

                <DetailSection heading="Source">
                  <code style={{ wordBreak: 'break-all' }}>{row.sourceFile}</code>
                </DetailSection>
                
                {row.managed && (
                  <>
                    <DetailSection heading="Last Captured">
                      <span className="muted-text">{row.capturedAt ? new Date(row.capturedAt).toLocaleString() : 'Never'}</span>
                    </DetailSection>

                    <DetailSection heading="Drift Analysis">
                      <div style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}>
                        <button className="action-pill" onClick={handleRestore} disabled={restore.isPending}>
                          <Download size={14} className="action-pill__icon" /> Restore
                        </button>
                        <button className="action-pill action-pill--accent" onClick={handleCapture} disabled={capture.isPending}>
                          <Upload size={14} className="action-pill__icon" /> Capture Current
                        </button>
                      </div>

                      {diff.isPending ? (
                        <p className="muted-text">Analyzing drift...</p>
                      ) : diff.data?.state === "drifted" ? (
                        <div style={{ padding: "0.75rem", backgroundColor: "var(--bg-warning-muted)", borderRadius: "6px" }}>
                          <p style={{ margin: "0 0 0.5rem 0" }}><strong>Drift detected</strong></p>
                          {diff.data.missing.length > 0 && <p style={{ margin: "0 0 0.25rem 0" }}>Missing in file: {diff.data.missing.join(", ")}</p>}
                          {diff.data.extra.length > 0 && <p style={{ margin: "0 0 0.25rem 0" }}>Extra in file: {diff.data.extra.join(", ")}</p>}
                          {diff.data.changed.length > 0 && <p style={{ margin: "0" }}>Changed values: {diff.data.changed.join(", ")}</p>}
                        </div>
                      ) : (
                        <p className="muted-text">No drift. File matches manifest.</p>
                      )}
                    </DetailSection>

                    <DetailSection heading={`Preferences Map (${row.keyCount} keys)`}>
                      <pre style={{ background: "var(--bg-secondary)", padding: "1rem", borderRadius: "6px", overflowX: "auto", fontSize: "0.85em" }}>
                        {JSON.stringify(row.preferences, null, 2)}
                      </pre>
                    </DetailSection>
                  </>
                )}
              </div>
            </>
          ) : null}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
