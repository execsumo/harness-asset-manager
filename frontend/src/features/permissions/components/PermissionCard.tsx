import { useMemo } from "react";
import { Loader2, Power, Trash2 } from "lucide-react";

import { CardMenu, type CardMenuItem } from "../../../components/cards/CardMenu";
import { OverflowTooltipText } from "../../../components/ui/OverflowTooltipText";
import type { PermissionInventoryColumnDto, PermissionInventoryEntryDto } from "../../permissions/api/management-types";
import { usePermissionsCopy } from "../../permissions/i18n";
import { isPermissionsHarnessAddressable } from "../model/selectors";
import { PermissionsHarnessLogoStack } from "./PermissionsHarnessLogoStack";
import { PermissionsStatusChip } from "./PermissionsStatusChip";

interface PermissionCardProps {
  entry: PermissionInventoryEntryDto;
  columns: PermissionInventoryColumnDto[];
  pending: boolean;
  onOpenDetail: (id: string) => void;
  onSetHarnesses: (id: string, target: "enabled" | "disabled") => void;
  onRequestUninstall: (id: string) => void;
}

function managedCount(
  entry: PermissionInventoryEntryDto,
  addressable: ReadonlySet<string>,
): number {
  return entry.sightings.filter(
    (b) => addressable.has(b.harness) && b.state === "managed",
  ).length;
}

function hasDifferentConfig(
  entry: PermissionInventoryEntryDto,
  addressable: ReadonlySet<string>,
): boolean {
  return entry.sightings.some(
    (b) => addressable.has(b.harness) && b.state === "drifted",
  );
}

export function PermissionCard({
  entry,
  columns,
  pending,
  onOpenDetail,
  onSetHarnesses,
  onRequestUninstall,
}: PermissionCardProps) {
  const copy = usePermissionsCopy();
  const addressableHarnesses = useMemo(
    () => new Set(columns.filter(isPermissionsHarnessAddressable).map((c) => c.harness)),
    [columns],
  );
  const enabled = managedCount(entry, addressableHarnesses);
  const total = addressableHarnesses.size;
  const differentConfig = hasDifferentConfig(entry, addressableHarnesses);
  const allEnabled = total > 0 && enabled === total;
  const target: "enabled" | "disabled" = allEnabled ? "disabled" : "enabled";

  const menuItems = useMemo<CardMenuItem[]>(
    () => [
      {
        key: "uninstall",
        label: copy.detail.uninstall,
        icon: <Trash2 size={13} aria-hidden="true" />,
        destructive: true,
        onSelect: () => onRequestUninstall(entry.id),
      },
    ],
    [copy.detail.uninstall, entry.id, onRequestUninstall],
  );

  return (
    <article
      className="skill-card permission-card"
      data-pending={pending || undefined}
      role="button"
      tabIndex={0}
      onClick={() => onOpenDetail(entry.id)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onOpenDetail(entry.id);
        }
      }}
      aria-label={copy.detail.openDetail(entry.displayName)}
    >
      <div className="skill-card__head permission-card__head">
        <OverflowTooltipText as="h3" className="skill-card__name">
          {entry.displayName}
        </OverflowTooltipText>
        {entry.spec && <PermissionsStatusChip decision={entry.spec.decision} scope={entry.spec.scope} />}
        <div className="permission-card__actions">
          <CardMenu
            label={copy.detail.moreActions(entry.displayName)}
            items={menuItems}
            disabled={pending}
          />
        </div>
      </div>

      <p className="permission-card__command">
        <code>{entry.spec?.pattern ?? "—"}</code>
      </p>

      {entry.spec?.description ? (
        <OverflowTooltipText as="p" className="skill-card__description permission-card__detail">
          {entry.spec.description}
        </OverflowTooltipText>
      ) : null}

      <div className="skill-card__footer">
        <PermissionsHarnessLogoStack bindings={entry.sightings} columns={columns} />
        <button
          type="button"
          className="action-pill"
          disabled={pending || total === 0 || !entry.canEnable}
          onClick={(event) => {
            event.stopPropagation();
            if (differentConfig) {
              onOpenDetail(entry.id);
              return;
            }
            onSetHarnesses(entry.id, target);
          }}
        >
          {pending ? (
            <Loader2 size={12} className="card-action-spinner" aria-hidden="true" />
          ) : (
            <Power size={12} aria-hidden="true" />
          )}
          {differentConfig ? copy.detail.resolveConfig : target === "enabled" ? "Apply to all" : "Remove from all"}
        </button>
      </div>
    </article>
  );
}
