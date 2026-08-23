import { useMemo, useState } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";

import { CardSelectCheckbox } from "../../../components/cards/CardSelectCheckbox";
import {
  MatrixHarnessCellTarget,
  MatrixHarnessIcon,
  MatrixSortableHeader,
  MatrixTable,
} from "../../../components/matrix";
import { OverflowTooltipText } from "../../../components/ui/OverflowTooltipText";
import { UiTooltip } from "../../../components/ui/UiTooltip";
import type { HookInventoryColumnDto, HookInventoryEntryDto } from "../api/management-types";
import { useHooksCopy, type HooksCopy } from "../i18n";
import {
  hooksSortKeysEqual,
  matrixCellFor,
  matrixColumns,
  matrixCoverage,
  sortHooksRows,
  type HooksMatrixCellModel,
  type HooksSortKey,
  type HooksSortState,
} from "../model/selectors";
import { HooksHarnessLogoStack } from "./HooksHarnessLogoStack";

interface HooksMatrixViewProps {
  entries: HookInventoryEntryDto[];
  columns: HookInventoryColumnDto[];
  pendingHookKeys: ReadonlySet<string>;
  pendingPerHarnessKeys: ReadonlySet<string>;
  checkedIds: ReadonlySet<string>;
  onOpenDetail: (id: string) => void;
  onToggleChecked: (id: string) => void;
  onEnableHarness: (id: string, harness: string) => void;
  onDisableHarness: (id: string, harness: string) => void;
  onAdopt: (id: string) => void;
}

const INITIAL_SORT: HooksSortState = { key: "name", direction: "asc" };

export function HooksMatrixView({
  entries,
  columns,
  pendingHookKeys,
  pendingPerHarnessKeys,
  checkedIds,
  onOpenDetail,
  onToggleChecked,
  onEnableHarness,
  onDisableHarness,
  onAdopt,
}: HooksMatrixViewProps) {
  const copy = useHooksCopy();
  const displayColumns = matrixColumns({ columns });
  const [sort, setSort] = useState<HooksSortState>(INITIAL_SORT);
  const sortedEntries = useMemo(
    () => sortHooksRows(entries, columns, sort, copy),
    [entries, columns, sort, copy],
  );

  const requestSort = (key: HooksSortKey) => {
    setSort((current) => {
      if (hooksSortKeysEqual(current.key, key)) {
        return { key, direction: current.direction === "asc" ? "desc" : "asc" };
      }
      return { key, direction: "asc" };
    });
  };

  return (
    <MatrixTable
      ariaLabel="Hooks harness matrix"
      harnessColumnWidth="52px"
      compactColumnWidth="140px"
      coverageColumnWidth="96px"
    >
      <thead className="matrix-table__head">
        <tr>
          <th className="matrix-table__th matrix-table__th--checkbox" aria-label="Select Column" />
          <MatrixSortableHeader
            label="Hook"
            align="identity"
            active={hooksSortKeysEqual(sort.key, "name")}
            direction={sort.direction}
            onClick={() => requestSort("name")}
          />
          {displayColumns.map((column) => {
            const key: HooksSortKey = { harness: column.harness };
            return (
              <MatrixSortableHeader
                key={column.harness}
                label={column.label}
                align="harness"
                active={hooksSortKeysEqual(sort.key, key)}
                direction={sort.direction}
                logoOnly
                leading={
                  <MatrixHarnessIcon
                    label={column.label}
                    logoKey={column.logoKey}
                    harness={column.harness}
                  />
                }
                srLabel={`Sort by ${column.label}`}
                onClick={() => requestSort(key)}
              />
            );
          })}
          <th className="matrix-table__th matrix-table__th--compact" aria-label="Harnesses">
            Harnesses
          </th>
          <MatrixSortableHeader
            label="Active"
            align="end"
            active={hooksSortKeysEqual(sort.key, "coverage")}
            direction={sort.direction}
            onClick={() => requestSort("coverage")}
          />
        </tr>
      </thead>
      <tbody>
        {sortedEntries.map((entry) => (
          <HooksMatrixRow
            key={entry.id}
            entry={entry}
            columns={displayColumns}
            pendingHook={pendingHookKeys.has(entry.id)}
            pendingPerHarnessKeys={pendingPerHarnessKeys}
            checked={checkedIds.has(entry.id)}
            onOpenDetail={onOpenDetail}
            onToggleChecked={onToggleChecked}
            onEnableHarness={onEnableHarness}
            onDisableHarness={onDisableHarness}
            onAdopt={onAdopt}
            copy={copy}
          />
        ))}
      </tbody>
    </MatrixTable>
  );
}

