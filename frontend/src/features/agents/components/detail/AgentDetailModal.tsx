import * as Dialog from "@radix-ui/react-dialog";
import { AgentDetailView } from "./AgentDetailView";
import type { AdoptedSkillOption, SkillTagOption } from "./AgentSkillsFieldEditor";

interface AgentDetailModalProps {
  open: boolean;
  agentRef: string | null;
  knownTags?: string[];
  knownSkills?: AdoptedSkillOption[];
  tagOptions?: SkillTagOption[];
  pendingPerHarnessKeys: ReadonlySet<string>;
  onToggleHarness: (ref: string, harness: string, disable: boolean) => Promise<void>;
  onClose: () => void;
}

export function AgentDetailModal({
  open,
  agentRef,
  knownTags,
  knownSkills,
  tagOptions,
  pendingPerHarnessKeys,
  onToggleHarness,
  onClose,
}: AgentDetailModalProps) {
  return (
    <Dialog.Root open={open && Boolean(agentRef)} onOpenChange={(next) => (next ? null : onClose())}>
      <Dialog.Portal>
        <Dialog.Overlay className="dialog-overlay" />
        <Dialog.Content className="detail-sheet skill-detail-modal">
          <Dialog.Title className="u-visually-hidden">Agent details</Dialog.Title>
          <Dialog.Description className="u-visually-hidden">
            Inspect and manage this agent across harnesses.
          </Dialog.Description>
          {agentRef ? (
            <AgentDetailView
              agentRef={agentRef}
              knownTags={knownTags}
              knownSkills={knownSkills}
              tagOptions={tagOptions}
              pendingPerHarnessKeys={pendingPerHarnessKeys}
              onToggleHarness={onToggleHarness}
              onClose={onClose}
            />
          ) : null}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
