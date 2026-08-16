import {
  MatrixHarnessCellTarget,
  MatrixHarnessIcon,
} from "../../../../components/matrix";
import { UiTooltip } from "../../../../components/ui/UiTooltip";
import type { HarnessCell as HarnessCellType } from "../../model/types";

interface SkillMatrixHarnessCellProps {
  cell: HarnessCellType;
  skillName: string;
  pending?: boolean;
  untracked?: boolean;
  onOpenSkill?: () => void;
  onToggle: (cell: HarnessCellType) => void;
}

export function SkillMatrixHarnessCell({
  cell,
  skillName,
  pending = false,
  untracked = false,
  onOpenSkill,
  onToggle,
}: SkillMatrixHarnessCellProps) {
  if (untracked && cell.state === "found" && onOpenSkill) {
    return (
      <UiTooltip content={`Found in ${cell.label} config`}>
        <MatrixHarnessCellTarget
          ariaLabel={`Open details for ${skillName} on ${cell.label}`}
          state="observed"
          onClick={(event) => {
            event.stopPropagation();
            onOpenSkill();
          }}
        >
          <MatrixHarnessIcon label={cell.label} logoKey={cell.logoKey} harness={cell.harness} />
        </MatrixHarnessCellTarget>
      </UiTooltip>
    );
  }

  // The inventory keeps undetected harnesses in the matrix so the column set
  // stays stable, but those cells are status-only. `interactive` already
  // includes harness availability; do not let an unavailable managed cell
  // look actionable just because its persisted state is "disabled".
  if (!cell.interactive || cell.state === "empty" || cell.state === "found") {
    return (
      <span
        className="matrix-harness-target"
        data-state={cell.interactive ? "empty" : "disabled"}
        aria-label={!cell.interactive && cell.state === "disabled" ? `${cell.label} unavailable` : undefined}
        aria-hidden={cell.interactive ? true : undefined}
      >
        —
      </span>
    );
  }

  const isEnabled = cell.state === "enabled";
  const action = isEnabled ? "Disable" : "Enable";

  const button = (
    <MatrixHarnessCellTarget
      ariaLabel={`${action} ${skillName} on ${cell.label}`}
      ariaPressed={isEnabled}
      state={cell.state}
      pending={pending}
      disabled={pending}
      onClick={(event) => {
        event.stopPropagation();
        onToggle(cell);
      }}
    >
      <MatrixHarnessIcon
        label={cell.label}
        logoKey={cell.logoKey}
        harness={cell.harness}
      />
    </MatrixHarnessCellTarget>
  );

  return (
    <UiTooltip content={`${cell.label} — ${isEnabled ? "enabled" : "disabled"}`}>
      {button}
    </UiTooltip>
  );
}