function HooksMatrixRow({
  entry,
  columns,
  pendingHook,
  pendingPerHarnessKeys,
  checked,
  onOpenDetail,
  onToggleChecked,
  onEnableHarness,
  onDisableHarness,
  onAdopt,
  copy,
}: {
  entry: HookInventoryEntryDto;
  columns: HookInventoryColumnDto[];
  pendingHook: boolean;
  pendingPerHarnessKeys: ReadonlySet<string>;
  checked: boolean;
  onOpenDetail: (id: string) => void;
  onToggleChecked: (id: string) => void;
  onEnableHarness: (id: string, harness: string) => void;
  onDisableHarness: (id: string, harness: string) => void;
  onAdopt: (id: string) => void;
  copy: HooksCopy;
}) {
  const coverage = matrixCoverage(entry, columns);
  const isUntracked = entry.kind === "unmanaged";

  return (
    <tr className="matrix-table__row" data-checked={checked ? "true" : undefined}>
      <td className="matrix-table__cell matrix-table__cell--checkbox">
        {isUntracked ? (
          <CardSelectCheckbox
            checked={checked}
            label={checked ? copy.detail.deselect(entry.displayName) : copy.detail.select(entry.displayName)}
            onToggle={() => onToggleChecked(entry.id)}
            disabled={pendingHook}
          />
        ) : null}
      </td>
      <td
        className="matrix-table__cell matrix-table__cell--identity"
        onClick={() => onOpenDetail(entry.id)}
      >
        <div className="matrix-table__name-row">
          <OverflowTooltipText as="span" className="matrix-table__name-text">
            {entry.displayName}
          </OverflowTooltipText>
        </div>
        <OverflowTooltipText as="p" className="matrix-table__description">
          <code>{entry.spec?.command ?? "—"}</code>
        </OverflowTooltipText>
      </td>
      {columns.map((column) => {
        const cell = matrixCellFor(entry, column, copy);
        return (
          <td key={column.harness} className="matrix-table__cell matrix-table__cell--harness">
            <HooksMatrixHarnessCell
              entry={entry}
              column={column}
              cell={cell}
              pending={pendingHook || pendingPerHarnessKeys.has(cell.pendingKey)}
              onOpenDetail={onOpenDetail}
              onEnableHarness={onEnableHarness}
              onDisableHarness={onDisableHarness}
            />
          </td>
        );
      })}
      <td className="matrix-table__cell matrix-table__cell--compact">
        <HooksHarnessLogoStack bindings={entry.sightings} columns={columns} />
      </td>
      <td className="matrix-table__cell matrix-table__cell--coverage">
        {isUntracked ? (
          <button
            type="button"
            className="action-pill action-pill--accent permission-adopt-btn"
            disabled={pendingHook}
            onClick={() => onAdopt(entry.id)}
          >
            {pendingHook ? <Loader2 size={12} className="card-action-spinner" aria-hidden="true" /> : null}
            {copy.inUse.adopt}
          </button>
        ) : (
          <span
            className="matrix-table__coverage"
            aria-label={`Coverage: ${coverage.enabled} / ${coverage.writable}`}
          >
            <span className="matrix-table__coverage-count">{coverage.enabled}</span>
            <span className="matrix-table__coverage-total" aria-hidden="true">
              {" / "}
              {coverage.writable}
            </span>
          </span>
        )}
      </td>
    </tr>
  );
}

function HooksMatrixHarnessCell({
  entry,
  column,
  cell,
  pending,
  onOpenDetail,
  onEnableHarness,
  onDisableHarness,
}: {
  entry: HookInventoryEntryDto;
  column: HookInventoryColumnDto;
  cell: HooksMatrixCellModel;
  pending: boolean;
  onOpenDetail: (id: string) => void;
  onEnableHarness: (id: string, harness: string) => void;
  onDisableHarness: (id: string, harness: string) => void;
}) {
  const content = cellContent(column, cell);
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
        if (cell.action === "enable") {
          onEnableHarness(entry.id, column.harness);
        } else if (cell.action === "disable") {
          onDisableHarness(entry.id, column.harness);
        } else {
          onOpenDetail(entry.id);
        }
      }}
    >
      {content}
    </MatrixHarnessCellTarget>
  );

  return <UiTooltip content={cell.tooltip}>{control}</UiTooltip>;
}

function cellContent(column: HookInventoryColumnDto, cell: HooksMatrixCellModel) {
  if (cell.state === "unavailable") {
    return <AlertTriangle size={14} aria-hidden="true" />;
  }
  return (
    <MatrixHarnessIcon
      label={column.label}
      logoKey={column.logoKey}
      harness={column.harness}
    />
  );
}
