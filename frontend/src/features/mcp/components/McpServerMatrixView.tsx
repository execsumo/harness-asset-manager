import { AlertTriangle, Loader2 } from "lucide-react";

import { CardSelectCheckbox } from "../../../components/cards/CardSelectCheckbox";
import {
  MatrixHarnessCellTarget,
  MatrixHarnessHeader,
  MatrixHarnessIcon,
  MatrixTable,
} from "../../../components/matrix";
import { UiTooltip } from "../../../components/ui/UiTooltip";
import type {
  McpIdentityGroupDto,
  McpInventoryColumnDto,
  McpInventoryEntryDto,
} from "../api/management-types";
import { useMcpCopy, type McpCopy } from "../i18n";
import {
  matrixCellFor,
  matrixColumns,
  matrixCoverage,
  type McpMatrixCellModel,
} from "../model/selectors";
import { McpHarnessLogoStack } from "./McpHarnessLogoStack";

interface McpServerMatrixViewProps {
  entries: McpInventoryEntryDto[];
  columns: McpInventoryColumnDto[];
  pendingServerKeys: ReadonlySet<string>;
  pendingAdoptKeys?: ReadonlySet<string>;
  pendingPerHarnessKeys: ReadonlySet<string>;
  checkedNames: ReadonlySet<string>;
  checkedUntrackedNames?: ReadonlySet<string>;
  groupsByName?: ReadonlyMap<string, McpIdentityGroupDto>;
  onOpenDetail: (name: string) => void;
  onToggleChecked: (name: string) => void;
  onToggleCheckedUntracked?: (name: string) => void;
  onEnableHarness: (name: string, harness: string) => void;
  onDisableHarness: (name: string, harness: string) => void;
  onAdopt?: (name: string) => void;
  onChooseConfigToAdopt?: (name: string) => void;
}

export function McpServerMatrixView({
  entries,
  columns,
  pendingServerKeys,
  pendingAdoptKeys,
  pendingPerHarnessKeys,
  checkedNames,
  checkedUntrackedNames,
  groupsByName,
  onOpenDetail,
  onToggleChecked,
  onToggleCheckedUntracked,
  onEnableHarness,
  onDisableHarness,
  onAdopt,
  onChooseConfigToAdopt,
}: McpServerMatrixViewProps) {
  const copy = useMcpCopy();
  const displayColumns = matrixColumns({ columns });

  const isAdoptPending = (name: string) =>
    Boolean(
      pendingAdoptKeys &&
        (pendingAdoptKeys.has(name) ||
          Array.from(pendingAdoptKeys).some((key) => key.startsWith(`${name}:`))),
    );

  return (
    <MatrixTable
      ariaLabel={copy.detail.matrix.ariaLabel}
      harnessColumnWidth="52px"
      compactColumnWidth="140px"
      coverageColumnWidth="160px"
    >
      <thead className="matrix-table__head">
        <tr>
          <th className="matrix-table__th matrix-table__th--checkbox" aria-label={copy.detail.matrix.selectColumn} />
          <th className="matrix-table__th matrix-table__th--identity">{copy.detail.matrix.serverColumn}</th>
          {displayColumns.map((column) => (
            <MatrixHarnessHeader
              key={column.harness}
              label={column.label}
              logoKey={column.logoKey}
              harness={column.harness}
            />
          ))}
          <th className="matrix-table__th matrix-table__th--compact" aria-label={copy.detail.matrix.harnessesColumn}>
            {copy.detail.matrix.harnessesColumn}
          </th>
          <th className="matrix-table__th matrix-table__th--end">{copy.detail.matrix.enabledColumn}</th>
        </tr>
      </thead>
      <tbody>
        {entries.map((entry) => {
          const isUntracked = entry.kind === "unmanaged";
          const group = groupsByName?.get(entry.name);
          const isChecked = isUntracked
            ? Boolean(checkedUntrackedNames?.has(entry.name))
            : checkedNames.has(entry.name);
          return (
            <McpMatrixRow
              key={entry.name}
              entry={entry}
              columns={displayColumns}
              pendingServer={pendingServerKeys.has(entry.name)}
              pendingAdopt={isAdoptPending(entry.name)}
              pendingPerHarnessKeys={pendingPerHarnessKeys}
              checked={isChecked}
              group={group}
              onOpenDetail={onOpenDetail}
              onToggleChecked={isUntracked && onToggleCheckedUntracked ? onToggleCheckedUntracked : onToggleChecked}
              onEnableHarness={onEnableHarness}
              onDisableHarness={onDisableHarness}
              onAdopt={onAdopt}
              onChooseConfigToAdopt={onChooseConfigToAdopt}
              copy={copy}
            />
          );
        })}
      </tbody>
    </MatrixTable>
  );
}

