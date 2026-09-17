import { useEffect, useState } from "react";
import * as Popover from "@radix-ui/react-popover";
import { ChevronDown, UserSquare2 } from "lucide-react";

import { LoadingSpinner } from "./LoadingSpinner";

export interface AgentAttachmentInfo {
  ref: string;
  name: string;
}

export interface BulkAgentPopoverProps {
  knownAgents?: AgentAttachmentInfo[];
  onApply: (agentRefs: string[], mode: "attach" | "detach") => Promise<void>;
  disabled?: boolean;
  pending?: boolean;
}

export function BulkAgentPopover({
  knownAgents = [],
  onApply,
  disabled = false,
  pending = false,
}: BulkAgentPopoverProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [stagedRefs, setStagedRefs] = useState<Set<string>>(new Set());
  const [mode, setMode] = useState<"attach" | "detach">("attach");

  useEffect(() => {
    if (!isOpen) {
      setStagedRefs(new Set());
      setMode("attach");
    }
  }, [isOpen]);

  const toggleAgent = (ref: string) => {
    setStagedRefs((prev) => {
      const next = new Set(prev);
      if (next.has(ref)) next.delete(ref);
      else next.add(ref);
      return next;
    });
  };

  const handleApply = async () => {
    if (stagedRefs.size === 0) return;
    await onApply(Array.from(stagedRefs), mode);
    setIsOpen(false);
  };

  const canApply = stagedRefs.size > 0;

  return (
    <Popover.Root open={isOpen} onOpenChange={setIsOpen}>
      <Popover.Trigger asChild>
        <button
          type="button"
          className="bulk-bar__action"
          disabled={disabled}
          aria-label="Attach to agents"
        >
          {pending ? (
            <LoadingSpinner size="sm" label="Updating agents" />
          ) : (
            <UserSquare2 size={15} />
          )}
          Attach to agents
          <ChevronDown size={13} aria-hidden="true" />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content className="ui-popup" align="end" sideOffset={8}>
          <div className="ui-popup__header">
            <h3 className="ui-popup__title">Attach to agents</h3>
          </div>
          
          <div className="ui-popup__body" style={{ minWidth: 280 }}>
            {knownAgents.length === 0 ? (
              <p className="ui-popup__empty">No agents available.</p>
            ) : (
              <ul className="ui-menu__list" style={{ maxHeight: 200, overflowY: "auto", margin: "0 -12px" }}>
                {knownAgents.map((agent) => {
                  const isStaged = stagedRefs.has(agent.ref);
                  return (
                    <li key={agent.ref}>
                      <label className="ui-menu__item">
                        <span className="ui-menu__icon">
                          <input
                            type="checkbox"
                            checked={isStaged}
                            onChange={() => toggleAgent(agent.ref)}
                            aria-label={agent.name}
                          />
                        </span>
                        <span className="ui-menu__label">{agent.name}</span>
                      </label>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          <div className="ui-popup__footer" style={{ display: "flex", gap: "8px", justifyContent: "space-between" }}>
            <select 
              value={mode} 
              onChange={(e) => setMode(e.target.value as "attach" | "detach")}
              className="ui-input"
              style={{ flex: 1, padding: "4px 8px" }}
            >
              <option value="attach">Attach to selected</option>
              <option value="detach">Detach from selected</option>
            </select>
            <button
              type="button"
              className="ui-button ui-button--primary"
              disabled={!canApply || pending}
              onClick={() => void handleApply()}
            >
              Preview
            </button>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
