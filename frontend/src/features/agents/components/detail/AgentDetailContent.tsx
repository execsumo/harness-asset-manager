import "../../agents.css";
import { lazy, Suspense, useEffect, useId, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import { DetailHeader } from "../../../../components/detail/DetailHeader";
import { DetailSection } from "../../../../components/detail/DetailSection";
import { ErrorBanner } from "../../../../components/ErrorBanner";
import { LoadingSpinner } from "../../../../components/LoadingSpinner";
import { ConfirmActionDialog } from "../../../../components/ConfirmActionDialog";
import { DocumentSection } from "../../../../components/detail/editing/DocumentSection";
import {
  FrontmatterEditor,
  parseFrontmatterFromYaml,
  type KnownFieldConfig,
  type OtherFrontmatterEntry,
} from "../../../../components/detail/editing/FrontmatterEditor";
import { useToast } from "../../../../components/Toast";
import { useFormatPath } from "../../../../lib/paths";
import { DetailBindingIdentity, type DetailBindingTone } from "../../../../components/detail/DetailBindingIdentity";
import { UiTooltip } from "../../../../components/ui/UiTooltip";
import { useAdoptAgentMutation, useDeleteAgentMutation, useUpdateAgentMutation } from "../../api/queries";
import type { AgentDetailDto } from "../../api/types";

const MarkdownDocument = lazy(() => import("../../../../components/MarkdownDocument"));

interface AgentDetailContentProps {
  detail: AgentDetailDto;
  pendingPerHarnessKeys: ReadonlySet<string>;
  onToggleHarness: (ref: string, harness: string, disable: boolean) => Promise<void>;
  actionErrorMessage: string | null;
  onClose: () => void;
  onDismissActionError: () => void;
}

export function AgentDetailContent({
  detail,
  pendingPerHarnessKeys,
  onToggleHarness,
  actionErrorMessage,
  onClose,
  onDismissActionError,
}: AgentDetailContentProps) {
  const headingId = useId();
  const formatPath = useFormatPath();
  const { toast } = useToast();
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [discardDialogOpen, setDiscardDialogOpen] = useState(false);
  
  const deleteMutation = useDeleteAgentMutation();
  const updateMutation = useUpdateAgentMutation();
  const adoptMutation = useAdoptAgentMutation();
  const [adoptDialogOpen, setAdoptDialogOpen] = useState(false);
  
  const [localActionError, setLocalActionError] = useState<string | null>(null);
  const errorMessage = actionErrorMessage || localActionError;
  const dismissError = () => {
    onDismissActionError();
    setLocalActionError(null);
  };

  // Frontmatter & Document editing state
  const initialOtherEntries = useMemo<OtherFrontmatterEntry[]>(() => {
    return (detail.configuration || [])
      .filter((c) => c.key !== "name" && c.key !== "description" && c.key !== "tools")
      .map((c, idx) => ({
        id: `entry-${idx}-${c.key}`,
        key: c.key,
        value: c.value,
      }));
  }, [detail.configuration]);

  const [documentMode, setDocumentMode] = useState<"preview" | "edit">("preview");
  const [frontmatterMode, setFrontmatterMode] = useState<"structured" | "raw">("structured");
  const [name, setName] = useState(detail.name);
  const [description, setDescription] = useState(detail.description);
  const [toolsStr, setToolsStr] = useState(detail.tools.join(", "));
  const [otherEntries, setOtherEntries] = useState<OtherFrontmatterEntry[]>(initialOtherEntries);
  const [rawYaml, setRawYaml] = useState("");
  const [prompt, setPrompt] = useState(detail.prompt);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    setName(detail.name);
    setDescription(detail.description);
    setToolsStr(detail.tools.join(", "));
    setOtherEntries(
      (detail.configuration || [])
        .filter((c) => c.key !== "name" && c.key !== "description" && c.key !== "tools")
        .map((c, idx) => ({
          id: `entry-${idx}-${c.key}`,
          key: c.key,
          value: c.value,
        })),
    );
    setPrompt(detail.prompt);
    setSaveError(null);
  }, [detail.ref]);

  const knownFields: KnownFieldConfig[] = useMemo(
    () => [
      {
        key: "name",
        label: "Agent Name",
        value: name,
        onChange: setName,
      },
      {
        key: "description",
        label: "Description",
        value: description,
        onChange: setDescription,
      },
      {
        key: "tools",
        label: "Tools (comma-separated)",
        value: toolsStr,
        onChange: setToolsStr,
        placeholder: "e.g. bash, edit, grep",
      },
    ],
    [name, description, toolsStr],
  );

  const isDirty = useMemo(() => {
    if (name !== detail.name) return true;
    if (description !== detail.description) return true;
    if (toolsStr !== detail.tools.join(", ")) return true;
    if (prompt !== detail.prompt) return true;

    if (otherEntries.length !== initialOtherEntries.length) return true;
    for (let i = 0; i < otherEntries.length; i++) {
      if (
        otherEntries[i].key !== initialOtherEntries[i].key ||
        otherEntries[i].value !== initialOtherEntries[i].value
      ) {
        return true;
      }
    }
    return false;
  }, [name, description, toolsStr, prompt, otherEntries, detail, initialOtherEntries]);

  const handleCancelEdit = () => {
    setName(detail.name);
    setDescription(detail.description);
    setToolsStr(detail.tools.join(", "));
    setOtherEntries(initialOtherEntries);
    setPrompt(detail.prompt);
    setSaveError(null);
    setFrontmatterMode("structured");
  };

  const handleSaveDocument = async () => {
    setSaveError(null);

    let finalName = name;
    let finalDesc = description;
    let finalToolsStr = toolsStr;
    let finalOther = otherEntries;

    if (frontmatterMode === "raw") {
      const parsed = parseFrontmatterFromYaml(rawYaml, ["name", "description", "tools"]);
      if (parsed.error) {
        setSaveError(parsed.error);
        return;
      }
      finalName = parsed.known.name ?? name;
      finalDesc = parsed.known.description ?? description;
      finalToolsStr = parsed.known.tools ?? toolsStr;
      finalOther = parsed.other;
      setName(finalName);
      setDescription(finalDesc);
      setToolsStr(finalToolsStr);
      setOtherEntries(finalOther);
    }

    if (!finalName.trim()) {
      setSaveError("Agent name cannot be empty.");
      return;
    }

    const toolsList = finalToolsStr
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);

    const metadataPayload = finalOther
      .filter((e) => e.key.trim().length > 0)
      .map((e) => ({ key: e.key.trim(), value: e.value }));

    try {
      await updateMutation.mutateAsync({
        ref: detail.ref,
        request: {
          name: finalName.trim(),
          description: finalDesc.trim(),
          prompt: prompt,
          tools: toolsList,
          metadata: metadataPayload,
        },
      });
      toast(`Successfully updated ${finalName.trim()}`);
      setFrontmatterMode("structured");
      setDocumentMode("preview");
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save agent.");
    }
  };

  const handleRequestClose = () => {
    if (isDirty) {
      setDiscardDialogOpen(true);
    } else {
      onClose();
    }
  };

  const handleToggleHarness = async (harness: string, currentState: "enabled" | "disabled" | "unsupported") => {
    if (currentState === "unsupported") return;
    setLocalActionError(null);
    try {
      await onToggleHarness(detail.ref, harness, currentState === "enabled");
    } catch (err) {
      setLocalActionError(err instanceof Error ? err.message : "Failed to toggle harness");
    }
  };

  const handleDelete = async () => {
    setLocalActionError(null);
    try {
      const promise = deleteMutation.mutateAsync(detail.ref);
      setDeleteDialogOpen(false);
      onClose();
      await promise;
    } catch (err) {
      setLocalActionError(err instanceof Error ? err.message : "Failed to delete agent");
      setDeleteDialogOpen(false);
    }
  };

  const isDeleting = deleteMutation.isPending;

  return (
    <>
      <div className="skill-detail-shell__chrome">
        <div className="skill-detail__chrome">
          <DetailHeader
            title={<h2 id={headingId}>{detail.name}</h2>}
            closeLabel="Close"
            onClose={handleRequestClose}
          />
          {errorMessage ? (
            <ErrorBanner message={errorMessage} onDismiss={dismissError} />
          ) : null}
          {saveError ? (
            <ErrorBanner message={saveError} onDismiss={() => setSaveError(null)} />
          ) : null}
        </div>
      </div>
      
      <div
        className="skill-detail-shell__body ui-scrollbar"
        aria-labelledby={headingId}
      >
        <div className="detail-sheet__body">
          <DetailSection heading="About">
            <p className="skill-detail__copy">
              {detail.description || "No description provided."}
            </p>
          </DetailSection>

          <DocumentSection
            title="Document"
            mode={documentMode}
            onModeChange={setDocumentMode}
            editable={detail.canEdit}
            previewContent={(
              <Suspense fallback={<LoadingSpinner size="sm" label="Loading document" />}>
                <MarkdownDocument markdown={detail.prompt} />
              </Suspense>
            )}
            editFrontmatter={(
              <FrontmatterEditor
                knownFields={knownFields}
                otherEntries={otherEntries}
                onChangeOtherEntries={setOtherEntries}
                rawYaml={rawYaml}
                onChangeRawYaml={setRawYaml}
                mode={frontmatterMode}
                onModeChange={setFrontmatterMode}
                validationError={null}
                disabled={updateMutation.isPending}
              />
            )}
            bodyValue={prompt}
            onBodyChange={setPrompt}
            bodyLabel="System Prompt"
            bodyPlaceholder="Agent system prompt..."
            isDirty={isDirty}
            isSaving={updateMutation.isPending}
            saveDisabled={!name.trim()}
            onSave={handleSaveDocument}
            onCancel={handleCancelEdit}
            saveLabel="Save"
            cancelLabel="Cancel"
            unsavedLabel="Unsaved changes"
          />

          <DetailSection heading="Harnesses">
            <div className="detail-sheet__bindings" aria-label={`Harness access for ${detail.name}`}>
              {detail.harnesses.map(h => {
                const pending = pendingPerHarnessKeys.has(`${detail.ref}:${h.harness}`);
                const isUnsupported = h.state === "unsupported";
                let tone: DetailBindingTone = "disabled";
                let statusLabel = "Disabled";
                if (h.state === "enabled") {
                  tone = "enabled";
                  statusLabel = "Enabled";
                } else if (isUnsupported) {
                  tone = "disabled";
                  statusLabel = "Unsupported";
                }

                return (
                  <div
                    key={h.harness}
                    className="detail-sheet__binding-row"
                    data-state={h.state}
                    data-pending={pending || undefined}
                  >
                    <DetailBindingIdentity
                      harness={h.harness}
                      label={h.label}
                      logoKey={h.logoKey}
                      statusLabel={statusLabel}
                      tone={tone}
                    />
                    <div className="detail-sheet__binding-actions">
                      {isUnsupported ? (
                        <UiTooltip content={h.detail || "Not supported"}>
                          <span className="action-pill agent-detail__unsupported-pill">
                            Enable
                          </span>
                        </UiTooltip>
                      ) : (
                        <button
                          type="button"
                          className={`action-pill ${h.state === "enabled" ? "action-pill--danger" : "action-pill--accent"}`}
                          disabled={pending || isDeleting}
                          onClick={() => handleToggleHarness(h.harness, h.state)}
                        >
                          {pending ? <Loader2 size={12} className="card-action-spinner" aria-hidden="true" /> : null}
                          {h.state === "enabled" ? "Disable" : "Enable"}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </DetailSection>

          <DetailSection heading="Locations">
            <div className="skill-detail__locations">
              {!detail.storePath ? (
                <p className="skill-detail__context-note">
                  This agent is not managed by Harness Asset Manager yet. Edits save directly to
                  the harness file below; adopt it to manage it across harnesses.
                </p>
              ) : null}
              {detail.storePath ? (
                <article className="skill-detail__location">
                  <div className="skill-detail__location-header">
                    <strong>Harness Asset Manager's copy</strong>
                  </div>
                  <p className="skill-detail__location-path">{formatPath(detail.storePath)}</p>
                </article>
              ) : null}
              {detail.harnesses.filter(h => h.state === "enabled" || (!detail.storePath && h.state !== "unsupported")).map(h => (
                <article key={h.harness} className="skill-detail__location">
                  <div className="skill-detail__location-header">
                    <strong>{h.label}</strong>
                  </div>
                  <p className="skill-detail__location-path">{formatPath(h.path)}</p>
                  {h.installMethod === "rendered" ? (
                    <p className="skill-detail__location-note agent-detail__rendered-note">
                      This agent is rendered as a TOML file. Local edits to it will be overwritten on re-enable.
                    </p>
                  ) : null}
                </article>
              ))}
            </div>
          </DetailSection>
        </div>
      </div>

      {detail.canDelete ? (
        <footer className="skill-detail-shell__footer" aria-label="Agent actions">
          <button
            type="button"
            className="action-pill action-pill--md action-pill--danger"
            disabled={isDeleting}
            onClick={() => setDeleteDialogOpen(true)}
          >
            {isDeleting ? <Loader2 size={14} className="animate-spin agent-action-spinner" /> : null}
            Delete
          </button>
        </footer>
      ) : null}

      {detail.canDelete ? (
        <ConfirmActionDialog
          open={deleteDialogOpen}
          title="Delete Agent"
          description={<>Are you sure you want to delete <strong>{detail.name}</strong>? This action cannot be undone.</>}
          confirmLabel="Delete Agent"
          pendingLabel="Deleting"
          isPending={isDeleting}
          onOpenChange={setDeleteDialogOpen}
          onConfirm={handleDelete}
        />
      ) : null}

      <ConfirmActionDialog
        open={discardDialogOpen}
        title="Discard changes?"
        description="You have unsaved changes that will be lost. Are you sure you want to discard them?"
        confirmLabel="Discard changes"
        pendingLabel="Discarding..."
        isPending={false}
        confirmTone="danger"
        onOpenChange={setDiscardDialogOpen}
        onConfirm={() => {
          setDiscardDialogOpen(false);
          onClose();
        }}
      />
    </>
  );
}
