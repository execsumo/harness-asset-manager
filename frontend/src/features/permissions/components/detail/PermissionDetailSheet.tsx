import * as Dialog from "@radix-ui/react-dialog";
import { Loader2, Star, Trash2 } from "lucide-react";
import { useId, useState } from "react";

import { DetailBindingIdentity } from "../../../../components/detail/DetailBindingIdentity";
import { DetailHeader } from "../../../../components/detail/DetailHeader";
import { DetailSection } from "../../../../components/detail/DetailSection";
import { DetailTags } from "../../../../components/detail/DetailTags";
import { ErrorBanner } from "../../../../components/ErrorBanner";
import { LoadingSpinner } from "../../../../components/LoadingSpinner";
import { usePermissionDetailQuery, useSetPermissionTagsMutation } from "../../api/management-queries";
import { usePermissionsCopy } from "../../i18n";
import { isPermissionsHarnessAddressable } from "../../model/selectors";

interface PermissionDetailSheetProps {
  id: string | null;
  knownTags?: string[];
  columns: any[];
  pendingPerHarness: ReadonlySet<string>;
  isServerPending: boolean;
  isUninstalling: boolean;
  onClose: () => void;
  onEnableHarness: (harness: string) => void;
  onDisableHarness: (harness: string) => void;
  onResolveConfig: (args: {
    sourceKind: "managed" | "harness";
    observedHarness?: string | null;
    harnesses?: string[];
  }) => Promise<void>;
  onUninstall: () => void;
}

