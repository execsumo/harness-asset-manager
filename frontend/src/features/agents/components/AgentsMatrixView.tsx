import { AlertTriangle, Loader2 } from "lucide-react";

import { CardSelectCheckbox } from "../../../components/cards/CardSelectCheckbox";
import {
  MatrixHarnessCellTarget,
  MatrixHarnessHeader,
  MatrixHarnessIcon,
  MatrixTable,
} from "../../../components/matrix";
import { OverflowTooltipText } from "../../../components/ui/OverflowTooltipText";
import { UiTooltip } from "../../../components/ui/UiTooltip";
import type { AgentInventoryDto, AgentInventoryEntryDto } from "../api/types";
import { matrixCellFor, type AgentMatrixCellModel } from "../model/selectors";

interface AgentsMatrixViewProps {
  entries: AgentInventoryEntryDto[];
  columns: AgentInventoryDto["columns"];
  pendingAgentKeys: ReadonlySet<string>;
  pendingPerHarnessKeys: ReadonlySet<string>;
  checkedRefs: ReadonlySet<string>;
  onOpenDetail: (ref: string) => void;
  onToggleChecked: (ref: string) => void;
  onEnableHarness: (ref: string, harness: string) => void;
  onDisableHarness: (ref: string, harness: string) => void;
  onAdopt: (ref: string) => void;
}

export function AgentsMatrixView({
  entries,
  columns,
  pendingAgentKeys,
  pendingPerHarnessKeys,
  checkedRefs,
  onOpenDetail,
  onToggleChecked,
  onEnableHarness,
  onDisableHarness,
  onAdopt,
}: AgentsMatrixViewProps) {
  return (
    <MatrixTable
      ariaLabel="Agents Matrix"
      harnessColumnWidth="52px"
      compactColumnWidth="140px"
      coverageColumnWidth="96px"
      minWidth="800px"
    >
      <thead className="matrix-table__head">
        <tr>
          <th className="matrix-table__th matrix-table__th--checkbox" aria-label="Select Column" />
          <th className="matrix-table__th matrix-table__th--identity">Agent Name</th>
          {columns.map((column) => (
            <MatrixHarnessHeader
              key={column.harness}
              label={column.label}
              logoKey={column.logoKey}
              harness={column.harness}
            />
          ))}
          <th className="matrix-table__th matrix-table__th--end">Active</th>
        </tr>
      </thead>
      <tbody>
        {entries.map((entry) => (
          <AgentsMatrixRow
            key={entry.ref}
            entry={entry}
            columns={columns}
            pendingAgent={pendingAgentKeys.has(entry.ref)}
            pendingPerHarnessKeys={pendingPerHarnessKeys}
            checked={checkedRefs.has(entry.ref)}
            onOpenDetail={onOpenDetail}
            onToggleChecked={onToggleChecked}
            onEnableHarness={onEnableHarness}
            onDisableHarness={onDisableHarness}
            onAdopt={onAdopt}
          />
        ))}
      </tbody>
    </MatrixTable>
  );
}

