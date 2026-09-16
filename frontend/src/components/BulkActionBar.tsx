import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import * as Popover from "@radix-ui/react-popover";
import { Check, ChevronDown, CircleSlash2, Star, Trash2, X } from "lucide-react";

import { BulkTagPopover } from "./BulkTagPopover";
import { ConfirmActionDialog } from "./ConfirmActionDialog";
import { LoadingSpinner } from "./LoadingSpinner";
import { useCommonCopy } from "../i18n";

export type MultiSelectAction = "enable-all" | "disable-all" | "delete" | "star" | "tag" | "adopt";

export interface BulkHarnessOption {
  harness: string;
  label: string;
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
                {starLabel ?? "Star selected"}
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
              <>
                <BulkHarnessMenu
                  action="enable"
                  options={harnessOptions}
                  pending={pending === "enable-all"}
                  disabled={disabled}
                  onSelect={onEnableHarness}
                />
                <BulkHarnessMenu
                  action="disable"
                  options={harnessOptions}
                  pending={pending === "disable-all"}
                  disabled={disabled}
                  onSelect={onDisableHarness}
                />
              </>
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
  action,
  options,
  pending,
  disabled,
  onSelect,
}: {
  action: "enable" | "disable";
  options: readonly BulkHarnessOption[];
  pending: boolean;
  disabled: boolean;
  onSelect: (harness: string) => Promise<void>;
}) {
  const isEnable = action === "enable";
  const label = isEnable ? "Enable on" : "Disable on";
  const Icon = isEnable ? Check : CircleSlash2;

  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button
          type="button"
          className="bulk-bar__action"
          disabled={disabled}
          aria-label={`${label} a harness`}
        >
          {pending ? <LoadingSpinner size="sm" label={label} /> : <Icon size={15} />}
          {label}
          <ChevronDown size={13} aria-hidden="true" />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content className="ui-popup ui-popup--menu ui-menu" align="end" sideOffset={8}>
          <ul className="ui-menu__list">
            <li className="ui-menu__section-label">
              {isEnable ? "Enable selected on" : "Disable selected on"}
            </li>
            {options.map((option) => (
              <li key={option.harness}>
                <Popover.Close asChild>
                  <button
                    type="button"
                    className="ui-menu__item"
                    aria-label={`${label} ${option.label}`}
                    onClick={() => void onSelect(option.harness)}
                  >
                    <span className="ui-menu__icon" aria-hidden="true">
                      <Icon size={14} />
                    </span>
                    <span className="ui-menu__label">{option.label}</span>
                  </button>
                </Popover.Close>
              </li>
            ))}
          </ul>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
