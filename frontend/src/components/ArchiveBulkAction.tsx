import { useState } from "react";
import { ConfirmActionDialog } from "./ConfirmActionDialog";

export function ArchiveBulkAction({ count, archived, pending, onChange }: {
  count: number;
  archived: boolean;
  pending: boolean;
  onChange: (archived: boolean) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  if (!count) return null;
  return <>
    <button type="button" className="bulk-bar__action" disabled={pending} onClick={() => archived ? void onChange(false) : setOpen(true)}>{archived ? "Unarchive" : "Archive"}</button>
    <ConfirmActionDialog open={open} title={`Archive ${count} selected?`} description="This removes their harness bindings while keeping their content and tags." confirmLabel="Archive" pendingLabel="Archiving" isPending={pending} onOpenChange={setOpen} onConfirm={async () => { await onChange(true); setOpen(false); }} />
  </>;
}
