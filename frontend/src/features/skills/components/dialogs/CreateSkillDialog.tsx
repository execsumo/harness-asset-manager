import { useEffect, useMemo, useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Loader2, X } from "lucide-react";

import { ErrorBanner } from "../../../../components/ErrorBanner";
import { DetailBindingIdentity } from "../../../../components/detail/DetailBindingIdentity";
import {
  FrontmatterEditor,
  parseFrontmatterFromYaml,
  type KnownFieldConfig,
  type OtherFrontmatterEntry,
} from "../../../../components/detail/editing/FrontmatterEditor";
import { useToast } from "../../../../components/Toast";
import { useSettingsQuery } from "../../../settings/public";
import { useCreateSkillMutation, useSkillsListQuery } from "../../api/queries";
import { useSkillsCopy } from "../../i18n";

/** The specification's ceiling on `description`, mirrored from conformance.py. */
const DESCRIPTION_MAX_LENGTH = 1024;

/**
 * Mirrors `slugify_skill_name` in application/skills/conformance.py, so a name the
 * server would refuse is caught before the request rather than after a round trip.
 */
export function slugifySkillName(name: string): string {
  const collapsed = name.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return collapsed.replace(/^-+|-+$/g, "").slice(0, 64).replace(/-+$/g, "");
}

interface CreateSkillDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CreateSkillDialog({ open, onOpenChange }: CreateSkillDialogProps) {
  const copy = useSkillsCopy();
  const { toast } = useToast();
  const createMutation = useCreateSkillMutation();
  const skillsQuery = useSkillsListQuery();
  const settingsQuery = useSettingsQuery();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [otherEntries, setOtherEntries] = useState<OtherFrontmatterEntry[]>([]);
  const [rawYaml, setRawYaml] = useState("");
  const [frontmatterMode, setFrontmatterMode] = useState<"structured" | "raw">("structured");
  const [body, setBody] = useState("");
  const [selectedHarnesses, setSelectedHarnesses] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  // Settings can still be in flight when the dialog opens, so the harness preselection
  // is seeded separately from the rest of the form — once per opening, so that a later
  // settings refetch never overwrites a choice the user has made in the meantime.
  const harnessesSeeded = useRef(false);

  useEffect(() => {
    if (!open) {
      harnessesSeeded.current = false;
      return;
    }
    setName("");
    setDescription("");
    setOtherEntries([]);
    setRawYaml("");
    setFrontmatterMode("structured");
    setBody("");
    setError(null);
  }, [open]);

  useEffect(() => {
    if (!open || harnessesSeeded.current || !settingsQuery.data) return;
    setSelectedHarnesses(settingsQuery.data.autoAdoptHarnesses?.skills ?? []);
    harnessesSeeded.current = true;
  }, [open, settingsQuery.data]);

  const columns = skillsQuery.data?.harnessColumns ?? [];

  const existingPackageDirs = useMemo(() => {
    const dirs = new Set<string>();
    for (const row of skillsQuery.data?.rows ?? []) {
      if (row.skillRef.startsWith("shared:")) {
        dirs.add(row.skillRef.slice("shared:".length));
      }
    }
    return dirs;
  }, [skillsQuery.data?.rows]);

  const trimmedName = name.trim();
  const slug = slugifySkillName(trimmedName);
  const trimmedDescription = description.trim();

  const nameError = !trimmedName
    ? ""
    : !slug
      ? "Cannot derive a valid package name from this skill name."
      : existingPackageDirs.has(slug)
        ? `A skill named "${slug}" already exists.`
        : "";
  const descriptionError =
    trimmedDescription.length > DESCRIPTION_MAX_LENGTH
      ? `Description is ${trimmedDescription.length} characters; the specification allows ${DESCRIPTION_MAX_LENGTH}.`
      : "";

  const isPending = createMutation.isPending;
  // Raw YAML holds the authoritative name and description while that mode is open, so
  // the structured values behind it cannot decide whether the form is submittable.
  const canSubmit =
    frontmatterMode === "raw" ||
    Boolean(trimmedName && !nameError && trimmedDescription && !descriptionError);

  const knownFields: KnownFieldConfig[] = useMemo(
    () => [
      {
        key: "name",
        label: "Name",
        value: name,
        onChange: setName,
        disabled: isPending,
        placeholder: "e.g. Release Notes Writer",
        helpText: slug
          ? `Written as ${slug}/SKILL.md, with name: ${slug}.`
          : "Lowercase letters, numbers and single hyphens. The package directory and name: are written from it.",
      },
      {
        key: "description",
        label: "Description",
        value: description,
        onChange: setDescription,
        disabled: isPending,
        placeholder: "When should an agent reach for this skill?",
        helpText: "Agents read this to decide when the skill applies.",
      },
    ],
    [name, description, slug, isPending],
  );

  function toggleHarness(harnessId: string) {
    setSelectedHarnesses((current) =>
      current.includes(harnessId)
        ? current.filter((id) => id !== harnessId)
        : [...current, harnessId],
    );
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!canSubmit || isPending) return;
    setError(null);

    let finalName = name;
    let finalDescription = description;
    let finalOther = otherEntries;

    if (frontmatterMode === "raw") {
      const parsed = parseFrontmatterFromYaml(rawYaml, ["name", "description"]);
      if (parsed.error) {
        setError(parsed.error);
        return;
      }
      finalName = parsed.known.name ?? name;
      finalDescription = parsed.known.description ?? description;
      finalOther = parsed.other;
      setName(finalName);
      setDescription(finalDescription);
      setOtherEntries(finalOther);
    }