export function PermissionDetailSheet({
  id,
  knownTags,
  columns,
  pendingPerHarness,
  isServerPending,
  isUninstalling,
  onClose,
  onEnableHarness,
  onDisableHarness,
  onResolveConfig,
  onUninstall,
}: PermissionDetailSheetProps) {
  const headingId = useId();
  const copy = usePermissionsCopy();
  const detailQuery = usePermissionDetailQuery(id);
  const setTagsMutation = useSetPermissionTagsMutation();
  const [resolvePending, setResolvePending] = useState(false);
  const [resolveError, setResolveError] = useState("");

  if (!id) return null;

  const detail = detailQuery.data ?? null;
  const spec = detail?.spec ?? null;
  const displayName = detail?.displayName ?? id;
  const errorMessage = detailQuery.error instanceof Error ? detailQuery.error.message : "";
  const isStarred = (detail?.tags || []).some((t) => t.toLowerCase() === "starred");

  const handleToggleStar = async () => {
    if (!detail) return;
    const nextTags = isStarred
      ? (detail.tags || []).filter((t) => t.toLowerCase() !== "starred")
      : ["starred", ...(detail.tags || []).filter((t) => t.toLowerCase() !== "starred")];
    await setTagsMutation.mutateAsync({
      id: detail.id,
      tags: nextTags,
    });
  };

  const handleAddTag = async (newTag: string) => {
    if (!detail) return;
    const nextTags = [...(detail.tags || []), newTag];
    await setTagsMutation.mutateAsync({
      id: detail.id,
      tags: nextTags,
    });
  };

  const handleRemoveTag = async (tagToRemove: string) => {
    if (!detail) return;
    const nextTags = (detail.tags || []).filter(
      (t) => t.toLowerCase() !== tagToRemove.toLowerCase(),
    );
    await setTagsMutation.mutateAsync({
      id: detail.id,
      tags: nextTags,
    });
  };

  async function handleResolve(sourceKind: "managed" | "harness", observedHarness: string): Promise<void> {
    setResolveError("");
    setResolvePending(true);
    try {
      await onResolveConfig({
        sourceKind,
        observedHarness,
        harnesses: [observedHarness],
      });
    } catch (err) {
      setResolveError(err instanceof Error ? err.message : "Reconciliation failed");
    } finally {
      setResolvePending(false);
    }
  }

  return (
    <Dialog.Root
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="dialog-overlay" />
        <Dialog.Content className="detail-sheet permission-detail-modal" aria-describedby="permission-detail-desc">
          <div id="permission-detail-desc" className="u-visually-hidden">
            Permission detail panel showing permission specs and enabled status across harnesses.
          </div>
          
          <DetailHeader
            title={
              <h2 id={headingId} className="skill-detail__title">
                {displayName}
                {detail?.kind === "managed" ? (
                  <button
                    type="button"
                    className={`skill-star-btn ${isStarred ? "skill-star-btn--active" : ""}`}
                    aria-label={isStarred ? `Unstar ${displayName}` : `Star ${displayName}`}
                    onClick={handleToggleStar}
                  >
                    <Star
                      size={16}
                      className={`skill-star-icon ${isStarred ? "skill-star-icon--filled" : ""}`}
                    />
                  </button>
                ) : null}
              </h2>
            }
            closeLabel={copy.detail.close}
            onClose={onClose}
          />

          {errorMessage ? <ErrorBanner message={errorMessage} /> : null}
          {resolveError ? <ErrorBanner message={resolveError} onDismiss={() => setResolveError("")} /> : null}

          {detailQuery.isPending ? (
            <div className="panel-state">
              <LoadingSpinner label={copy.detail.loading} />
            </div>
          ) : detail ? (
            <div className="detail-sheet__body">
              <DetailSection heading={copy.detail.about}>
                <dl className="detail-sheet__description-list">
                  {spec?.description ? (
                    <div className="description-list-item description-list-item--full">
                      <dt className="description-list-item__term">Description</dt>
                      <dd className="description-list-item__definition">{spec.description}</dd>
                    </div>
                  ) : null}
                  <div className="description-list-item">
                    <dt className="description-list-item__term">{copy.detail.decision}</dt>
                    <dd className="description-list-item__definition">{spec?.decision}</dd>
                  </div>
                  <div className="description-list-item">
                    <dt className="description-list-item__term">{copy.detail.scope}</dt>
                    <dd className="description-list-item__definition">{spec?.scope}</dd>
                  </div>
                  {spec?.pattern ? (
                    <div className="description-list-item description-list-item--full">
                      <dt className="description-list-item__term">{copy.detail.pattern}</dt>
                      <dd className="description-list-item__definition">
                        <code>{spec.pattern}</code>
                      </dd>
                    </div>
                  ) : null}
                </dl>
              </DetailSection>

              {detail.kind === "managed" ? (
                <DetailSection heading="Tags">
                  <DetailTags
                    tags={detail.tags || []}
                    knownTags={knownTags}
                    canEdit={true}
                    onAddTag={handleAddTag}
                    onRemoveTag={handleRemoveTag}
                    disabled={setTagsMutation.isPending}
                  />
                </DetailSection>
              ) : null}

              <DetailSection heading={copy.detail.bindings}>
                <div className="detail-sheet__bindings">
                  {columns.map((column) => {
                    const binding = detail.sightings.find((s) => s.harness === column.harness);
                    const state = binding?.state ?? "missing";
                    const pending = pendingPerHarness.has(column.harness) || isServerPending;
                    const canWriteConfig = isPermissionsHarnessAddressable(column);

                    const stateLabel = () => {
                      if (state === "managed") return "Applied";
                      if (state === "drifted") return "Differs";
                      if (state === "unmanaged") return "Untracked";
                      return "Not applied";
                    };

                    const stateTone = () => {
                      if (state === "managed") return "enabled";
                      if (state === "drifted" || state === "unmanaged") return "warning";
                      return "disabled";
                    };

                    return (
                      <div
                        key={column.harness}
                        className="detail-sheet__binding-row"
                        data-state={state}
                        data-pending={pending || undefined}
                      >
                        <DetailBindingIdentity
                          harness={column.harness}
                          label={column.label}
                          logoKey={column.logoKey}
                          statusLabel={stateLabel()}
                          tone={stateTone()}
                          visibleStatus={state === "drifted" ? "Differs" : null}
                          detail={state === "drifted" ? binding?.driftDetail : null}
                        />
                        <div className="detail-sheet__binding-actions">
                          {state === "missing" ? (
                            <button
                              type="button"
                              className={detail.canEnable && canWriteConfig ? "action-pill action-pill--accent" : "action-pill"}
                              onClick={() => {
                                if (detail.canEnable && canWriteConfig) onEnableHarness(column.harness);
                              }}
                              disabled={pending || !detail.canEnable || !canWriteConfig}
                            >
                              {pending ? <Loader2 size={12} className="card-action-spinner" aria-hidden="true" /> : null}
                              {detail.canEnable && canWriteConfig ? "Apply" : "Unavailable"}
                            </button>
                          ) : null}

                          {state === "managed" ? (
                            <button
                              type="button"
                              className="action-pill action-pill--danger"
                              onClick={() => onDisableHarness(column.harness)}
                              disabled={pending}
                            >
                              {pending ? <Loader2 size={12} className="card-action-spinner" aria-hidden="true" /> : null}
                              Remove
                            </button>
                          ) : null}

                          {state === "drifted" ? (
                            <div style={{ display: "flex", gap: "4px" }}>
                              <button
                                type="button"
                                className="action-pill action-pill--accent"
                                onClick={() => handleResolve("managed", column.harness)}
                                disabled={pending || resolvePending}
                              >
                                Keep central
                              </button>
                              <button
                                type="button"
                                className="action-pill"
                                onClick={() => handleResolve("harness", column.harness)}
                                disabled={pending || resolvePending}
                              >
                                Take harness's
                              </button>
                            </div>
                          ) : null}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </DetailSection>

              <div className="detail-sheet__footer-actions">
                <button
                  type="button"
                  className="action-pill action-pill--danger-outline"
                  onClick={onUninstall}
                  disabled={isUninstalling || isServerPending}
                >
                  <Trash2 size={14} className="action-pill__icon" />
                  {copy.detail.uninstall}
                </button>
              </div>
            </div>
          ) : null}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
