import { useMemo, useState } from "react";
import { Loader2, Star } from "lucide-react";

import { CardSelectCheckbox } from "../../../components/cards/CardSelectCheckbox";
import {
  MatrixHarnessCellTarget,
  MatrixHarnessIcon,
  MatrixSortableHeader,
  MatrixTable,
} from "../../../components/matrix";
import { getHarnessPresentation } from "../../../components/harness/harnessPresentation";
import { OverflowTooltipText } from "../../../components/ui/OverflowTooltipText";
import { UiTooltip } from "../../../components/ui/UiTooltip";
import type { SlashCommandDto, SlashCommandReviewDto, SlashTargetDto } from "../api/types";
import { useSlashCommandsCopy } from "../i18n";
import {
  enabledTargetsForCommand,
  primaryReviewAction,
  reviewKey,
  slashSortKeysEqual,
  syncedTargetIds,
  type SlashCommandInventoryEntry,
  type SlashMatrixSortKey,
  type SlashMatrixSortState,
} from "../model/selectors";

interface SlashCommandMatrixProps {
  entries: SlashCommandInventoryEntry[];
  targets: SlashTargetDto[];
  pendingName: string | null;
  pendingTarget: string | null;
  pendingReviewKey: string | null;
  checkedRefs: ReadonlySet<string>;
  onOpenManaged: (command: SlashCommandDto) => void;
  onOpenReview: (row: SlashCommandReviewDto) => void;
  onToggleChecked: (ref: string) => void;
  onToggleTarget: (command: SlashCommandDto, target: SlashTargetDto) => void;
  onReviewAction: (row: SlashCommandReviewDto) => void;
  onToggleStar?: (name: string) => void;
  starredFilterActive?: boolean;
  onToggleStarredFilter?: () => void;
}

const INITIAL_SORT: SlashMatrixSortState = { key: "name", direction: "asc" };

export function SlashCommandMatrix({
  entries,
  targets,
  pendingName,
  pendingTarget,
  pendingReviewKey,
  checkedRefs,
  onOpenManaged,
  onOpenReview,
  onToggleChecked,
  onToggleTarget,
  onReviewAction,
  onToggleStar,
  starredFilterActive = false,
  onToggleStarredFilter,
}: SlashCommandMatrixProps) {
  const [sort, setSort] = useState<SlashMatrixSortState>(INITIAL_SORT);
  const sortedEntries = useMemo(() => sortEntries(entries, sort), [entries, sort]);

  function requestSort(key: SlashMatrixSortKey): void {
    setSort((current) => {
      if (slashSortKeysEqual(current.key, key)) {
        return { key, direction: current.direction === "asc" ? "desc" : "asc" };
      }
      return { key, direction: "asc" };
    });
  }

  return (
    <MatrixTable
      ariaLabel="Slash commands target matrix"
      harnessColumnWidth="52px"
      compactColumnWidth="140px"
      coverageColumnWidth="96px"
    >
      <thead className="matrix-table__head">
        <tr>
          <th className="matrix-table__th matrix-table__th--checkbox" aria-label="Select" />
          <MatrixSortableHeader
            label="Slash Command"
            align="identity"
            active={slashSortKeysEqual(sort.key, "name")}
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
          {targets.map((target) => {
            const key: SlashMatrixSortKey = { target: target.id };
            return (
              <MatrixSortableHeader
                key={target.id}
                label={target.label}
                align="harness"
                active={slashSortKeysEqual(sort.key, key)}
                direction={sort.direction}
                logoOnly
                leading={
                  <MatrixHarnessIcon
                    label={target.label}
                    logoKey={target.id === "claude" ? "claude" : target.id}
                    harness={target.id}
                  />
                }
                srLabel={`Sort by ${target.label}`}
                onClick={() => requestSort(key)}
              />
            );
          })}
          <th className="matrix-table__th matrix-table__th--compact" aria-label="Targets">
            Targets
          </th>
          <MatrixSortableHeader
            label="Active"
            align="end"
            active={slashSortKeysEqual(sort.key, "coverage")}
            direction={sort.direction}
            onClick={() => requestSort("coverage")}
          />
        </tr>
      </thead>
      <tbody>
        {sortedEntries.map((entry) => (
          <SlashCommandMatrixRow
            key={entry.kind === "managed" ? `managed:${entry.command.name}` : `review:${entry.review.reviewRef}`}
            entry={entry}
            targets={targets}
            pendingName={pendingName}
            pendingTarget={pendingTarget}
            pendingReviewKey={pendingReviewKey}
            checked={checkedRefs.has(entry.id)}
            onOpenManaged={onOpenManaged}
            onOpenReview={onOpenReview}
            onToggleChecked={onToggleChecked}
            onToggleTarget={onToggleTarget}
            onReviewAction={onReviewAction}
            onToggleStar={onToggleStar}
          />
        ))}
      </tbody>
    </MatrixTable>
  );
}

