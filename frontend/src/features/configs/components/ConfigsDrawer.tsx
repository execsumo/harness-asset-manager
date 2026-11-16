import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useRef } from "react";
import { Download, Power, PowerOff, Upload } from "lucide-react";

import { ErrorBanner } from "../../../components/ErrorBanner";
import { DetailHeader } from "../../../components/detail/DetailHeader";
import { DetailNote } from "../../../components/detail/DetailNote";
import { DetailSection } from "../../../components/detail/DetailSection";
import { DetailTags } from "../../../components/detail/DetailTags";
import { HarnessAvatar } from "../../../components/harness/HarnessAvatar";
import { useFormatPath } from "../../../lib/paths";
import {
  useCaptureConfigsMutation,
  useConfigDiffMutation,
  useDisableConfigMutation,
  useEnableConfigMutation,
  useRestoreConfigMutation,
  useSetConfigTagsMutation,
} from "../api/queries";
import { useConfigsCopy } from "../i18n";
import { describeActionError, reportFailure, useSingleFlight, type ConfigActionError } from "../model/action-errors";
import type { ConfigRowData, ConfigStatus } from "../model/selectors";

const STATUS_TONE: Record<ConfigStatus, string> = {
  managed: "success",
  drifted: "warning",
  orphaned: "neutral",
  unmanaged: "muted",
};

const CAPTURED_AT_FORMAT = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

interface ConfigsDrawerActions {
  actionError: ConfigActionError | null;
  onActionError: (message: string) => void;
  onDismissActionError: () => void;
}

