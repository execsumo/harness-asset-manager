import { useEffect, useId, useMemo, useState } from "react";
import { Loader2, Star, Trash2 } from "lucide-react";

import { DetailBindingIdentity } from "../../../../components/detail/DetailBindingIdentity";
import { DetailHeader } from "../../../../components/detail/DetailHeader";
import { DetailSection } from "../../../../components/detail/DetailSection";
import { DetailTags } from "../../../../components/detail/DetailTags";
import { ErrorBanner } from "../../../../components/ErrorBanner";
import { ConfirmActionDialog } from "../../../../components/ConfirmActionDialog";
import { DocumentSection } from "../../../../components/detail/editing/DocumentSection";
import {
  FrontmatterEditor,
  parseFrontmatterFromYaml,
  type KnownFieldConfig,
  type OtherFrontmatterEntry,
} from "../../../../components/detail/editing/FrontmatterEditor";
import MarkdownDocument from "../../../../components/MarkdownDocument";
import { useToast } from "../../../../components/Toast";
import { useFormatPath } from "../../../../lib/paths";
import { useSetSlashCommandTagsMutation, useUpdateSlashCommandMutation } from "../../api/queries";
import type {
  SlashCommandDto,
  SlashSyncEntryDto,
  SlashTargetDto,
  SlashTargetId,
} from "../../api/types";
import { useSlashCommandsCopy, type SlashCommandsCopy } from "../../i18n";
import { syncedTargetIds } from "../../model/selectors";

interface SlashCommandDetailViewProps {
  command: SlashCommandDto;
  knownTags?: string[];
  targets: SlashTargetDto[];
  pendingName: string | null;
  pendingTarget: string | null;
  onClose: () => void;
  onDelete: (command: SlashCommandDto) => void;
  onToggleTarget: (command: SlashCommandDto, target: SlashTargetDto) => void;
}

