import { useMemo, useState } from "react";
import { AlertTriangle, Loader2, Star } from "lucide-react";

import {
  MatrixHarnessCellTarget,
  MatrixHarnessIcon,
  MatrixSortableHeader,
  MatrixTable,
} from "../../../components/matrix";
import { CardSelectCheckbox } from "../../../components/cards/CardSelectCheckbox";
import { UiTooltip } from "../../../components/ui/UiTooltip";
import type { PermissionInventoryColumnDto, PermissionInventoryEntryDto } from "../api/management-types";
import { usePermissionsCopy, type PermissionsCopy } from "../i18n";
import {
  matrixCellFor,
  matrixColumns,
  matrixCoverage,
  permissionsSortKeysEqual,
  sortPermissionsRows,
  type PermissionsMatrixCellModel,
  type PermissionsSortKey,
  type PermissionsSortState,
} from "../model/selectors";
import { PermissionsHarnessLogoStack } from "./PermissionsHarnessLogoStack";
import { PermissionsStatusChip } from "./PermissionsStatusChip";

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
  onAdopt: (id: string) => void;
  onToggleStar?: (id: string) => void;
  starredFilterActive?: boolean;
  onToggleStarredFilter?: () => void;
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
  onAdopt,
  onToggleStar,
  starredFilterActive = false,
  onToggleStarredFilter,
}: PermissionsMatrixViewProps) {
  const copy = usePermissionsCopy();
  const displayColumns = matrixColumns({ columns });
  const [sort, setSort] = useState<PermissionsSortState>({ key: "name", direction: "asc" });

  const requestSort = (key: PermissionsSortKey) => {
    setSort((current) => {
      if (permissionsSortKeysEqual(current.key, key)) {
        return { key, direction: current.direction === "asc" ? "desc" : "asc" };
      }
      return { key, direction: "asc" };
    });
  };

  const sortedEntries = useMemo(
    () => sortPermissionsRows(entries, displayColumns, sort, copy),
    [entries, displayColumns, sort, copy],
  );

  return (
    <MatrixTable
      ariaLabel="Permissions harness matrix"
      harnessColumnWidth="52px"
      compactColumnWidth="140px"
      coverageColumnWidth="96px"
    >
      <thead className="matrix-table__head">
        <tr>
          <th className="matrix-table__th matrix-table__th--checkbox" aria-label="Select Column" />
          <MatrixSortableHeader
            label="Rule"
            align="identity"
            active={permissionsSortKeysEqual(sort.key, "name")}
            direction={sort.direction}
            onClick={() => requestSort("name")}
          />
          <th className="matrix-table__th matrix-table__th--star">
            <UiTooltip content="Starred">
              <button
                type="button"
                className="matrix-table__sort-btn matrix-table__sort-btn--harness matrix-table__star-header-btn"
                data-active={starredFilterActive ? "true" : undefined}
                aria-pressed={starredFilterActive}
                aria-label="Filter by starred"
                onClick={onToggleStarredFilter}
              >
                <Star size={16} fill="currentColor" aria-hidden="true" />
              </button>
            </UiTooltip>
          </th>
          {displayColumns.map((column) => {
            const key: PermissionsSortKey = { harness: column.harness };
            return (
              <MatrixSortableHeader
                key={column.harness}
                label={column.label}
                align="harness"
                active={permissionsSortKeysEqual(sort.key, key)}
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
            active={permissionsSortKeysEqual(sort.key, "coverage")}
            direction={sort.direction}
            onClick={() => requestSort("coverage")}
          />
        </tr>
      </thead>
      <tbody>
        {sortedEntries.map((entry) => (
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
            onAdopt={onAdopt}
            onToggleStar={onToggleStar}
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
  onAdopt,
  onToggleStar,
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
  onAdopt: (id: string) => void;
  onToggleStar?: (id: string) => void;
  copy: PermissionsCopy;
}) {
  const coverage = matrixCoverage(entry, columns);
  const isUntracked = entry.kind === "unmanaged";
  const ruleName = entry.spec?.pattern ?? entry.displayName;
  const isStarred = (entry.tags || []).some((t) => t.toLowerCase() === "starred");
  const displayTags = (entry.tags || []).filter((t) => t.toLowerCase() !== "starred");

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
            <code className="matrix-table__name-text">{ruleName}</code>
            {entry.spec ? (
              <PermissionsStatusChip decision={entry.spec.decision} scope={entry.spec.scope} />
            ) : null}
            {displayTags.length > 0 ? (
              <div className="matrix-table__tag-pills">
                {displayTags.slice(0, 2).map((tag) => (
                  <span key={tag} className="matrix-table__tag-pill">
                    {tag}
                  </span>
                ))}
                {displayTags.length > 2 ? (
                  <span className="matrix-table__tag-pill matrix-table__tag-pill--more">
                    +{displayTags.length - 2}
                  </span>
                ) : null}
              </div>
            ) : null}
          </span>
          {entry.spec?.description ? (
            <span className="matrix-table__description">{entry.spec.description}</span>
          ) : null}
        </button>
      </td>
      <td className="matrix-table__cell matrix-table__cell--star">
        {onToggleStar ? (
          <button
            type="button"
            className={`skill-star-btn ${isStarred ? "skill-star-btn--active" : ""}`}
            aria-label={isStarred ? `Unstar ${entry.displayName}` : `Star ${entry.displayName}`}
            onClick={(e) => {
              e.stopPropagation();
              onToggleStar(entry.id);
            }}
          >
            <Star
              size={14}
              className={`skill-star-icon ${isStarred ? "skill-star-icon--filled" : ""}`}
            />
          </button>
        ) : null}
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
        {isUntracked ? (
          <button
            type="button"
            className="action-pill action-pill--accent permission-adopt-btn"
            disabled={pendingPermission}
            onClick={() => onAdopt(entry.id)}
          >
            {pendingPermission ? (
              <Loader2 size={12} className="card-action-spinner" aria-hidden="true" />
            ) : null}
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
