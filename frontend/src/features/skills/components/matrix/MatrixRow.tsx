import { CardSelectCheckbox } from "../../../../components/cards/CardSelectCheckbox";
import { OverflowTooltipText } from "../../../../components/ui/OverflowTooltipText";
import { HarnessChipStack } from "../cards/HarnessChipStack";
import { cellActionKey } from "../../model/pending";
import type { CellActionKey } from "../../model/pending";
import type { StructuralSkillAction } from "../../model/pending";
import type {
  HarnessCell as HarnessCellType,
  HarnessColumn,
  SkillListRow,
} from "../../model/types";
import { SkillMatrixHarnessCell } from "./SkillMatrixHarnessCell";
import { skillStatusConcept } from "../../../../lib/product-language";

interface MatrixRowProps {
  row: SkillListRow;
  harnessColumns: HarnessColumn[];
  checked: boolean;
  selected: boolean;
  pendingToggleKeys: ReadonlySet<CellActionKey>;
  onOpenSkill: (skillRef: string) => void;
  onToggleChecked: (skillRef: string) => void;
  onToggleCell: (row: SkillListRow, cell: HarnessCellType) => void;
  onManageSkill?: (skillRef: string) => void;
  pendingStructuralActions?: ReadonlyMap<string, StructuralSkillAction>;
  untrackedSelectionOnly?: boolean;
}

function findCell(row: SkillListRow, harness: string): HarnessCellType {
  return (
    row.cells.find((cell) => cell.harness === harness) ?? {
      harness,
      label: harness,
      state: "empty",
      interactive: false,
    }
  );
}

function countEnabled(row: SkillListRow): number {
  let count = 0;
  for (const cell of row.cells) if (cell.state === "enabled") count += 1;
  return count;
}

export function MatrixRow({
  row,
  harnessColumns,
  checked,
  selected,
  pendingToggleKeys,
  onOpenSkill,
  onToggleChecked,
  onToggleCell,
  onManageSkill,
  pendingStructuralActions,
  untrackedSelectionOnly = false,
}: MatrixRowProps) {
  const enabledCount = countEnabled(row);
  const totalCount = harnessColumns.length;
  const isUntracked = skillStatusConcept(row.displayStatus) === "needsReview";
  // Skills keeps managed selection for its enable/disable/delete bar while
  // limiting the adopt selection to eligible untracked rows.
  const selectable = untrackedSelectionOnly ? (!isUntracked || row.actions.canManage) : true;
  const pendingStructuralAction = pendingStructuralActions?.get(row.skillRef) ?? null;

  return (
    <tr
      className="matrix-table__row"
      data-selected={selected ? "true" : undefined}
      data-checked={checked ? "true" : undefined}
    >
      <td className="matrix-table__cell matrix-table__cell--checkbox">
        {selectable ? (
          <CardSelectCheckbox
            checked={checked}
            label={checked ? `Deselect ${row.name}` : `Select ${row.name}`}
            onToggle={() => onToggleChecked(row.skillRef)}
            disabled={pendingStructuralAction !== null}
          />
        ) : null}
      </td>

      <td
        className="matrix-table__cell matrix-table__cell--identity"
        onClick={() => onOpenSkill(row.skillRef)}
      >
        <div className="matrix-table__name-row">
          <OverflowTooltipText as="span" className="matrix-table__name-text">
            {row.name}
          </OverflowTooltipText>
        </div>
        {row.description ? (
          <OverflowTooltipText as="p" className="matrix-table__description">
            {row.description}
          </OverflowTooltipText>
        ) : null}
      </td>

      {harnessColumns.map((column) => {
        const cell = findCell(row, column.harness);
        const pending = pendingToggleKeys.has(cellActionKey(row.skillRef, cell.harness));
        return (
          <td key={column.harness} className="matrix-table__cell matrix-table__cell--harness">
            <SkillMatrixHarnessCell
              cell={cell}
              skillName={row.name}
              pending={pending}
              untracked={isUntracked}
              onOpenSkill={() => onOpenSkill(row.skillRef)}
              onToggle={(next) => onToggleCell(row, next)}
            />
          </td>
        );
      })}

      <td className="matrix-table__cell matrix-table__cell--compact">
        <HarnessChipStack cells={row.cells} />
      </td>

      <td className="matrix-table__cell matrix-table__cell--coverage">
        {isUntracked ? (
          <button
            type="button"
            className="action-pill action-pill--accent permission-adopt-btn"
            disabled={!row.actions.canManage || pendingStructuralAction !== null}
            onClick={() => onManageSkill?.(row.skillRef)}
          >
            {pendingStructuralAction === "manage" ? <span className="card-action-spinner" aria-hidden="true" /> : null}
            Adopt
          </button>
        ) : (
          <span className="matrix-table__coverage" aria-label={`Active on ${enabledCount} of ${totalCount} harnesses`}>
            <span className="matrix-table__coverage-count">{enabledCount}</span>
            <span className="matrix-table__coverage-total" aria-hidden="true">
              {" / "}
              {totalCount}
            </span>
          </span>
        )}
      </td>
    </tr>
  );
}