export function ConfigsDrawer({
  row,
  knownTags,
  onClose,
  ...actions
}: {
  row: ConfigRowData | null;
  knownTags: string[];
  onClose: () => void;
} & ConfigsDrawerActions) {
  return (
    <Dialog.Root open={row !== null} onOpenChange={(open) => !open && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="detail-sheet__overlay" />
        <Dialog.Content className="detail-sheet" aria-describedby={undefined}>
          {row ? <ConfigsDrawerBody row={row} knownTags={knownTags} onClose={onClose} {...actions} /> : null}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function ConfigsDrawerBody({
  row,
  knownTags,
  onClose,
  actionError,
  onActionError,
  onDismissActionError,
}: { row: ConfigRowData; knownTags: string[]; onClose: () => void } & ConfigsDrawerActions) {
  const copy = useConfigsCopy();
  const formatPath = useFormatPath();
  const diff = useConfigDiffMutation();
  const enable = useEnableConfigMutation();
  const disable = useDisableConfigMutation();
  const restore = useRestoreConfigMutation();
  const capture = useCaptureConfigsMutation();
  const tagsMutation = useSetConfigTagsMutation();

  const { harness, managed } = row;
  const { mutate: runDiff } = diff;

  useEffect(() => {
    if (managed) runDiff(harness);
  }, [harness, managed, runDiff]);

  const diffError = diff.error;
  useEffect(() => {
    if (diffError) onActionError(describeActionError(copy.errors.diff(row.label), diffError));
  }, [diffError, onActionError, copy, row.label]);

  // mutateAsync keeps reporting a failure after the drawer closes; the diff
  // only refreshes while the drawer is still open.
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const singleFlight = useSingleFlight();
  const runAction = (
    key: string,
    headline: string,
    action: () => Promise<unknown>,
    refresh = false,
  ) =>
    singleFlight(key, async () => {
      const ok = await reportFailure(onActionError, headline, action);
      if (ok && refresh && mounted.current) runDiff(harness);
    });
  const drift = diff.data;
  const hasDrift = drift?.state === "drifted";

  return (
    <>
      <DetailHeader
        closeLabel={copy.detail.close}
        onClose={onClose}
        title={
          <div className="configs-detail__title">
            <HarnessAvatar harness={row.harness} label={row.label} logoKey={row.logoKey} />
            <h2 className="skill-detail__title-text">{row.label}</h2>
          </div>
        }
        meta={
          <>
            <span className={`ui-status-badge ui-status-badge--${STATUS_TONE[row.status]}`}>
              {copy.status[row.status]}
            </span>
            {row.managed ? (
              <span className="configs-detail__meta-item">
                {copy.detail.keyCount(row.keyCount)}
              </span>
            ) : null}
            {row.capturedAt ? (
              <span className="configs-detail__meta-item">
                {copy.detail.capturedAt} {CAPTURED_AT_FORMAT.format(new Date(row.capturedAt))}
              </span>
            ) : null}
          </>
        }
        titleAction={
          row.managed ? (
            <button
              type="button"
              className="action-pill action-pill--danger"
              onClick={() => void runAction("disable", copy.errors.stopManaging(row.label), () => disable.mutateAsync(row.harness))}
              disabled={disable.isPending}
              data-pending={disable.isPending || undefined}
            >
              <PowerOff size={14} aria-hidden="true" />
              {copy.actions.stopManaging}
            </button>
          ) : !row.hasRecord ? (
            <button
              type="button"
              className="action-pill action-pill--accent"
              onClick={() => void runAction("enable", copy.errors.manage(row.label), () => enable.mutateAsync(row.harness), true)}
              disabled={enable.isPending}
              data-pending={enable.isPending || undefined}
            >
              <Power size={14} aria-hidden="true" />
              {copy.actions.manage}
            </button>
          ) : null
        }
      />

      <div className="detail-sheet__body">
        {actionError ? (
          <ErrorBanner key={actionError.id} message={actionError.message} onDismiss={onDismissActionError} />
        ) : null}
        <DetailSection heading="Tags">
          <DetailTags
            tags={row.tags}
            knownTags={knownTags}
            canEdit
            disabled={tagsMutation.isPending}
            onAddTag={async (tag) => { await tagsMutation.mutateAsync({ harness: row.harness, tags: [...row.tags, tag] }); }}
            onRemoveTag={async (tag) => { await tagsMutation.mutateAsync({ harness: row.harness, tags: row.tags.filter((item) => item.toLowerCase() !== tag.toLowerCase()) }); }}
          />
        </DetailSection>
        <DetailSection heading={copy.detail.sourceHeading}>
          <code className="configs-detail__path">{formatPath(row.sourceFile)}</code>
        </DetailSection>

        {!row.managed ? (
          <DetailSection heading={copy.detail.statusHeading}>
            {row.hasRecord ? (
              <DetailNote
                title={copy.detail.orphanTitle}
                actions={
                  <button
                    type="button"
                    className="action-pill action-pill--danger"
                    onClick={() => void runAction("disable", copy.errors.stopManaging(row.label), () => disable.mutateAsync(row.harness))}
                    disabled={disable.isPending}
                    data-pending={disable.isPending || undefined}
                  >
                    <PowerOff size={14} aria-hidden="true" />
                    {copy.actions.removeRecord}
                  </button>
                }
              >
                <p>{copy.detail.orphanBody}</p>
              </DetailNote>
            ) : (
              <p className="muted-text">{copy.detail.unmanagedBody}</p>
            )}
          </DetailSection>
        ) : null}

        {row.managed ? (
          <>
            <DetailSection heading={copy.detail.driftHeading}>
              <div className="configs-detail__actions">
                <button
                  type="button"
                  className="action-pill"
                  onClick={() => void runAction("restore", copy.errors.restore(row.label), () => restore.mutateAsync(row.harness), true)}
                  disabled={restore.isPending}
                  data-pending={restore.isPending || undefined}
                  title={copy.detail.restoreHint}
                >
                  <Download size={14} aria-hidden="true" />
                  {copy.actions.restore}
                </button>
                <button
                  type="button"
                  className="action-pill action-pill--accent"
                  onClick={() => void runAction("capture", copy.errors.captureHarness(row.label), () => capture.mutateAsync(true), true)}
                  disabled={capture.isPending}
                  data-pending={capture.isPending || undefined}
                  title={copy.detail.captureHint}
                >
                  <Upload size={14} aria-hidden="true" />
                  {copy.actions.capture}
                </button>
              </div>

              {diff.isPending ? (
                <p className="muted-text">{copy.detail.analyzing}</p>
              ) : hasDrift ? (
                <DetailNote title={copy.detail.driftDetected}>
                  <dl className="configs-detail__drift">
                    <DriftGroup label={copy.detail.missing} keys={drift.missing} />
                    <DriftGroup label={copy.detail.extra} keys={drift.extra} />
                    <DriftGroup label={copy.detail.changed} keys={drift.changed} />
                  </dl>
                </DetailNote>
              ) : diff.isError ? (
                <div className="configs-detail__actions">
                  <p className="muted-text">{copy.detail.driftUnknown}</p>
                  <button type="button" className="action-pill" onClick={() => runDiff(harness)}>
                    {copy.detail.retryDiff}
                  </button>
                </div>
              ) : (
                <p className="muted-text">{copy.detail.noDrift}</p>
              )}
            </DetailSection>

            <DetailSection heading={copy.detail.preferencesHeading}>
              <pre className="configs-detail__preferences ui-scrollbar--thin">
                {JSON.stringify(row.preferences, null, 2)}
              </pre>
            </DetailSection>
          </>
        ) : null}
      </div>
    </>
  );
}

function DriftGroup({ label, keys }: { label: string; keys: string[] }) {
  if (keys.length === 0) return null;
  return (
    <div className="configs-detail__drift-group">
      <dt>{label}</dt>
      <dd>
        {keys.map((key) => (
          <code key={key} className="configs-detail__drift-key">
            {key}
          </code>
        ))}
      </dd>
    </div>
  );
}
