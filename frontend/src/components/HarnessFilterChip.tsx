import { X } from "lucide-react";

import { useCommonCopy } from "../i18n";

interface HarnessFilterChipProps {
  label: string;
  onClear: () => void;
}

/**
 * Compact indicator for a URL-backed `?harness=` deep-link filter.
 * Rendered inside a page's FilterBar trailing slot.
 */
export function HarnessFilterChip({ label, onClear }: HarnessFilterChipProps) {
  const common = useCommonCopy();

  return (
    <span className="harness-filter-chip">
      <span className="harness-filter-chip__label">{label}</span>
      <button
        type="button"
        className="harness-filter-chip__clear"
        aria-label={`${common.actions.clearFilters}: ${label}`}
        onClick={onClear}
      >
        <X size={12} strokeWidth={2.25} aria-hidden="true" />
      </button>
    </span>
  );
}