function AgentsMatrixRow({
  entry,
  columns,
  pendingAgent,
  pendingPerHarnessKeys,
  checked,
  onOpenDetail,
  onToggleChecked,
  onEnableHarness,
  onDisableHarness,
  onAdopt,
}: {
  entry: AgentInventoryEntryDto;
  columns: AgentInventoryDto["columns"];
  pendingAgent: boolean;
  pendingPerHarnessKeys: ReadonlySet<string>;
  checked: boolean;
  onOpenDetail: (ref: string) => void;
  onToggleChecked: (ref: string) => void;
  onEnableHarness: (ref: string, harness: string) => void;
  onDisableHarness: (ref: string, harness: string) => void;
  onAdopt: (ref: string) => void;
}) {
  const isUntracked = entry.kind === "unmanaged";
  const enabledCount = entry.bindings.filter((binding) => binding.state === "enabled").length;

  return (
    <tr className="matrix-table__row" data-checked={checked ? "true" : undefined}>
      <td className="matrix-table__cell matrix-table__cell--checkbox">
        {isUntracked ? (
          <CardSelectCheckbox
            checked={checked}
            disabled={pendingAgent}
            label={checked ? `Deselect ${entry.name}` : `Select ${entry.name}`}
            onToggle={() => onToggleChecked(entry.ref)}
          />
        ) : null}
      </td>
      <td
        className="matrix-table__cell matrix-table__cell--identity agent-pointer"
        onClick={() => onOpenDetail(entry.ref)}
      >
        <div className="matrix-table__name-row">
          <OverflowTooltipText as="span" className="matrix-table__name-text">
            {entry.name}
          </OverflowTooltipText>
        </div>
        <OverflowTooltipText as="p" className="matrix-table__description">
          {entry.description}
        </OverflowTooltipText>
      </td>
      {columns.map((column) => {
        const cell = matrixCellFor(entry, column);
        return (
          <td key={column.harness} className="matrix-table__cell matrix-table__cell--harness">
            <AgentsMatrixHarnessCell
              entry={entry}
              column={column}
              cell={cell}
              pending={pendingAgent || pendingPerHarnessKeys.has(cell.pendingKey)}
              onOpenDetail={onOpenDetail}
              onEnableHarness={onEnableHarness}
              onDisableHarness={onDisableHarness}
            />
          </td>
        );
      })}
      <td className="matrix-table__cell matrix-table__cell--coverage">
        {isUntracked ? (
          <button
            type="button"
            className="action-pill action-pill--accent permission-adopt-btn"
            disabled={pendingAgent || !entry.actions.canAdopt}
            onClick={() => onAdopt(entry.ref)}
          >
            {pendingAgent ? <Loader2 size={12} className="card-action-spinner" aria-hidden="true" /> : null}
            Adopt
          </button>
        ) : (
          <span
            className="matrix-table__coverage"
            aria-label={`Coverage: ${enabledCount} / ${columns.length}`}
          >
            <span className="matrix-table__coverage-count">{enabledCount}</span>
            <span className="matrix-table__coverage-total" aria-hidden="true">
              {" / "}
              {columns.length}
            </span>
          </span>
        )}
      </td>
    </tr>
  );
}

function AgentsMatrixHarnessCell({
  entry,
  column,
  cell,
  pending,
  onOpenDetail,
  onEnableHarness,
  onDisableHarness,
}: {
  entry: AgentInventoryEntryDto;
  column: AgentInventoryDto["columns"][number];
  cell: AgentMatrixCellModel;
  pending: boolean;
  onOpenDetail: (ref: string) => void;
  onEnableHarness: (ref: string, harness: string) => void;
  onDisableHarness: (ref: string, harness: string) => void;
}) {
  const content = cell.state === "unavailable" ? <AlertTriangle size={14} aria-hidden="true" /> : cell.state === "empty" ? "—" : (
    <MatrixHarnessIcon label={column.label} logoKey={column.logoKey} harness={column.harness} />
  );
  const disabled = pending || cell.action === null;

  const control = cell.action === null ? (
    <MatrixHarnessCellTarget
      state={cell.state}
      ariaLabel={cell.ariaLabel}
      disabled
      title={cell.tooltip}
    >
      {content}
    </MatrixHarnessCellTarget>
  ) : (
    <MatrixHarnessCellTarget
      state={cell.state}
      pending={pending}
      disabled={disabled}
      ariaLabel={cell.ariaLabel}
      title={cell.tooltip}
      onClick={() => {
        if (cell.action === "enable") onEnableHarness(entry.ref, column.harness);
        else if (cell.action === "disable") onDisableHarness(entry.ref, column.harness);
        else onOpenDetail(entry.ref);
      }}
    >
      {content}
    </MatrixHarnessCellTarget>
  );

  return <UiTooltip content={cell.tooltip}>{control}</UiTooltip>;
}
