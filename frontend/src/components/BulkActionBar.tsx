import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import * as Popover from "@radix-ui/react-popover";
import { Check, ChevronDown, CircleSlash2, Star, Trash2, X } from "lucide-react";

import { BulkTagPopover } from "./BulkTagPopover";
import { BulkAgentPopover } from "./BulkAgentPopover";
import { ConfirmActionDialog } from "./ConfirmActionDialog";
import { LoadingSpinner } from "./LoadingSpinner";
import { useCommonCopy } from "../i18n";

export type MultiSelectAction = "enable-all" | "disable-all" | "delete" | "star" | "tag" | "adopt" | "attach-agents";
export type BulkHarnessState = "all" | "none" | "mixed";

export interface BulkHarnessOption {
  harness: string;
  label: string;
  state?: BulkHarnessState;
}

interface BulkActionBarProps {
  selectedCount: number;
  pending: MultiSelectAction | null;
  onClear: () => void;
  onEnableAll?: () => Promise<void>;
  onDisableAll?: () => Promise<void>;
  harnessOptions?: readonly BulkHarnessOption[];
  onEnableHarness?: (harness: string) => Promise<void>;
  onDisableHarness?: (harness: string) => Promise<void>;
  onDelete: () => Promise<void>;
  extraActions?: ReactNode;
  showHarnessActions?: boolean;
  showDestructiveAction?: boolean;
  onStarSelected?: () => Promise<void>;
  starLabel?: string;
  onTagSelected?: (tags: string[]) => Promise<void>;
  knownTags?: string[];
  onAgentSelected?: (agentRefs: string[], mode: "attach" | "detach") => Promise<void>;
  knownAgents?: { ref: string; name: string }[];
  destructive: {
    /** Button aria-label + confirm button text (e.g. "Delete" / "Uninstall"). */
    actionLabel: string;
    /** Confirm dialog title (e.g. "Delete 3 skills?"). */
    confirmTitle: string;
    /** Confirm dialog body paragraph. */
    confirmDescription: string;
    /** Optional quieter secondary note below the main body. */
    confirmNote?: string;
  };
}

export function BulkActionBar({
  selectedCount,
  pending,
  onClear,
  onEnableAll,
  onDisableAll,
  harnessOptions,
  onEnableHarness,
  onDisableHarness,
  onDelete,
  extraActions,
  showHarnessActions = true,
  showDestructiveAction = true,
  onStarSelected,
  starLabel,
  onTagSelected,
  knownTags,
  onAgentSelected,
  knownAgents,
  destructive,
}: BulkActionBarProps) {
  const [visible, setVisible] = useState(selectedCount > 0);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const common = useCommonCopy();

  useEffect(() => {
    if (selectedCount > 0) {
      setVisible(true);
    } else {
      const timer = window.setTimeout(() => setVisible(false), 220);
      return () => window.clearTimeout(timer);
    }
    return undefined;
  }, [selectedCount]);

  if (!visible) {
    return null;
  }

  const disabled = pending !== null;
  const active = selectedCount > 0;

  return (
    <>
      <div className="bulk-dock" aria-hidden={!active}>
        <div className="bulk-dock__fade" />
        <div
          className="bulk-bar"
          data-state={active ? "open" : "closed"}
          role="toolbar"
          aria-label={common.bulk.ariaLabel}
        >
          <div className="bulk-bar__group">
            <span className="bulk-bar__count">
              {common.bulk.selected(selectedCount)}
            </span>
            <button
              type="button"
              className="bulk-bar__clear"
              onClick={onClear}
              disabled={disabled}
              aria-label={common.actions.clearSelection}
            >
              <X size={14} />
            </button>
          </div>

          <span className="bulk-bar__divider" aria-hidden="true" />

          <div className="bulk-bar__group">
            {extraActions}
            {onStarSelected ? (
              <button
                type="button"
                className="bulk-bar__action"
                onClick={() => void onStarSelected()}
                disabled={disabled}
              >
                {pending === "star" ? (
                  <LoadingSpinner size="sm" label="Starring" />
                ) : (
                  <Star size={15} />
                )}
                {starLabel ?? "Star"}
              </button>
            ) : null}
            {onTagSelected ? (
              <BulkTagPopover
                knownTags={knownTags}
                onApply={onTagSelected}
                disabled={disabled}
                pending={pending === "tag"}
              />
            ) : null}
            {onAgentSelected ? (
              <BulkAgentPopover
                knownAgents={knownAgents}
                onApply={onAgentSelected}
                disabled={disabled}
                pending={pending === "attach-agents"}
              />
            ) : null}
            {showHarnessActions && onEnableAll && onDisableAll ? (
              <>
                <button
                  type="button"
                  className="bulk-bar__action"
                  onClick={() => void onEnableAll()}
                  disabled={disabled}
                >
                  {pending === "enable-all" ? (
                    <LoadingSpinner size="sm" label={common.actions.enabling} />
                  ) : (
                    <Check size={15} />
                  )}
                  {common.actions.enableAll}
                </button>
                <button
                  type="button"
                  className="bulk-bar__action"
                  onClick={() => void onDisableAll()}
                  disabled={disabled}
                >
                  {pending === "disable-all" ? (
                    <LoadingSpinner size="sm" label={common.actions.disabling} />
                  ) : (
                    <CircleSlash2 size={15} />
                  )}
                  {common.actions.disableAll}
                </button>
              </>
            ) : null}
            {showHarnessActions && harnessOptions && harnessOptions.length > 0 && onEnableHarness && onDisableHarness ? (
              <BulkHarnessMenu
                options={harnessOptions}
                pending={pending === "enable-all" || pending === "disable-all"}
                disabled={disabled}
                onEnable={onEnableHarness}
                onDisable={onDisableHarness}
              />
            ) : null}
          </div>

          {showDestructiveAction ? (
            <>
              <span className="bulk-bar__divider" aria-hidden="true" />

              <button
                type="button"
                className="bulk-bar__danger"
                onClick={() => setConfirmOpen(true)}
                disabled={disabled}
                aria-label={common.bulk.selectedAction(destructive.actionLabel, selectedCount)}
              >
                {pending === "delete" ? (
                  <LoadingSpinner size="sm" label={destructive.actionLabel} />
                ) : (
                  <Trash2 size={15} />
                )}
              </button>
            </>
          ) : null}
        </div>
      </div>

      <ConfirmActionDialog
        open={confirmOpen}
        title={destructive.confirmTitle}
        description={destructive.confirmDescription}
        note={destructive.confirmNote}
        confirmLabel={destructive.actionLabel}
        pendingLabel={destructive.actionLabel}
        isPending={pending === "delete"}
        onOpenChange={setConfirmOpen}
        onConfirm={async () => {
          setConfirmOpen(false);
          await onDelete();
        }}
      />
    </>
  );
}

