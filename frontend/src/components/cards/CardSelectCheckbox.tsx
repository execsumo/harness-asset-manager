import { type KeyboardEvent, type PointerEvent as ReactPointerEvent } from "react";

interface CardSelectCheckboxProps {
  checked: boolean;
  indeterminate?: boolean;
  label: string;
  onToggle: () => void;
  disabled?: boolean;
}

interface SelectAllCheckboxProps {
  selectedCount: number;
  totalCount: number;
  onToggle: () => void;
  label: string;
}

/**
 * Square 14×14 select checkbox used by asset rows and matrix headers.
 * Stops propagation so it doesn't fire the row's click-to-open handler.
 */
export function CardSelectCheckbox({
  checked,
  indeterminate = false,
  label,
  onToggle,
  disabled = false,
}: CardSelectCheckboxProps) {
  function handleClick(event: ReactPointerEvent<HTMLSpanElement>): void {
    event.stopPropagation();
    if (disabled) return;
    onToggle();
  }
  function handleKey(event: KeyboardEvent<HTMLSpanElement>): void {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    event.stopPropagation();
    if (disabled) return;
    onToggle();
  }

  return (
    <span
      className="card-select-checkbox"
      role="checkbox"
      aria-checked={indeterminate ? "mixed" : checked}
      aria-label={label}
      aria-disabled={disabled || undefined}
      data-state={indeterminate ? "mixed" : checked ? "checked" : "unchecked"}
      tabIndex={disabled ? -1 : 0}
      onPointerDown={(event) => event.stopPropagation()}
      onClick={handleClick}
      onKeyDown={handleKey}
    >
      {indeterminate ? (
        <svg width="10" height="10" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path
            d="M3 8h10"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </svg>
      ) : checked ? (
        <svg width="10" height="10" viewBox="0 0 16 16" fill="none" aria-hidden="true">
          <path
            d="M3 8.5 6.5 12 13 5"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      ) : null}
    </span>
  );
}

export function SelectAllCheckbox({
  selectedCount,
  totalCount,
  onToggle,
  label,
}: SelectAllCheckboxProps) {
  const allSelected = totalCount > 0 && selectedCount === totalCount;
  const indeterminate = selectedCount > 0 && !allSelected;

  return (
    <CardSelectCheckbox
      checked={allSelected}
      indeterminate={indeterminate}
      label={allSelected ? `Deselect all ${label}` : `Select all ${label}`}
      onToggle={onToggle}
      disabled={totalCount === 0}
    />
  );
}
