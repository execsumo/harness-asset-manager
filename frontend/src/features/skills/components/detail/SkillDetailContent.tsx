import { useEffect, useId, useMemo, useState } from "react";

import { DetailHeader } from "../../../../components/detail/DetailHeader";
import { DetailNote } from "../../../../components/detail/DetailNote";
import { DetailSection } from "../../../../components/detail/DetailSection";
import { DetailSourceLinks, type DetailSourceLink } from "../../../../components/detail/DetailSourceLinks";
import { ErrorBanner } from "../../../../components/ErrorBanner";
import { LoadingSpinner } from "../../../../components/LoadingSpinner";
import { useToast } from "../../../../components/Toast";
import { ConfirmActionDialog } from "../../../../components/ConfirmActionDialog";
import { DocumentSection } from "../../../../components/detail/editing/DocumentSection";
import {
  FrontmatterEditor,
  parseFrontmatterFromYaml,
  serializeFrontmatterToYaml,
  type KnownFieldConfig,
  type OtherFrontmatterEntry,
} from "../../../../components/detail/editing/FrontmatterEditor";
import MarkdownDocument from "../../../../components/MarkdownDocument";
import { useFormatPath } from "../../../../lib/paths";
import { skillStatusConcept } from "../../../../lib/product-language";
import { useSkillsCopy, type SkillsCopy } from "../../i18n";
import { useUpdateSkillDocumentMutation } from "../../api/queries";
import type { StructuralSkillAction } from "../../model/pending";
import type { HarnessCell, SkillDetail, SkillSourceLinks } from "../../model/types";
import { SkillDetailHarnessMatrix } from "./SkillDetailHarnessMatrix";
import { SkillDetailRemoveAction } from "./SkillDetailRemoveAction";
import { SkillDetailUpdateControl } from "./SkillDetailUpdateControl";
import { SkillDetailShell } from "./SkillDetailShell";

interface SkillDetailContentProps {
  detail: SkillDetail;
  actionErrorMessage: string;
  queryErrorMessage: string;
  pendingToggleHarnesses: ReadonlySet<string>;
  pendingStructuralAction: StructuralSkillAction | null;
  onClose: () => void;
  onDismissActionError: () => void;
  onManage: () => void;
  onToggleHarness: (cell: HarnessCell) => void;
  onUpdate: () => void;
  onRequestRemove: () => void;
  onRequestDelete: () => void;
}

