import { useEffect, useState } from "react";
import * as Popover from "@radix-ui/react-popover";
import { Check, CircleSlash2, ChevronDown, UserSquare2 } from "lucide-react";

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
    <Popover.Root
      open={isOpen}
      onOpenChange={(open) => {
        if (disabled && open) return;
        setIsOpen(open);
      }}
    >
      <Popover.Trigger asChild>
        <button
          type="button"
          className="bulk-bar__action"
          disabled={disabled}
          aria-label="Agents"
        >
          {pending ? (
            <LoadingSpinner size="sm" label="Updating agents" />
          ) : (
            <UserSquare2 size={15} />
          )}
          Agents
          <ChevronDown size={13} aria-hidden="true" />
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content className="ui-popup bulk-agent-popover" align="end" sideOffset={8}>
          <div className="bulk-agent-popover__header">
            <h3 className="bulk-agent-popover__title">Agents</h3>
          </div>

          <div className="bulk-agent-popover__mode" aria-label="Agent action">
            <button
              type="button"
              className="action-pill action-pill--sm bulk-agent-popover__mode-button"
              data-selected={mode === "attach"}
              onClick={() => setMode("attach")}
              disabled={pending}
            >
              <Check size={13} aria-hidden="true" />
              Attach
            </button>
            <button
              type="button"
              className="action-pill action-pill--sm bulk-agent-popover__mode-button"
              data-selected={mode === "detach"}
              onClick={() => setMode("detach")}
              disabled={pending}
            >
              <CircleSlash2 size={13} aria-hidden="true" />
              Detach
            </button>
          </div>

          <div className="bulk-agent-popover__body">
            {knownAgents.length === 0 ? (
              <p className="bulk-agent-popover__empty">No agents available.</p>
            ) : (
              <ul className="bulk-agent-popover__list">
                {knownAgents.map((agent) => {
                  const isStaged = stagedRefs.has(agent.ref);
                  return (
                    <li key={agent.ref}>
                      <label className="bulk-agent-popover__item">
                        <span className="bulk-agent-popover__check-wrap">
                          <input
                            type="checkbox"
                            className="bulk-agent-popover__checkbox"
                            checked={isStaged}
                            onChange={() => toggleAgent(agent.ref)}
                            aria-label={agent.name}
                            disabled={pending}
                          />
                        </span>
                        <span className="bulk-agent-popover__label">{agent.name}</span>
                      </label>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>

          <div className="bulk-agent-popover__footer">
            <button
              type="button"
              className="action-pill action-pill--sm"
              onClick={() => setIsOpen(false)}
              disabled={pending}
            >
              Cancel
            </button>
            <button
              type="button"
              className="action-pill action-pill--sm action-pill--accent"
              disabled={!canApply || pending}
              onClick={() => void handleApply()}
            >
              {pending ? <LoadingSpinner size="sm" label="Applying" /> : "Apply"}
            </button>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
