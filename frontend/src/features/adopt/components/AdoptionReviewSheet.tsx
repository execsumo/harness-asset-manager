import * as Dialog from "@radix-ui/react-dialog";
import { useMemo, useState } from "react";
import { LoadingSpinner } from "../../../components/LoadingSpinner";
import { useHomeDir } from "../../../lib/paths";
import { formatHomePath } from "../../../lib/paths/formatHomePath";
import { useApplyAdoptionMutation } from "../queries";
import type {
  AdoptionActionDto,
  AdoptionApplyResultDto,
  AdoptionPlanDto,
} from "../types";

interface AdoptionReviewSheetProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  plan: AdoptionPlanDto;
}

const FAMILY_LABELS: Record<string, string> = {
  skills: "Skills",
  agents: "Agents",
  slash_commands: "Slash Commands",
};

export function AdoptionReviewSheet({
  open,
  onOpenChange,
  plan,
}: AdoptionReviewSheetProps) {
  const home = useHomeDir();
  const applyMutation = useApplyAdoptionMutation();

  // Candidates for adoption: linkable and conflict actions
  const adoptableActions = useMemo(
    () => plan.actions.filter((a) => a.action === "link" || a.action === "conflict"),
    [plan.actions],
  );

  // Selected keys: default to all "link" actions, but NOT "conflict" actions
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(() => {
    const initial = new Set<string>();
    for (const a of adoptableActions) {
      if (a.action === "link") {
        initial.add(`${a.family}:${a.ref}:${a.harness}`);
      }
    }
    return initial;
  });

  const [results, setResults] = useState<Record<string, AdoptionApplyResultDto>>({});
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const selectedActions = useMemo(
    () =>
      adoptableActions.filter((a) =>
        selectedKeys.has(`${a.family}:${a.ref}:${a.harness}`),
      ),
    [adoptableActions, selectedKeys],
  );

  const grouped = useMemo(() => {
    const groups: Record<string, AdoptionActionDto[]> = {};
    for (const a of adoptableActions) {
      if (!groups[a.family]) {
        groups[a.family] = [];
      }
      groups[a.family].push(a);
    }
    return groups;
  }, [adoptableActions]);

  function toggleKey(key: string) {
    if (applyMutation.isPending) return;
    setSelectedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  }

  function selectAllLinkable() {
    if (applyMutation.isPending) return;
    const next = new Set<string>();
    for (const a of adoptableActions) {
      if (a.action === "link") {
        next.add(`${a.family}:${a.ref}:${a.harness}`);
      }
    }
    setSelectedKeys(next);
  }

  function deselectAll() {
    if (applyMutation.isPending) return;
    setSelectedKeys(new Set());
  }

  async function handleAdopt() {
    if (selectedActions.length === 0) return;
    setErrorMessage(null);

    const hasConflicts = selectedActions.some((a) => a.action === "conflict");
    try {
      const response = await applyMutation.mutateAsync({
        actions: selectedActions,
        allowConflicts: hasConflicts,
      });
      const resultMap: Record<string, AdoptionApplyResultDto> = {};
      for (const res of response.results) {
        resultMap[`${res.family}:${res.ref}:${res.harness}`] = res;
      }
      setResults(resultMap);
    } catch (err: unknown) {
      setErrorMessage(
        err instanceof Error ? err.message : "Failed to apply adoption actions",
      );
    }
  }

  const isAppliedDone = Object.keys(results).length > 0;

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="dialog-overlay" />
        <Dialog.Content
          className="dialog-content adoption-dialog"
          aria-describedby="adoption-dialog-desc"
        >
          <div className="dialog-header">
            <Dialog.Title className="dialog-title">
              Adopt Synced Assets
            </Dialog.Title>
            <p id="adoption-dialog-desc" className="dialog-description">
              Select assets from your synced store to create local bindings for installed harnesses.
            </p>
          </div>

          <div className="adoption-dialog__controls">
            <span>
              {selectedKeys.size} of {adoptableActions.length} selected
            </span>
            <div className="adoption-dialog__controls-links">
              <button
                type="button"
                className="adoption-link-btn"
                onClick={selectAllLinkable}
                disabled={applyMutation.isPending}
              >
                Select linkable
              </button>
              <button
                type="button"
                className="adoption-link-btn"
                onClick={deselectAll}
                disabled={applyMutation.isPending}
              >
                Deselect all
              </button>
            </div>
          </div>

          {errorMessage && (
            <div className="error-banner" style={{ margin: "12px 0" }}>
              <span className="error-banner__message">{errorMessage}</span>
            </div>
          )}

          <div className="adoption-dialog__body ui-scrollbar">
            {Object.entries(grouped).map(([family, items]) => (
              <div key={family} className="adoption-group">
                <div className="adoption-group__title">
                  {FAMILY_LABELS[family] ?? family} ({items.length})
                </div>
                {items.map((item) => {
                  const key = `${item.family}:${item.ref}:${item.harness}`;
                  const isChecked = selectedKeys.has(key);
                  const result = results[key];

                  return (
                    <div key={key} className="adoption-item-row">
                      <div className="adoption-item-row__left">
                        <input
                          type="checkbox"
                          id={`adopt-check-${key}`}
                          checked={isChecked}
                          onChange={() => toggleKey(key)}
                          disabled={applyMutation.isPending || !!result}
                        />
                        <label
                          htmlFor={`adopt-check-${key}`}
                          className="adoption-item-row__label"
                        >
                          <span className="adoption-item-row__name">
                            {item.displayName}
                          </span>
                          <span className="adoption-item-row__target">
                            {formatHomePath(item.targetPath, home)}
                          </span>
                        </label>
                      </div>

                      <div className="adoption-item-row__right">
                        <span className="adoption-badge adoption-badge--harness">
                          {item.harness}
                        </span>

                        {item.action === "conflict" && !result && (
                          <span
                            className="adoption-badge adoption-badge--conflict"
                            title={item.detail ?? "Target occupied"}
                          >
                            Conflict
                          </span>
                        )}

                        {result && result.status === "applied" && (
                          <span className="adoption-status-chip adoption-status-chip--applied">
                            ✓ Applied
                          </span>
                        )}

                        {result && result.status === "failed" && (
                          <span
                            className="adoption-status-chip adoption-status-chip--failed"
                            title={result.error ?? "Failed"}
                          >
                            ✗ {result.error || "Failed"}
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>

          <div className="dialog-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => onOpenChange(false)}
              disabled={applyMutation.isPending}
            >
              {isAppliedDone ? "Close" : "Cancel"}
            </button>

            {!isAppliedDone && (
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleAdopt}
                disabled={selectedKeys.size === 0 || applyMutation.isPending}
              >
                {applyMutation.isPending ? (
                  <>
                    <LoadingSpinner />
                    <span>Adopting...</span>
                  </>
                ) : (
                  `Adopt Selected (${selectedKeys.size})`
                )}
              </button>
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