function SlashCommandMatrixRow({
  entry,
  targets,
  pendingName,
  pendingTarget,
  pendingReviewKey,
  checked,
  onOpenManaged,
  onOpenReview,
  onToggleChecked,
  onToggleTarget,
  onReviewAction,
  onToggleStar,
}: {
  entry: SlashCommandInventoryEntry;
  targets: SlashTargetDto[];
  pendingName: string | null;
  pendingTarget: string | null;
  pendingReviewKey: string | null;
  checked: boolean;
  onOpenManaged: (command: SlashCommandDto) => void;
  onOpenReview: (row: SlashCommandReviewDto) => void;
  onToggleChecked: (ref: string) => void;
  onToggleTarget: (command: SlashCommandDto, target: SlashTargetDto) => void;
  onReviewAction: (row: SlashCommandReviewDto) => void;
  onToggleStar?: (name: string) => void;
}) {
  const copy = useSlashCommandsCopy();

  if (entry.kind === "managed") {
    const { command } = entry;
    const enabled = syncedTargetIds(command);
    const isStarred = (command.tags || []).some((t) => t.toLowerCase() === "starred");
    const displayTags = (command.tags || []).filter((t) => t.toLowerCase() !== "starred");

    return (
      <tr className="matrix-table__row">
        <td className="matrix-table__cell matrix-table__cell--checkbox" />
        <td className="matrix-table__cell matrix-table__cell--identity" onClick={() => onOpenManaged(command)}>
          <div className="matrix-table__name-row slash-matrix-name-row">
            <OverflowTooltipText as="span" className="matrix-table__name-text">{command.name}</OverflowTooltipText>
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
          {command.description ? (
            <OverflowTooltipText as="p" className="matrix-table__description">{command.description}</OverflowTooltipText>
          ) : null}
        </td>
        <td className="matrix-table__cell matrix-table__cell--star">
          {onToggleStar ? (
            <button
              type="button"
              className={`skill-star-btn ${isStarred ? "skill-star-btn--active" : ""}`}
              aria-label={isStarred ? `Unstar ${command.name}` : `Star ${command.name}`}
              onClick={(e) => {
                e.stopPropagation();
                onToggleStar(command.name);
              }}
            >
              <Star
                size={14}
                className={`skill-star-icon ${isStarred ? "skill-star-icon--filled" : ""}`}
              />
            </button>
          ) : null}
        </td>
        {targets.map((target) => {
          const isEnabled = enabled.has(target.id);
          const pending = pendingName === command.name;
          return (
            <td key={target.id} className="matrix-table__cell matrix-table__cell--harness">
              <UiTooltip content={`${target.label} — ${isEnabled ? "enabled" : "disabled"}`}>
                <MatrixHarnessCellTarget
                  ariaLabel={`${isEnabled ? "Disable" : "Enable"} ${target.label} for ${command.name}`}
                  state={isEnabled ? "enabled" : "disabled"}
                  pending={pending && pendingTarget === target.id}
                  disabled={pending || !target.enabled}
                  ariaPressed={isEnabled}
                  onClick={() => onToggleTarget(command, target)}
                >
                  <MatrixHarnessIcon label={target.label} logoKey={target.id === "claude" ? "claude" : target.id} harness={target.id} />
                </MatrixHarnessCellTarget>
              </UiTooltip>
            </td>
          );
        })}
        <td className="matrix-table__cell matrix-table__cell--compact"><SlashMatrixTargetStack command={command} targets={targets} /></td>
        <td className="matrix-table__cell matrix-table__cell--coverage">
          <span className="matrix-table__coverage" aria-label={`Active on ${enabled.size} of ${targets.length} targets`}>
            <span className="matrix-table__coverage-count">{enabled.size}</span>
            <span className="matrix-table__coverage-total" aria-hidden="true">{" / "}{targets.length}</span>
          </span>
        </td>
      </tr>
    );
  }

  const { review } = entry;
  const primaryAction = primaryReviewAction(review);
  const isPending = primaryAction ? pendingReviewKey === reviewKey(review.target, review.name, primaryAction) : false;
  const actionLabel = copy.review.actionLabel(primaryAction);
  const isDisabled = !primaryAction || isPending;
  return (
    <tr className="matrix-table__row" data-checked={checked ? "true" : undefined}>
      <td className="matrix-table__cell matrix-table__cell--checkbox">
        <CardSelectCheckbox
          checked={checked}
          disabled={isDisabled}
          label={checked ? `Deselect ${review.name}` : `Select ${review.name}`}
          onToggle={() => onToggleChecked(review.reviewRef)}
        />
      </td>
      <td className="matrix-table__cell matrix-table__cell--identity">
        <button type="button" className="mcp-matrix__server-button" aria-label={`Open detail for ${review.name}`} onClick={() => onOpenReview(review)}>
          <span className="matrix-table__name-row"><span className="matrix-table__name-text">{review.name}</span></span>
          <span className="matrix-table__description">{copy.review.metaText(review)}</span>
        </button>
      </td>
      <td className="matrix-table__cell matrix-table__cell--star" />
      {targets.map((target) => {
        const isTarget = review.target === target.id;
        const title = isTarget ? copy.review.metaText(review) : `Not found in ${target.label}`;
        return (
          <td key={target.id} className="matrix-table__cell matrix-table__cell--harness">
            <MatrixHarnessCellTarget
              state={isTarget ? "observed" : "empty"}
              ariaLabel={title}
              title={title}
              disabled={!isTarget}
              onClick={isTarget ? () => onOpenReview(review) : undefined}
            >
              {isTarget ? <MatrixHarnessIcon label={target.label} logoKey={target.id === "claude" ? "claude" : target.id} harness={target.id} /> : "—"}
            </MatrixHarnessCellTarget>
          </td>
        );
      })}
      <td className="matrix-table__cell matrix-table__cell--compact"><ReviewHarnessStack review={review} /></td>
      <td className="matrix-table__cell matrix-table__cell--coverage">
        <button type="button" className="action-pill action-pill--accent" disabled={isDisabled} title={primaryAction ? copy.review.actionTitle(primaryAction) : review.error ?? copy.review.cannotUpdate} onClick={() => onReviewAction(review)}>
          {isPending ? <Loader2 size={12} className="card-action-spinner" aria-hidden="true" /> : null}
          {actionLabel}
        </button>
      </td>
    </tr>
  );
}