export function SlashCommandDetailView({
  command,
  knownTags,
  targets,
  pendingName,
  pendingTarget,
  onClose,
  onDelete,
  onToggleTarget,
}: SlashCommandDetailViewProps) {
  const headingId = useId();
  const copy = useSlashCommandsCopy();
  const { toast } = useToast();
  const updateMutation = useUpdateSlashCommandMutation();
  const setTagsMutation = useSetSlashCommandTagsMutation();

  const commandPending = pendingName === command.name;
  const enabledTargetIds = useMemo(() => syncedTargetIds(command), [command]);
  const writtenEntries = useMemo(
    () => writtenLocationEntries(command.syncTargets, targets),
    [command.syncTargets, targets],
  );

  const isStarred = (command.tags || []).some((t) => t.toLowerCase() === "starred");

  const handleToggleStar = async () => {
    const nextTags = isStarred
      ? (command.tags || []).filter((t) => t.toLowerCase() !== "starred")
      : ["starred", ...(command.tags || []).filter((t) => t.toLowerCase() !== "starred")];
    try {
      await setTagsMutation.mutateAsync({
        name: command.name,
        tags: nextTags,
      });
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to toggle star.");
    }
  };

  const handleAddTag = async (newTag: string) => {
    const nextTags = [...(command.tags || []), newTag];
    await setTagsMutation.mutateAsync({
      name: command.name,
      tags: nextTags,
    });
  };

  const handleRemoveTag = async (tagToRemove: string) => {
    const nextTags = (command.tags || []).filter(
      (t) => t.toLowerCase() !== tagToRemove.toLowerCase(),
    );
    await setTagsMutation.mutateAsync({
      name: command.name,
      tags: nextTags,
    });
  };

  // Frontmatter & Document editing state
  const initialOtherEntries = useMemo<OtherFrontmatterEntry[]>(() => {
    return (command.metadata || []).map((m, idx) => ({
      id: `entry-${idx}-${m.key}`,
      key: m.key,
      value: m.value,
    }));
  }, [command.metadata]);

  const [documentMode, setDocumentMode] = useState<"preview" | "edit">("preview");
  const [frontmatterMode, setFrontmatterMode] = useState<"structured" | "raw">("structured");
  const [description, setDescription] = useState(command.description);
  const [prompt, setPrompt] = useState(command.prompt);
  const [otherEntries, setOtherEntries] = useState<OtherFrontmatterEntry[]>(initialOtherEntries);
  const [rawYaml, setRawYaml] = useState("");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [discardDialogOpen, setDiscardDialogOpen] = useState(false);

  useEffect(() => {
    setDescription(command.description);
    setPrompt(command.prompt);
    setOtherEntries(
      (command.metadata || []).map((m, idx) => ({
        id: `entry-${idx}-${m.key}`,
        key: m.key,
        value: m.value,
      })),
    );
    setSaveError(null);
  }, [command.name]);

  const knownFields: KnownFieldConfig[] = useMemo(
    () => [
      {
        key: "name",
        label: "Name (Immutable)",
        value: command.name,
        onChange: () => {},
        disabled: true,
      },
      {
        key: "description",
        label: "Description",
        value: description,
        onChange: setDescription,
      },
    ],
    [command.name, description],
  );

  const isDirty = useMemo(() => {
    if (description !== command.description) return true;
    if (prompt !== command.prompt) return true;

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
  }, [description, prompt, otherEntries, command, initialOtherEntries]);

  const handleCancelEdit = () => {
    setDescription(command.description);
    setPrompt(command.prompt);
    setOtherEntries(initialOtherEntries);
    setSaveError(null);
    setFrontmatterMode("structured");
  };

  const handleSaveDocument = async () => {
    setSaveError(null);

    let finalDesc = description;
    let finalOther = otherEntries;

    if (frontmatterMode === "raw") {
      const parsed = parseFrontmatterFromYaml(rawYaml, ["name", "description"]);
      if (parsed.error) {
        setSaveError(parsed.error);
        return;
      }
      finalDesc = parsed.known.description ?? description;
      finalOther = parsed.other;
      setDescription(finalDesc);
      setOtherEntries(finalOther);
    }

    if (!finalDesc.trim()) {
      setSaveError("Description cannot be empty.");
      return;
    }

    const metadataPayload = finalOther
      .filter((e) => e.key.trim().length > 0)
      .map((e) => ({ key: e.key.trim(), value: e.value }));

    const selectedTargets = Array.from(enabledTargetIds) as SlashTargetId[];

    try {
      await updateMutation.mutateAsync({
        name: command.name,
        body: {
          description: finalDesc.trim(),
          prompt: prompt,
          targets: selectedTargets,
          metadata: metadataPayload,
        },
      });
      toast(copy.detail.savedSuccess(command.name));
      setFrontmatterMode("structured");
      setDocumentMode("preview");
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save slash command.");
    }
  };

  const handleRequestClose = () => {
    if (isDirty) {
      setDiscardDialogOpen(true);
    } else {
      onClose();
    }
  };

  return (
    <>
      <div className="slash-command-detail-shell__chrome">
        <DetailHeader
          title={
            <h2 id={headingId} className="skill-detail__title">
              {command.name}
              <button
                type="button"
                className={`skill-star-btn ${isStarred ? "skill-star-btn--active" : ""}`}
                aria-label={isStarred ? `Unstar ${command.name}` : `Star ${command.name}`}
                onClick={handleToggleStar}
              >
                <Star
                  size={16}
                  className={`skill-star-icon ${isStarred ? "skill-star-icon--filled" : ""}`}
                />
              </button>
            </h2>
          }
          closeLabel={copy.detail.close}
          onClose={handleRequestClose}
        />
        {saveError ? (
          <ErrorBanner message={saveError} onDismiss={() => setSaveError(null)} />
        ) : null}
      </div>

      <div className="slash-command-detail-shell__body ui-scrollbar" aria-labelledby={headingId}>
        <div className="detail-sheet__body">
          <DetailSection heading={copy.detail.about ?? "About"}>
            <p className="skill-detail__copy">
              {command.description || copy.detail.noDescription}
            </p>
          </DetailSection>

          <DetailSection heading="Tags">
            <DetailTags
              tags={command.tags || []}
              knownTags={knownTags}
              canEdit={true}
              onAddTag={handleAddTag}
              onRemoveTag={handleRemoveTag}
              disabled={setTagsMutation.isPending}
            />
          </DetailSection>

          <DocumentSection
            title={copy.detail.document}
            mode={documentMode}
            onModeChange={setDocumentMode}
            previewContent={
              command.prompt ? (
                <MarkdownDocument markdown={command.prompt} />
              ) : (
                <p className="skill-detail__copy">{copy.detail.noPrompt}</p>
              )
            }
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
            bodyLabel="Prompt Body"
            bodyPlaceholder="Prompt content..."
            isDirty={isDirty}
            isSaving={updateMutation.isPending}
            saveDisabled={!description.trim() || !prompt.trim()}
            onSave={handleSaveDocument}
            onCancel={handleCancelEdit}
            saveLabel={copy.detail.save}
            cancelLabel={copy.detail.cancel}
            unsavedLabel={copy.detail.unsavedChanges}
          />

          <HarnessesSection
            command={command}
            targets={targets}
            enabledTargetIds={enabledTargetIds}
            commandPending={commandPending}
            pendingTarget={pendingTarget}
            onToggleTarget={onToggleTarget}
            copy={copy}
          />

          <LocationsSection entries={writtenEntries} targets={targets} copy={copy} />
        </div>
      </div>

      <footer className="slash-command-detail-shell__footer" aria-label={copy.detail.actionsAria}>
        <button
          type="button"
          className="action-pill action-pill--md action-pill--danger"
          disabled={commandPending}
          onClick={() => onDelete(command)}
        >
          <Trash2 size={13} aria-hidden="true" />
          {copy.detail.delete}
        </button>
      </footer>

      <ConfirmActionDialog
        open={discardDialogOpen}
        title={copy.detail.discardTitle}
        description={copy.detail.discardDescription}
        confirmLabel={copy.detail.discardConfirm}
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

function HarnessesSection({
  command,
  targets,
  enabledTargetIds,
  commandPending,
  pendingTarget,
  onToggleTarget,
  copy,
}: {
  command: SlashCommandDto;
  targets: SlashTargetDto[];
  enabledTargetIds: ReadonlySet<string>;
  commandPending: boolean;
  pendingTarget: string | null;
  onToggleTarget: (command: SlashCommandDto, target: SlashTargetDto) => void;
  copy: SlashCommandsCopy;
}) {
  return (
    <DetailSection heading={copy.detail.harnesses}>
      <div className="detail-sheet__bindings" aria-label={copy.detail.harnessesFor(command.name)}>
        {targets.map((target) => {
          const enabled = enabledTargetIds.has(target.id);
          const targetPending = commandPending && pendingTarget === target.id;
          return (
            <div
              key={target.id}
              className="detail-sheet__binding-row"
              data-state={enabled ? "enabled" : "disabled"}
              data-pending={targetPending ? "true" : undefined}
            >
              <DetailBindingIdentity
                harness={target.id}
                label={target.label}
                logoKey={logoKeyForHarness(target.id)}
                statusLabel={enabled ? copy.detail.enabled : copy.detail.disabled}
                tone={enabled ? "enabled" : "disabled"}
                visibleStatus={enabled ? copy.detail.enabled : null}
              />
              <div className="detail-sheet__binding-actions">
                <button
                  type="button"
                  className={`action-pill ${enabled ? "action-pill--danger" : "action-pill--accent"}`}
                  disabled={commandPending || !target.enabled}
                  onClick={() => onToggleTarget(command, target)}
                  aria-pressed={enabled}
                  aria-label={enabled ? copy.detail.disableTargetFor(target.label, command.name) : copy.detail.enableTargetFor(target.label, command.name)}
                >
                  {targetPending ? (
                    <Loader2 size={12} className="card-action-spinner" aria-hidden="true" />
                  ) : null}
                  {enabled ? copy.detail.disable : copy.detail.enable}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </DetailSection>
  );
}

function LocationsSection({
  entries,
  targets,
  copy,
}: {
  entries: SlashSyncEntryDto[];
  targets: SlashTargetDto[];
  copy: SlashCommandsCopy;
}) {
  const targetById = new Map(targets.map((target) => [target.id, target]));
  return (
    <DetailSection heading={copy.detail.locations}>
      {entries.length > 0 ? (
        <div className="detail-sheet__bindings">
          {entries.map((entry) => (
            <SlashCommandLocationRow
              key={`${entry.target}:${entry.path}`}
              entry={entry}
              target={targetById.get(entry.target)}
              copy={copy}
            />
          ))}
        </div>
      ) : (
        <p className="slash-review-detail__empty">{copy.detail.noHarnessLocations}</p>
      )}
    </DetailSection>
  );
}

function SlashCommandLocationRow({
  entry,
  target,
  copy,
}: {
  entry: SlashSyncEntryDto;
  target: SlashTargetDto | undefined;
  copy: SlashCommandsCopy;
}) {
  const label = target?.label ?? entry.target;
  const formatPath = useFormatPath();
  return (
    <div className="detail-sheet__binding-row slash-written-location-row">
      <DetailBindingIdentity
        harness={entry.target}
        label={label}
        logoKey={logoKeyForHarness(entry.target)}
        statusLabel={copy.detail.written}
        tone="enabled"
        visibleStatus={copy.detail.written}
      />
      <p className="slash-written-location-row__path">{formatPath(entry.path)}</p>
    </div>
  );
}

function writtenLocationEntries(
  entries: SlashSyncEntryDto[],
  targets: SlashTargetDto[],
): SlashSyncEntryDto[] {
  const order = new Map(targets.map((target, index) => [target.id, index]));
  return [...entries]
    .filter((entry) => entry.status === "synced")
    .sort((left, right) => (order.get(left.target) ?? 99) - (order.get(right.target) ?? 99));
}

function logoKeyForHarness(id: string): string {
  return id === "claude" ? "claude" : id;
}