function McpMatrixRow({
  entry,
  columns,
  pendingServer,
  pendingAdopt,
  pendingPerHarnessKeys,
  checked,
  group,
  onOpenDetail,
  onToggleChecked,
  onEnableHarness,
  onDisableHarness,
  onAdopt,
  onChooseConfigToAdopt,
  copy,
}: {
  entry: McpInventoryEntryDto;
  columns: McpInventoryColumnDto[];
  pendingServer: boolean;
  pendingAdopt: boolean;
  pendingPerHarnessKeys: ReadonlySet<string>;
  checked: boolean;
  group?: McpIdentityGroupDto;
  onOpenDetail: (name: string) => void;
  onToggleChecked: (name: string) => void;
  onEnableHarness: (name: string, harness: string) => void;
  onDisableHarness: (name: string, harness: string) => void;
  onAdopt?: (name: string) => void;
  onChooseConfigToAdopt?: (name: string) => void;
  copy: McpCopy;
}) {
  const coverage = matrixCoverage(entry, columns);
  const isUntracked = entry.kind === "unmanaged";
  const isIdentical = group ? group.identical : true;
  const isSelectable = !isUntracked || isIdentical;
  const isRowPending = pendingServer || pendingAdopt;

  return (
    <tr className="matrix-table__row" data-checked={checked ? "true" : undefined}>
      <td className="matrix-table__cell matrix-table__cell--checkbox">
        <CardSelectCheckbox
          checked={checked}
          label={checked ? copy.detail.deselect(entry.displayName) : copy.detail.select(entry.displayName)}
          onToggle={() => onToggleChecked(entry.name)}
          disabled={isRowPending || !isSelectable}
        />
      </td>
      <td className="matrix-table__cell matrix-table__cell--identity">
        <button
          type="button"
          className="mcp-matrix__server-button"
          aria-label={copy.detail.openDetail(entry.displayName)}
          onClick={() => onOpenDetail(entry.name)}
        >
          <span className="matrix-table__name-row">
            <span className="matrix-table__name-text">{entry.displayName}</span>
          </span>
          <span className="matrix-table__description">
            {isUntracked
              ? (group
                  ? (group.identical ? copy.detail.review.identical : copy.detail.review.differsAcrossHarnesses)
                  : (entry.spec?.transport ?? "—"))
              : `${entry.name} · ${entry.spec?.transport ?? "—"}`}
          </span>
        </button>
      </td>
      {columns.map((column) => {
        const cell = matrixCellFor(entry, column, copy);
        return (
          <td key={column.harness} className="matrix-table__cell matrix-table__cell--harness">
            <McpMatrixHarnessCell
              entry={entry}
              column={column}
              cell={cell}
              pending={isRowPending || pendingPerHarnessKeys.has(cell.pendingKey)}
              onOpenDetail={onOpenDetail}
              onEnableHarness={onEnableHarness}
              onDisableHarness={onDisableHarness}
            />
          </td>
        );
      })}
      <td className="matrix-table__cell matrix-table__cell--compact">
        <McpHarnessLogoStack bindings={entry.sightings} columns={columns} />
      </td>
      <td className="matrix-table__cell matrix-table__cell--coverage">
        {isUntracked ? (
          <button
            type="button"
            className={`action-pill ${isIdentical ? "action-pill--accent" : ""}`}
            disabled={isRowPending}
            title={isIdentical ? copy.detail.review.addTooltip : copy.detail.review.chooseTooltip}
            onClick={() => {
              if (isIdentical) {
                onAdopt?.(entry.name);
              } else {
                onChooseConfigToAdopt?.(entry.name);
              }
            }}
          >
            {pendingAdopt ? (
              <Loader2 size={12} className="card-action-spinner" aria-hidden="true" />
            ) : null}
            {isIdentical ? copy.detail.review.adopt : copy.detail.review.chooseConfigToAdopt}
          </button>
        ) : (
          <span
            className="matrix-table__coverage"
            aria-label={copy.detail.matrix.coverage(coverage.enabled, coverage.writable)}
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

function McpMatrixHarnessCell({
  entry,
  column,
  cell,
  pending,
  onOpenDetail,
  onEnableHarness,
  onDisableHarness,
}: {
  entry: McpInventoryEntryDto;
  column: McpInventoryColumnDto;
  cell: McpMatrixCellModel;
  pending: boolean;
  onOpenDetail: (name: string) => void;
  onEnableHarness: (name: string, harness: string) => void;
  onDisableHarness: (name: string, harness: string) => void;
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
          onEnableHarness(entry.name, column.harness);
        } else if (cell.action === "disable") {
          onDisableHarness(entry.name, column.harness);
        } else {
          onOpenDetail(entry.name);
        }
      }}
    >
      {content}
    </MatrixHarnessCellTarget>
  );

  return <UiTooltip content={cell.tooltip}>{control}</UiTooltip>;
}

function cellContent(column: McpInventoryColumnDto, cell: McpMatrixCellModel) {
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