function sortEntries(entries: SlashCommandInventoryEntry[], sort: SlashMatrixSortState): SlashCommandInventoryEntry[] {
  const direction = sort.direction === "asc" ? 1 : -1;
  if (sort.key === "name") {
    return [...entries].sort((left, right) => entryName(left).localeCompare(entryName(right)) * direction);
  }
  if (sort.key === "coverage") {
    return [...entries].sort((left, right) => coverage(left) - coverage(right) || entryName(left).localeCompare(entryName(right)) * direction);
  }
  const targetKey = sort.key;
  if (typeof targetKey === "string") return [...entries];
  return [...entries].sort((left, right) => {
    const leftValue = left.kind === "managed" && syncedTargetIds(left.command).has(targetKey.target) ? 1 : 0;
    const rightValue = right.kind === "managed" && syncedTargetIds(right.command).has(targetKey.target) ? 1 : 0;
    return (leftValue - rightValue) * direction || entryName(left).localeCompare(entryName(right));
  });
}

function entryName(entry: SlashCommandInventoryEntry): string {
  return entry.kind === "managed" ? entry.command.name : entry.review.name;
}

function coverage(entry: SlashCommandInventoryEntry): number {
  return entry.kind === "managed" ? syncedTargetIds(entry.command).size : 0;
}

function SlashMatrixTargetStack({ command, targets }: { command: SlashCommandDto; targets: SlashTargetDto[] }) {
  const enabledTargets = enabledTargetsForCommand(command, targets);
  return (
    <div className="skill-card__harness-row">
      <div className="harness-stack" aria-label={`Enabled on ${enabledTargets.length} targets`}>
        {enabledTargets.map((target, index) => {
          const presentation = getHarnessPresentation(target.id === "claude" ? "claude" : target.id);
          return (
            <UiTooltip key={target.id} content={target.label}>
              <span className="harness-stack__item" style={{ zIndex: enabledTargets.length - index }}>
                {presentation ? <img src={presentation.logoSrc} alt="" aria-hidden="true" /> : <span className="harness-stack__fallback">{target.label.slice(0, 1)}</span>}
              </span>
            </UiTooltip>
          );
        })}
      </div>
      <span className="skill-card__harness-count">{enabledTargets.length}/{targets.length}</span>
    </div>
  );
}

function ReviewHarnessStack({ review }: { review: SlashCommandReviewDto }) {
  const presentation = getHarnessPresentation(review.target === "claude" ? "claude" : review.target);
  return (
    <div className="harness-stack" aria-label={review.targetLabel}>
      <UiTooltip content={review.targetLabel}>
        <span className="harness-stack__item">
          {presentation ? <img src={presentation.logoSrc} alt="" aria-hidden="true" /> : <span className="harness-stack__fallback">{review.targetLabel.slice(0, 1)}</span>}
        </span>
      </UiTooltip>
    </div>
  );
}