    if (!slugifySkillName(finalName)) {
      setError("Cannot derive a valid package name from this skill name.");
      return;
    }
    if (!finalDescription.trim()) {
      setError("A description is required — agents use it to decide when the skill applies.");
      return;
    }

    try {
      const created = await createMutation.mutateAsync({
        name: finalName.trim(),
        description: finalDescription.trim(),
        body,
        metadata: finalOther
          .filter((entry) => entry.key.trim().length > 0)
          .map((entry) => ({ key: entry.key.trim(), value: entry.value })),
        harnesses: selectedHarnesses,
      });
      const failures = created.harnessFailures ?? [];
      toast(
        failures.length > 0
          ? copy.create.createdWithFailures(created.name, failures.map((failure) => failure.harness))
          : copy.create.created(created.name),
      );
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : copy.create.failed);
    }
  }

  return (
    <Dialog.Root
      open={open}
      onOpenChange={(nextOpen) => {
        if (!isPending) onOpenChange(nextOpen);
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="dialog-overlay" />
        <Dialog.Content className="dialog-content create-dialog">
          <div className="dialog-header dialog-header--split">
            <div>
              <Dialog.Title className="dialog-title">{copy.create.title}</Dialog.Title>
              <Dialog.Description className="dialog-subtitle">
                {slug ? (
                  <>
                    Written as <code>{slug}/SKILL.md</code> in the shared store, then linked into
                    every harness enabled below.
                  </>
                ) : (
                  <>{copy.create.subtitle}</>
                )}
              </Dialog.Description>
            </div>
            <Dialog.Close className="dialog-close-btn" aria-label={copy.create.close} disabled={isPending}>
              <X size={16} aria-hidden="true" />
            </Dialog.Close>
          </div>

          <form onSubmit={handleSubmit} className="dialog-form create-dialog__form">
            <div className="dialog-form-body create-dialog__body ui-scrollbar">
              {error ? <ErrorBanner message={error} onDismiss={() => setError(null)} /> : null}

              {/* The same editor Skill Details uses, so the fields a skill is created
                  with and the fields it is edited with are one surface — including the
                  raw-YAML escape hatch for frontmatter this form does not name. */}
              <FrontmatterEditor
                knownFields={knownFields}
                otherEntries={otherEntries}
                onChangeOtherEntries={setOtherEntries}
                rawYaml={rawYaml}
                onChangeRawYaml={setRawYaml}
                mode={frontmatterMode}
                onModeChange={setFrontmatterMode}
                validationError={nameError || descriptionError || null}
                disabled={isPending}
              />

              <section className="detail-sheet__section">
                <h3 className="detail-sheet__section-heading">{copy.create.documentHeading}</h3>
                <label className="form-field">
                  <span className="form-field__label">{copy.create.bodyLabel}</span>
                  <textarea
                    className="form-field__textarea form-field__textarea--mono"
                    placeholder={copy.create.bodyPlaceholder}
                    value={body}
                    onChange={(event) => setBody(event.target.value)}
                    disabled={isPending}
                    rows={8}
                    spellCheck={false}
                    aria-label={copy.create.bodyLabel}
                  />
                  <span className="form-field__hint">{copy.create.bodyHint}</span>
                </label>
              </section>

              <fieldset className="asset-target-picker">
                <legend className="detail-sheet__section-heading">{copy.detail.harnesses}</legend>
                <div className="detail-sheet__bindings">
                  {columns.map((column) => {
                    const checked = selectedHarnesses.includes(column.harness);
                    const disabled = isPending || !column.installed;
                    return (
                      <div
                        key={column.harness}
                        className="detail-sheet__binding-row"
                        data-state={checked ? "enabled" : "disabled"}
                      >
                        <DetailBindingIdentity
                          harness={column.harness}
                          label={column.label}
                          logoKey={column.logoKey}
                          statusLabel={
                            !column.installed ? "Not installed" : checked ? "Enabled" : "Disabled"
                          }
                          tone={!column.installed ? "warning" : checked ? "enabled" : "disabled"}
                        />
                        <div className="detail-sheet__binding-actions">
                          <button
                            type="button"
                            className={`action-pill ${checked ? "action-pill--danger" : "action-pill--accent"}`}
                            disabled={disabled}
                            onClick={() => toggleHarness(column.harness)}
                            aria-pressed={checked}
                            aria-label={
                              !column.installed
                                ? `${column.label} is not installed`
                                : checked
                                  ? `Disable ${column.label} for ${slug || "skill"}`
                                  : `Enable ${column.label} for ${slug || "skill"}`
                            }
                          >
                            {checked ? "Disable" : "Enable"}
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
                {selectedHarnesses.length === 0 ? (
                  <p className="create-dialog__hint" role="status">
                    {copy.create.noHarnessHint}
                  </p>
                ) : null}
              </fieldset>
            </div>

            <div className="dialog-footer create-dialog__footer">
              <Dialog.Close asChild>
                <button type="button" className="action-pill action-pill--md" disabled={isPending}>
                  {copy.detail.cancel}
                </button>
              </Dialog.Close>
              <button
                type="submit"
                className="action-pill action-pill--md action-pill--accent"
                disabled={!canSubmit || isPending}
              >
                {isPending ? <Loader2 className="animate-spin" size={16} /> : null}
                {copy.create.submit}
              </button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
