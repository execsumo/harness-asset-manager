import { Loader2 } from "lucide-react";

import {
  DetailBindingIdentity,
  type DetailBindingTone,
} from "../../../../components/detail/DetailBindingIdentity";
import type { StructuralSkillAction } from "../../model/pending";
import type { HarnessCell, HarnessCellState } from "../../model/types";
import {
  hermesBotLabel,
  hermesBotScopes,
  hermesBotScopesFromLocations,
} from "../../model/hermesTargets";

interface SkillDetailHarnessMatrixProps {
  skillName: string;
  cells: HarnessCell[];
  linkedTargets?: string[];
  locations?: readonly { harness?: string | null }[];
  pendingToggleHarnesses: ReadonlySet<string>;
  pendingStructuralAction: StructuralSkillAction | null;
  onToggleCell: (cell: HarnessCell) => void;
}

const STATE_LABEL: Record<HarnessCellState, string> = {
  enabled: "Enabled",
  disabled: "Disabled",
  found: "Found in harness",
  empty: "Not present",
};

const STATE_TONE: Record<HarnessCellState, DetailBindingTone> = {
  enabled: "enabled",
  disabled: "disabled",
  found: "warning",
  empty: "disabled",
};

function visibleStateLabel(state: HarnessCellState): string | null {
  return state === "found" ? STATE_LABEL[state] : null;
}

export function SkillDetailHarnessMatrix({
  skillName,
  cells,
  linkedTargets,
  locations,
  pendingToggleHarnesses,
  pendingStructuralAction,
  onToggleCell,
}: SkillDetailHarnessMatrixProps) {
  if (cells.length === 0) {
    return null;
  }
  const structuralLocked = pendingStructuralAction !== null;

  return (
    <div className="detail-sheet__bindings" aria-label={`Harness access for ${skillName}`}>
      {cells.map((cell) => {
        const pending = pendingToggleHarnesses.has(cell.harness);
        // Bound Bots come from recorded targets; an unmanaged copy a Bot created
        // for itself has no binding yet, so fall back to where it was found.
        const hermesBotScopeList = cell.harness === "hermes"
          ? Array.from(new Set([
              ...hermesBotScopes(linkedTargets),
              ...hermesBotScopesFromLocations(locations),
            ])).sort()
          : [];
        const hermesBots = hermesBotScopeList.map(hermesBotLabel);
        return (
          <div
            key={cell.harness}
            className="detail-sheet__binding-row"
            data-state={cell.state}
            data-pending={pending || undefined}
          >
            <DetailBindingIdentity
              harness={cell.harness}
              label={cell.label}
              logoKey={cell.logoKey}
              statusLabel={STATE_LABEL[cell.state]}
              tone={STATE_TONE[cell.state]}
              visibleStatus={visibleStateLabel(cell.state)}
              trailing={hermesBots.length > 0 ? (
                <div
                  className="detail-sheet__binding-targets"
                  aria-label={`Hermes Bots: ${hermesBots.join(", ")}`}
                >
                  {hermesBots.map((bot) => (
                    <span key={bot} className="detail-sheet__binding-target">
                      {bot}
                    </span>
                  ))}
                </div>
              ) : null}
            />
            <div className="detail-sheet__binding-actions">
              <HarnessCellAction
                skillName={skillName}
                cell={cell}
                pending={pending}
                disabled={structuralLocked}
                onToggleCell={onToggleCell}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

interface HarnessCellActionProps {
  skillName: string;
  cell: HarnessCell;
  pending: boolean;
  disabled: boolean;
  onToggleCell: (cell: HarnessCell) => void;
}

function HarnessCellAction({
  skillName,
  cell,
  pending,
  disabled,
  onToggleCell,
}: HarnessCellActionProps) {
  if (!cell.interactive) {
    if (cell.state === "found") {
      return (
        <span className="detail-sheet__binding-hint">
          Adopt this skill to manage it
        </span>
      );
    }
    return null;
  }

  if (cell.state === "enabled") {
    return (
      <button
        type="button"
        className="action-pill action-pill--danger"
        disabled={disabled || pending}
        onClick={() => onToggleCell(cell)}
        aria-label={`Disable ${skillName} for ${cell.label}`}
      >
        {pending ? (
          <Loader2 size={12} className="card-action-spinner" aria-hidden="true" />
        ) : null}
        Disable
      </button>
    );
  }

  if (cell.state === "disabled") {
    return (
      <button
        type="button"
        className="action-pill action-pill--accent"
        disabled={disabled || pending}
        onClick={() => onToggleCell(cell)}
        aria-label={`Enable ${skillName} for ${cell.label}`}
      >
        {pending ? (
          <Loader2 size={12} className="card-action-spinner" aria-hidden="true" />
        ) : null}
        Enable
      </button>
    );
  }

  return null;
}
