import { useMemo, useState } from "react";
import { AlertTriangle, Loader2, Star } from "lucide-react";

import { CardSelectCheckbox } from "../../../components/cards/CardSelectCheckbox";
import {
  MatrixHarnessCellTarget,
  MatrixHarnessIcon,
  MatrixSortableHeader,
  MatrixTable,
} from "../../../components/matrix";
import { OverflowTooltipText } from "../../../components/ui/OverflowTooltipText";
import { UiTooltip } from "../../../components/ui/UiTooltip";
import type { AgentInventoryDto, AgentInventoryEntryDto } from "../api/types";
import {
  agentSortKeysEqual,
  matrixCellFor,
  sortAgentsRows,
  type AgentMatrixCellModel,
  type AgentSortKey,
  type AgentSortState,
} from "../model/selectors";
import { AgentsHarnessLogoStack } from "./AgentsHarnessLogoStack";

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
  onToggleStar?: (ref: string) => void;
  starredFilterActive?: boolean;
  onToggleStarredFilter?: () => void;
}

const INITIAL_SORT: AgentSortState = { key: "name", direction: "asc" };

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
  onToggleStar,
  starredFilterActive = false,
  onToggleStarredFilter,
}: AgentsMatrixViewProps) {
  const [sort, setSort] = useState<AgentSortState>(INITIAL_SORT);
  const sortedEntries = useMemo(() => sortAgentsRows(entries, columns, sort), [entries, columns, sort]);

  const requestSort = (key: AgentSortKey) => {
    setSort((current) => {
      if (agentSortKeysEqual(current.key, key)) {
        return { key, direction: current.direction === "asc" ? "desc" : "asc" };
      }
      return { key, direction: "asc" };
    });
  };

  return (
    <MatrixTable
      ariaLabel="Agents harness matrix"
      harnessColumnWidth="52px"
      compactColumnWidth="140px"
      coverageColumnWidth="96px"
    >
      <thead className="matrix-table__head">
        <tr>
          <th className="matrix-table__th matrix-table__th--checkbox" aria-label="Select Column" />
          <MatrixSortableHeader
            label="Agent"
            align="identity"
            active={agentSortKeysEqual(sort.key, "name")}
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
          {columns.map((column) => {
            const key: AgentSortKey = { harness: column.harness };
            return (
              <MatrixSortableHeader
                key={column.harness}
                label={column.label}
                align="harness"
                active={agentSortKeysEqual(sort.key, key)}
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
            active={agentSortKeysEqual(sort.key, "coverage")}
            direction={sort.direction}
            onClick={() => requestSort("coverage")}
          />
        </tr>
      </thead>
      <tbody>
        {sortedEntries.map((entry) => (
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
            onToggleStar={onToggleStar}
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
  onToggleStar,
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
  onToggleStar?: (ref: string) => void;
}) {
  const isUntracked = entry.kind === "unmanaged";
  const enabledCount = entry.bindings.filter((binding) => binding.state === "enabled").length;
  const isStarred = (entry.tags || []).some((t) => t.toLowerCase() === "starred");
  const displayTags = (entry.tags || []).filter((t) => t.toLowerCase() !== "starred");

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
        </div>
        <OverflowTooltipText as="p" className="matrix-table__description">
          {entry.description}
        </OverflowTooltipText>
      </td>
      <td className="matrix-table__cell matrix-table__cell--star">
        {onToggleStar ? (
          <button
            type="button"
            className={`skill-star-btn ${isStarred ? "skill-star-btn--active" : ""}`}
            aria-label={isStarred ? `Unstar ${entry.name}` : `Star ${entry.name}`}
            onClick={(e) => {
              e.stopPropagation();
              onToggleStar(entry.ref);
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
      <td className="matrix-table__cell matrix-table__cell--compact">
        <AgentsHarnessLogoStack bindings={entry.bindings} columns={columns} />
      </td>
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