export function SkillDetailContent({
  detail,
  actionErrorMessage,
  queryErrorMessage,
  pendingToggleHarnesses,
  pendingStructuralAction,
  onClose,
  onDismissActionError,
  onManage,
  onToggleHarness,
  onUpdate,
  onRequestRemove,
  onRequestDelete,
}: SkillDetailContentProps) {
  const headingId = useId();
  const copy = useSkillsCopy();
  const formatPath = useFormatPath();
  const { toast } = useToast();
  const updateDocumentMutation = useUpdateSkillDocumentMutation();

  const showSkillManagerStoreNote =
    skillStatusConcept(detail.displayStatus) === "inUse" &&
    detail.locations.some((location) => location.kind === "shared");
  const hasPendingHarnessToggles = pendingToggleHarnesses.size > 0;
  const structuralLocked = pendingStructuralAction !== null;
  const controlsDisabled = structuralLocked || hasPendingHarnessToggles;

  const errorMessage = actionErrorMessage || queryErrorMessage;
  const dismissError = actionErrorMessage ? onDismissActionError : undefined;

  const showUpdateControl =
    detail.actions.updateStatus !== null &&
    detail.actions.updateStatus !== "local_changes_detected";
  const showFooter = computeShowFooter(detail);
  const showHarnessSection = detail.harnessCells.length > 0;

  // Document & Frontmatter editing state
  const initialOtherEntries = useMemo<OtherFrontmatterEntry[]>(() => {
    return (detail.metadata || [])
      .filter((m) => m.key !== "name" && m.key !== "description")
      .map((m, idx) => ({
        id: `entry-${idx}-${m.key}`,
        key: m.key,
        value: m.value,
      }));
  }, [detail.metadata]);

  const [documentMode, setDocumentMode] = useState<"preview" | "edit">("preview");
  const [frontmatterMode, setFrontmatterMode] = useState<"structured" | "raw">("structured");
  const [name, setName] = useState(detail.name);
  const [description, setDescription] = useState(detail.description);
  const [otherEntries, setOtherEntries] = useState<OtherFrontmatterEntry[]>(initialOtherEntries);
  const [rawYaml, setRawYaml] = useState("");
  const [bodyValue, setBodyValue] = useState(detail.documentMarkdown ?? "");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [isDiscardDialogOpen, setDiscardDialogOpen] = useState(false);

  // Sync with incoming detail when asset ref changes
  useEffect(() => {
    setName(detail.name);
    setDescription(detail.description);
    setOtherEntries(
      (detail.metadata || [])
        .filter((m) => m.key !== "name" && m.key !== "description")
        .map((m, idx) => ({
          id: `entry-${idx}-${m.key}`,
          key: m.key,
          value: m.value,
        })),
    );
    setBodyValue(detail.documentMarkdown ?? "");
    setSaveError(null);
  }, [detail.skillRef]);

  const knownFields: KnownFieldConfig[] = useMemo(
    () => [
      {
        key: "name",
        label: "Name",
        value: name,
        onChange: setName,
      },
      {
        key: "description",
        label: "Description",
        value: description,
        onChange: setDescription,
      },
    ],
    [name, description],
  );

  // Compute dirty status
  const isDirty = useMemo(() => {
    if (name !== detail.name) return true;
    if (description !== detail.description) return true;
    if (bodyValue !== (detail.documentMarkdown ?? "")) return true;

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
  }, [name, description, bodyValue, otherEntries, detail, initialOtherEntries]);

  const handleCancelEdit = () => {
    setName(detail.name);
    setDescription(detail.description);
    setOtherEntries(initialOtherEntries);
    setBodyValue(detail.documentMarkdown ?? "");
    setSaveError(null);
    setFrontmatterMode("structured");
  };

  const handleSaveDocument = async () => {
    setSaveError(null);

    let finalName = name;
    let finalDesc = description;
    let finalOther = otherEntries;

    if (frontmatterMode === "raw") {
      const parsed = parseFrontmatterFromYaml(rawYaml, ["name", "description"]);
      if (parsed.error) {
        setSaveError(parsed.error);
        return;
      }
      finalName = parsed.known.name ?? name;
      finalDesc = parsed.known.description ?? description;
      finalOther = parsed.other;
      setName(finalName);
      setDescription(finalDesc);
      setOtherEntries(finalOther);
    }

    const metadataPayload = [
      { key: "name", value: finalName },
      { key: "description", value: finalDesc },
      ...finalOther
        .filter((e) => e.key.trim().length > 0)
        .map((e) => ({ key: e.key.trim(), value: e.value })),
    ];

    try {
      await updateDocumentMutation.mutateAsync({
        skillRef: detail.skillRef,
        body: {
          body: bodyValue,
          metadata: metadataPayload,
        },
      });
      toast(copy.detail.savedSuccess);
      setFrontmatterMode("structured");
      setDocumentMode("preview");
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : "Failed to save skill document.");
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
      <SkillDetailShell
        chrome={(
          <div className="skill-detail__chrome">
            <DetailHeader
              title={<h2 id={headingId}>{detail.name}</h2>}
              meta={detail.sourceLinks ? (
                <div className="detail-sheet__meta">
                  <DetailSourceLinks
                    ariaLabel={copy.detail.sourceLinksAria(detail.sourceLinks.repoLabel)}
                    links={skillSourceLinks(detail.sourceLinks, copy)}
                  />
                </div>
              ) : undefined}
              closeLabel={copy.detail.close}
              onClose={handleRequestClose}
            />
            {errorMessage ? (
              <ErrorBanner message={errorMessage} onDismiss={dismissError} />
            ) : null}
            {saveError ? (
              <ErrorBanner message={saveError} onDismiss={() => setSaveError(null)} />
            ) : null}
          </div>
        )}
        body={(
          <>
            <DetailSection heading={copy.detail.about}>
              <p className="skill-detail__copy">
                {detail.description || copy.detail.noDescription}
              </p>
              {detail.attentionMessage ? (
                <DetailNote>{detail.attentionMessage}</DetailNote>
              ) : null}
            </DetailSection>

            <DocumentSection
              title={copy.detail.document}
              mode={documentMode}
              onModeChange={setDocumentMode}
              previewContent={
                detail.documentMarkdown ? (
                  <MarkdownDocument markdown={detail.documentMarkdown} />
                ) : (
                  <p className="skill-detail__copy">{copy.detail.noDocument}</p>
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
                  note={copy.detail.skillPackageNote}
                  validationError={null}
                  disabled={updateDocumentMutation.isPending}
                />
              )}
              bodyValue={bodyValue}
              onBodyChange={setBodyValue}
              bodyLabel="Body (SKILL.md)"
              bodyPlaceholder="Markdown body..."
              isDirty={isDirty}
              isSaving={updateDocumentMutation.isPending}
              onSave={handleSaveDocument}
              onCancel={handleCancelEdit}
              saveLabel={copy.detail.save}
              cancelLabel={copy.detail.cancel}
              unsavedLabel={copy.detail.unsavedChanges}
            />

            {showHarnessSection ? (
              <DetailSection heading={copy.detail.harnesses}>
                <SkillDetailHarnessMatrix
                  skillName={detail.name}
                  cells={detail.harnessCells}
                  pendingToggleHarnesses={pendingToggleHarnesses}
                  pendingStructuralAction={pendingStructuralAction}
                  onToggleCell={onToggleHarness}
                />
              </DetailSection>
            ) : null}

            {detail.locations.length > 0 ? (
              <DetailSection heading={copy.detail.locations}>
                {showSkillManagerStoreNote ? (
                  <p className="skill-detail__context-note">
                    {copy.detail.storeNote}
                  </p>
                ) : null}
                <div className="skill-detail__locations">
                  {detail.locations.map((location, index) => {
                    const descriptor = locationDescriptor(detail, location, copy);
                    return (
                      <article
                        key={`${location.kind}:${location.path ?? index}`}
                        className="skill-detail__location"
                      >
                        <div className="skill-detail__location-header">
                          <strong>{location.label}</strong>
                          {descriptor ? (
                            <span className="skill-detail__location-note">{descriptor}</span>
                          ) : null}
                        </div>
                        <p className="skill-detail__location-path">
                          {location.path
                            ? formatPath(location.path)
                            : location.detail ?? location.sourceLocator}
                        </p>
                      </article>
                    );
                  })}
                </div>
              </DetailSection>
            ) : null}
          </>
        )}
        footer={showFooter ? (
          <>
            {detail.actions.canManage ? (
              <button
                type="button"
                className="action-pill action-pill--md action-pill--accent"
                disabled={controlsDisabled}
                onClick={onManage}
              >
                {pendingStructuralAction === "manage" ? (
                  <LoadingSpinner size="sm" label={copy.detail.managingSkill} />
                ) : null}
                {copy.detail.addToSkillManager}
              </button>
            ) : null}
            {showUpdateControl ? (
              <SkillDetailUpdateControl
                updateStatus={detail.actions.updateStatus!}
                pending={pendingStructuralAction === "update"}
                disabled={controlsDisabled}
                onUpdate={onUpdate}
              />
            ) : null}
            {detail.actions.stopManagingStatus !== null ? (
              <SkillDetailRemoveAction
                status={detail.actions.stopManagingStatus}
                disabled={controlsDisabled}
                onRequestRemove={onRequestRemove}
              />
            ) : null}
            {detail.actions.canDelete ? (
              <button
                type="button"
                className="action-pill action-pill--md action-pill--danger"
                disabled={controlsDisabled}
                onClick={onRequestDelete}
              >
                {pendingStructuralAction === "delete" ? (
                  <LoadingSpinner size="sm" label={copy.confirm.deletingSkill} />
                ) : null}
                {copy.detail.deleteSkill}
              </button>
            ) : null}
          </>
        ) : undefined}
        bodyAriaLabelledBy={headingId}
      />

      <ConfirmActionDialog
        open={isDiscardDialogOpen}
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

function skillSourceLinks(sourceLinks: SkillSourceLinks, copy: SkillsCopy): DetailSourceLink[] {
  const links: DetailSourceLink[] = [
    {
      href: sourceLinks.repoUrl,
      label: sourceLinks.repoLabel,
      kind: "repo",
    },
  ];
  if (sourceLinks.folderUrl) {
    links.push({
      href: sourceLinks.folderUrl,
      label: copy.detail.openSkillFolder,
      kind: "folder",
    });
  }
  return links;
}

function computeShowFooter(detail: SkillDetail): boolean {
  return (
    detail.actions.canManage ||
    (detail.actions.updateStatus !== null && detail.actions.updateStatus !== "local_changes_detected") ||
    detail.actions.stopManagingStatus !== null ||
    detail.actions.canDelete
  );
}

function locationDescriptor(
  detail: SkillDetail,
  location: SkillDetail["locations"][number],
  copy: SkillsCopy,
): string | null {
  if (skillStatusConcept(detail.displayStatus) !== "inUse") {
    return null;
  }
  if (location.kind === "shared") {
    return copy.detail.canonicalPhysicalPackage;
  }
  if (location.kind === "harness") {
    return copy.detail.symlinkToStore;
  }
  return null;
}
