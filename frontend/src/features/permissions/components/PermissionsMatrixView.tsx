import { AlertTriangle } from "lucide-react";

import { CardSelectCheckbox } from "../../../components/cards/CardSelectCheckbox";
import {
  MatrixHarnessCellTarget,
  MatrixHarnessHeader,
  MatrixHarnessIcon,
  MatrixTable,
} from "../../../components/matrix";
import { UiTooltip } from "../../../components/ui/UiTooltip";
import type { PermissionInventoryColumnDto, PermissionInventoryEntryDto } from "../api/management-types";
import { usePermissionsCopy, type PermissionsCopy } from "../i18n";
import {
  matrixCellFor,
  matrixColumns,
  matrixCoverage,
  type PermissionsMatrixCellModel,
} from "../model/selectors";
import { PermissionsHarnessLogoStack } from "./PermissionsHarnessLogoStack";

interface PermissionsMatrixViewProps {
  entries: PermissionInventoryEntryDto[];
  columns: PermissionInventoryColumnDto[];
  pendingPermissionKeys: ReadonlySet<string>;
  pendingPerHarnessKeys: ReadonlySet<string>;
  checkedIds: ReadonlySet<string>;
  onOpenDetail: (id: string) => void;
  onToggleChecked: (id: string) => void;
  onEnableHarness: (id: string, harness: string) => void;
  onDisableHarness: (id: string, harness: string) => void;
}

export function PermissionsMatrixView({
  entries,
  columns,
  pendingPermissionKeys,
  pendingPerHarnessKeys,
  checkedIds,
  onOpenDetail,
  onToggleChecked,
  onEnableHarness,
  onDisableHarness,
}: PermissionsMatrixViewProps) {
  const copy = usePermissionsCopy();
  const displayColumns = matrixColumns({ columns });

  return (
    <MatrixTable
      ariaLabel="Permissions Matrix"
      harnessColumnCount={displayColumns.length}
      harnessColumnWidth="52px"
      compactColumnWidth="140px"
      coverageColumnWidth="120px"
    >
      <thead className="matrix-table__head">
        <tr>
          <th className="matrix-table__th matrix-table__th--checkbox" aria-label="Select Column" />
          <th className="matrix-table__th matrix-table__th--identity">Permission ID</th>
          {displayColumns.map((column) => (
            <MatrixHarnessHeader
              key={column.harness}
              label={column.label}
              logoKey={column.logoKey}
              harness={column.harness}
            />
          ))}
          <th className="matrix-table__th matrix-table__th--compact" aria-label="Harnesses">
            Harnesses
          </th>
          <th className="matrix-table__th matrix-table__th--end">Enabled</th>
        </tr>
      </thead>
      <tbody>
        {entries.map((entry) => (
          <PermissionsMatrixRow
            key={entry.id}
            entry={entry}
            columns={displayColumns}
            pendingPermission={pendingPermissionKeys.has(entry.id)}
            pendingPerHarnessKeys={pendingPerHarnessKeys}
            checked={checkedIds.has(entry.id)}
            onOpenDetail={onOpenDetail}
            onToggleChecked={onToggleChecked}
            onEnableHarness={onEnableHarness}
            onDisableHarness={onDisableHarness}
            copy={copy}
          />
        ))}
      </tbody>
    </MatrixTable>
  );
}

function PermissionsMatrixRow({
  entry,
  columns,
  pendingPermission,
  pendingPerHarnessKeys,
  checked,
  onOpenDetail,
  onToggleChecked,
  onEnableHarness,
  onDisableHarness,
  copy,
}: {
  entry: PermissionInventoryEntryDto;
  columns: PermissionInventoryColumnDto[];
  pendingPermission: boolean;
  pendingPerHarnessKeys: ReadonlySet<string>;
  checked: boolean;
  onOpenDetail: (id: string) => void;
  onToggleChecked: (id: string) => void;
  onEnableHarness: (id: string, harness: string) => void;
  onDisableHarness: (id: string, harness: string) => void;
  copy: PermissionsCopy;
}) {
  const coverage = matrixCoverage(entry, columns);

  return (
    <tr className="matrix-table__row" data-checked={checked ? "true" : undefined}>
      <td className="matrix-table__cell matrix-table__cell--checkbox">
        <CardSelectCheckbox
          checked={checked}
          label={checked ? copy.detail.deselect(entry.displayName) : copy.detail.select(entry.displayName)}
          onToggle={() => onToggleChecked(entry.id)}
          disabled={pendingPermission}
        />
      </td>
      <td className="matrix-table__cell matrix-table__cell--identity">
        <button
          type="button"
          className="mcp-matrix__server-button"
          aria-label={copy.detail.openDetail(entry.displayName)}
          onClick={() => onOpenDetail(entry.id)}
        >
          <span className="matrix-table__name-row">
            <span className="matrix-table__name-text">{entry.displayName}</span>
          </span>
          <span className="matrix-table__description">
            <code>{entry.spec?.pattern ?? "—"}</code> · {entry.spec?.decision ?? "—"}: {entry.spec?.scope ?? "—"}
          </span>
        </button>
      </td>
      {columns.map((column) => {
        const cell = matrixCellFor(entry, column, copy);
        return (
          <td key={column.harness} className="matrix-table__cell matrix-table__cell--harness">
            <PermissionsMatrixHarnessCell
              entry={entry}
              column={column}
              cell={cell}
              pending={pendingPermission || pendingPerHarnessKeys.has(cell.pendingKey)}
              onOpenDetail={onOpenDetail}
              onEnableHarness={onEnableHarness}
              onDisableHarness={onDisableHarness}
            />
          </td>
        );
      })}
      <td className="matrix-table__cell matrix-table__cell--compact">
        <PermissionsHarnessLogoStack bindings={entry.sightings} columns={columns} />
      </td>
      <td className="matrix-table__cell matrix-table__cell--coverage">
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
      </td>
    </tr>
  );
}

function PermissionsMatrixHarnessCell({
  entry,
  column,
  cell,
  pending,
  onOpenDetail,
  onEnableHarness,
  onDisableHarness,
}: {
  entry: PermissionInventoryEntryDto;
  column: PermissionInventoryColumnDto;
  cell: PermissionsMatrixCellModel;
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

function cellContent(column: PermissionInventoryColumnDto, cell: PermissionsMatrixCellModel) {
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
