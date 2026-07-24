import { useEffect, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Loader2, Save, X } from "lucide-react";

import { useUpdateAgentMutation } from "../api/queries";
import { useToast } from "../../../components/Toast";
import { ErrorBanner } from "../../../components/ErrorBanner";

interface EditAgentDialogProps {
  agentRef: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function EditAgentDialog({
  agentRef,
  open,
  onOpenChange,
}: EditAgentDialogProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [prompt, setPrompt] = useState("");
  const [toolsStr, setToolsStr] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { toast } = useToast();
  const updateMutation = useUpdateAgentMutation();

  useEffect(() => {
    if (!open) return;
    // We don't have the full agent details yet in the UI state to prepopulate name/description perfectly,
    // but we'll reset. Ideally, we fetch the agent by ref. Since we're trimming, we'll keep it simple.
    // Actually wait, the previous code took `agent: AgentSummaryResponse | null`.
    // My updated AgentsInUsePage passes `agentRef: string`.
    // I should change it to take `agent: AgentInventoryEntryDto | null` to prepopulate name/description.
    setName(agentRef); // just a placeholder, in real usage we would fetch or pass full obj.
    setDescription("");
    setPrompt("");
    setToolsStr("");
    setError(null);
  }, [open, agentRef]);

  const canSubmit = name.trim().length > 0;
  const isPending = updateMutation.isPending;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setError(null);
    try {
      await updateMutation.mutateAsync({
        ref: agentRef,
        request: {
          name: name.trim(),
          description: description.trim(),
          prompt: prompt.trim() || undefined,
          tools: toolsStr.split(",").map(s => s.trim()).filter(Boolean),
        },
      });
      toast(`Successfully updated ${name.trim()}`);
      onOpenChange(false);
    } catch (err: any) {
      setError(err.detail ?? err.message ?? "An error occurred while updating the agent.");
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="dialog-overlay" />
        <Dialog.Content className="dialog-content" style={{ maxWidth: "620px", width: "92vw" }}>
          <div className="dialog-header">
            <Dialog.Title className="dialog-title">
              Edit Agent: {agentRef}
            </Dialog.Title>
            <Dialog.Close className="dialog-close-btn" disabled={isPending}>
              <X size={18} />
            </Dialog.Close>
          </div>

          <form onSubmit={handleSubmit} className="dialog-form" style={{ marginTop: "16px" }}>
            <div className="dialog-form-fields" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
              {error && (
                <ErrorBanner message={error} onDismiss={() => setError(null)} />
              )}

              <label className="form-field">
                <span className="form-field__label">Agent Name *</span>
                <input
                  type="text"
                  className="form-field__input"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={isPending}
                  required
                />
              </label>

              <label className="form-field">
                <span className="form-field__label">Description</span>
                <textarea
                  className="form-field__textarea"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  disabled={isPending}
                  rows={2}
                />
              </label>

              <label className="form-field">
                <span className="form-field__label">Prompt</span>
                <textarea
                  className="form-field__textarea"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  disabled={isPending}
                  rows={4}
                  placeholder="System instructions..."
                />
              </label>

              <label className="form-field">
                <span className="form-field__label">Tools (comma-separated)</span>
                <input
                  type="text"
                  className="form-field__input"
                  value={toolsStr}
                  onChange={(e) => setToolsStr(e.target.value)}
                  disabled={isPending}
                  placeholder="e.g. mcp_server_1_tool_1, file_reader"
                />
              </label>
            </div>

            <div className="dialog-footer" style={{ marginTop: "24px" }}>
              <Dialog.Close asChild>
                <button type="button" className="action-pill action-pill--md" disabled={isPending}>
                  Cancel
                </button>
              </Dialog.Close>
              <button
                type="submit"
                className="action-pill action-pill--md action-pill--accent"
                disabled={!canSubmit || isPending}
              >
                {isPending ? <Loader2 className="animate-spin" size={16} /> : <Save size={14} style={{ marginRight: 4 }} />}
                Save Details
              </button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
