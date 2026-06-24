import type { PermissionInventoryColumnDto, PermissionInventoryEntryDto } from "../api/management-types";
import { PermissionCard } from "./PermissionCard";

interface PermissionCardListProps {
  entries: PermissionInventoryEntryDto[];
  columns: PermissionInventoryColumnDto[];
  pendingPermissionKeys: ReadonlySet<string>;
  onOpenDetail: (id: string) => void;
  onSetHarnesses: (id: string, target: "enabled" | "disabled") => void;
  onRequestUninstall: (id: string) => void;
  ariaLabel?: string;
}

export function PermissionCardList({
  entries,
  columns,
  pendingPermissionKeys,
  onOpenDetail,
  onSetHarnesses,
  onRequestUninstall,
  ariaLabel,
}: PermissionCardListProps) {
  return (
    <section className="skill-grid" aria-label={ariaLabel ?? "Permissions list"}>
      {entries.map((entry) => (
        <PermissionCard
          key={entry.id}
          entry={entry}
          columns={columns}
          pending={pendingPermissionKeys.has(entry.id)}
          onOpenDetail={onOpenDetail}
          onSetHarnesses={onSetHarnesses}
          onRequestUninstall={onRequestUninstall}
        />
      ))}
    </section>
  );
}
