import { SelectionMenu } from "../../../components/ui/SelectionMenu";
import type { HooksStatusFilter } from "../model/selectors";
import { useHooksCopy } from "../i18n";

const OPTIONS: HooksStatusFilter[] = ["all", "enabled", "all-harnesses", "unbound", "drifted", "untracked"];

interface HooksFilterMenuProps {
  pill: HooksStatusFilter;
  counts: Record<HooksStatusFilter, number>;
  onChange: (next: HooksStatusFilter) => void;
}

export function HooksFilterMenu({ pill, counts, onChange }: HooksFilterMenuProps) {
  const copy = useHooksCopy();
  const options = OPTIONS.map((value) => ({
    value,
    label: pillLabel(copy, value),
    meta: counts[value],
  }));

  return (
    <SelectionMenu
      value={pill}
      options={options}
      active={pill !== "all"}
      ariaLabel={copy.inUse.filters.aria(pillLabel(copy, pill))}
      onChange={onChange}
    />
  );
}

function pillLabel(copy: ReturnType<typeof useHooksCopy>, value: HooksStatusFilter): string {
  if (value === "all") return copy.inUse.filters.all;
  if (value === "enabled") return copy.inUse.filters.enabled;
  if (value === "all-harnesses") return copy.inUse.filters.allHarnesses;
  if (value === "unbound") return copy.inUse.filters.unbound;
  if (value === "drifted") return copy.inUse.filters.drifted;
  return copy.inUse.filters.untracked;
}