function BulkHarnessMenu({
  options,
  pending,
  disabled,
  onEnable,
  onDisable,
}: {
  options: readonly BulkHarnessOption[];
  pending: boolean;
  disabled: boolean;
  onEnable: (harness: string) => Promise<void>;
  onDisable: (harness: string) => Promise<void>;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [staged, setStaged] = useState<Map<string, boolean>>(new Map());

  useEffect(() => {
    if (!isOpen) {
      setStaged(new Map());
    }
  }, [isOpen]);

  const handleToggle = (harness: string, checked: boolean) => {
    setStaged((current) => {
      const next = new Map(current);
      next.set(harness, checked);
      return next;
    });
  };

  const handleApply = async () => {
    for (const [harness, shouldEnable] of staged) {
      if (shouldEnable) await onEnable(harness);
      else await onDisable(harness);
    }
    setIsOpen(false);
  };

  return (
    <Popover.Root
      open={isOpen}
      onOpenChange={(open) => {
        if (disabled && open) return;
        setIsOpen(open);
      }}
    >
      <Popover.Trigger asChild>
        <button
          type="button"
          className="bulk-bar__action"
          disabled={disabled}
          aria-label="Harnesses"
        >
          {pending ? <LoadingSpinner size="sm" label="Harnesses" /> : <Check size={15} />}
          Harnesses
          <ChevronDown size={13} aria-hidden="true" />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content className="ui-popup bulk-harness-popover" align="end" sideOffset={8}>
          <div className="bulk-harness-popover__header">
            <h3 className="bulk-harness-popover__title">Harnesses</h3>
            <p className="bulk-harness-popover__description">
              Mixed harnesses stay unchanged unless toggled.
            </p>
          </div>
          <ul className="bulk-harness-popover__list">
            {options.map((option) => {
              const state = option.state ?? "mixed";
              const checked = staged.get(option.harness) ?? state === "all";
              const indeterminate = !staged.has(option.harness) && state === "mixed";
              return (
                <li key={option.harness}>
                  <label className="bulk-harness-popover__item" data-state={state}>
                    <TriStateHarnessCheckbox
                      label={option.label}
                      checked={checked}
                      indeterminate={indeterminate}
                      disabled={pending}
                      onChange={(nextChecked) => handleToggle(option.harness, nextChecked)}
                    />
                    <span className="bulk-harness-popover__label">{option.label}</span>
                    <span className="bulk-harness-popover__state">{harnessStateLabel(state)}</span>
                  </label>
                </li>
              );
            })}
          </ul>
          <div className="bulk-harness-popover__footer">
            <button
              type="button"
              className="action-pill action-pill--sm"
              onClick={() => setIsOpen(false)}
              disabled={pending}
            >
              Cancel
            </button>
            <button
              type="button"
              className="action-pill action-pill--sm action-pill--accent"
              onClick={() => void handleApply()}
              disabled={pending}
            >
              {pending ? <LoadingSpinner size="sm" label="Applying" /> : "Apply"}
            </button>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}

function TriStateHarnessCheckbox({
  label,
  checked,
  indeterminate,
  disabled,
  onChange,
}: {
  label: string;
  checked: boolean;
  indeterminate: boolean;
  disabled: boolean;
  onChange: (checked: boolean) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.indeterminate = indeterminate;
    }
  }, [indeterminate]);

  return (
    <input
      ref={inputRef}
      type="checkbox"
      className="bulk-harness-popover__checkbox"
      checked={checked}
      disabled={disabled}
      aria-label={label}
      onChange={(event) => onChange(event.currentTarget.checked)}
    />
  );
}

function harnessStateLabel(state: BulkHarnessState): string {
  if (state === "all") return "All selected";
  if (state === "none") return "None selected";
  return "Mixed";
}
