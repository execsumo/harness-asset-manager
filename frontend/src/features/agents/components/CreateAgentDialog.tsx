import "../agents.css";
import { useEffect, useMemo, useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Loader2, X } from "lucide-react";

import { useCreateAgentMutation, useAgentsInventoryQuery } from "../api/queries";
import { useSettingsQuery } from "../../settings/public";
import { useSkillsListQuery } from "../../skills/public";
import { useToast } from "../../../components/Toast";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { DetailBindingIdentity } from "../../../components/detail/DetailBindingIdentity";
import { FrontmatterSegmentedField } from "../../../components/detail/editing/FrontmatterSegmentedField";
import {
  AgentSkillsFieldEditor,
  deriveSkillTagOptions,
  type AdoptedSkillOption,
  type SkillTagOption,
} from "./detail/AgentSkillsFieldEditor";
import {
  ALLOWED_SUBAGENTS_VALUES,
  COLOR_VALUES,
  EFFORT_VALUES,
  ISOLATION_VALUES,
  MAX_TURNS_DEFAULT,
  type AgentCreateRequest,
} from "../api/types";

/**
 * Mirrors `slugify` in application/agents/store.py, so a name the server would
 * reject is caught before the request rather than after a round trip.
 */
function slugify(name: string): string {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9._-]+/g, "-")
    .replace(/^[-.]+|[-.]+$/g, "");
}

interface CreateAgentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CreateAgentDialog({
  open,
  onOpenChange,
}: CreateAgentDialogProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [color, setColor] = useState("");
  const [model, setModel] = useState("");
  const [effort, setEffort] = useState("");
  const [toolsStr, setToolsStr] = useState("");
  const [skills, setSkills] = useState<string[]>([]);
  const [allowedSubagents, setAllowedSubagents] = useState("");
  const [maxTurns, setMaxTurns] = useState("");
  const [isolation, setIsolation] = useState("");
  const [prompt, setPrompt] = useState("");
  const [selectedHarnesses, setSelectedHarnesses] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const { toast } = useToast();
  const createMutation = useCreateAgentMutation();
  const settingsQuery = useSettingsQuery();
  const inventoryQuery = useAgentsInventoryQuery();
  const skillsListQuery = useSkillsListQuery();

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
    setColor("");
    setModel("");
    setEffort("");
    setToolsStr("");
    setSkills([]);
    setAllowedSubagents("");
    setMaxTurns("");
    setIsolation("");
    setPrompt("");
    setError(null);
  }, [open]);

  useEffect(() => {
    if (!open || harnessesSeeded.current || !settingsQuery.data) return;
    setSelectedHarnesses(settingsQuery.data.autoAdoptHarnesses?.agents ?? []);
    harnessesSeeded.current = true;
  }, [open, settingsQuery.data]);

  const existingSlugs = useMemo(() => {
    const set = new Set<string>();
    for (const entry of inventoryQuery.data?.entries ?? []) {
      if (entry.kind === "managed") {
        set.add(entry.ref);
      }
    }
    return set;
  }, [inventoryQuery.data?.entries]);

  const adoptedSkills = useMemo<AdoptedSkillOption[]>(() => {
    if (!skillsListQuery.data?.rows) return [];
    return skillsListQuery.data.rows
      .filter((row) => row.skillRef.startsWith("shared:") || row.displayStatus === "Managed")
      .map((row) => ({
        slug: row.skillRef.replace(/^shared:/, ""),
        name: row.name,
        tags: row.tags ?? [],
      }));
  }, [skillsListQuery.data?.rows]);

  const tagOptions = useMemo<SkillTagOption[]>(() => {
    if (!skillsListQuery.data?.rows) return [];
    return deriveSkillTagOptions(skillsListQuery.data.rows);
  }, [skillsListQuery.data?.rows]);

  const trimmedName = name.trim();
  const derivedSlug = trimmedName ? slugify(trimmedName) : "";
  const nameError = !trimmedName
    ? ""
    : !derivedSlug
      ? "Cannot derive a valid file name from this agent name."
      : existingSlugs.has(derivedSlug)
        ? `An agent named "${derivedSlug}" already exists.`
        : "";

  const canSubmit = Boolean(
    trimmedName &&
    !nameError &&
    description.trim() &&
    prompt.trim()
  );
  const isPending = createMutation.isPending;

  const columns = inventoryQuery.data?.columns ?? [];

  function toggleHarness(harnessId: string) {
    setSelectedHarnesses((current) =>
      current.includes(harnessId)
        ? current.filter((id) => id !== harnessId)
        : [...current, harnessId],
    );
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setError(null);

    const payload: AgentCreateRequest = {
      name: trimmedName,
      description: description.trim(),
      prompt: prompt.trim(),
    };

    if (color) {
      payload.color = color;
    }
    if (model.trim()) {
      payload.model = model.trim();
    }
    if (effort) {
      payload.effort = effort;
    }
    const tools = toolsStr
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    if (tools.length > 0) {
      payload.tools = tools;
    }
    if (skills.length > 0) {
      payload.skills = skills;
    }
    if (allowedSubagents) {
      payload.allowedSubagents = allowedSubagents;
    }
    if (maxTurns.trim()) {
      payload.maxTurns = maxTurns.trim();
    }
    if (isolation) {
      payload.isolation = isolation;
    }
    if (selectedHarnesses.length > 0) {
      payload.harnesses = selectedHarnesses;
    }

    try {
      const created = await createMutation.mutateAsync(payload);
      const failures = created.harnessFailures ?? [];
      toast(
        failures.length > 0
          ? `Created agent ${created.name}, but failed to bind to: ${failures.map((failure) => failure.harness).join(", ")}`
          : `Successfully created agent ${created.name}`,
      );
      onOpenChange(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred while creating the agent.");
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
        <Dialog.Content className="dialog-content agent-dialog-content">
          <div className="dialog-header dialog-header--split">
            <div>
              <Dialog.Title className="dialog-title">Create Agent</Dialog.Title>
              <Dialog.Description className="dialog-subtitle">
                {derivedSlug ? (
                  <>
                    Written as <code>{derivedSlug}.md</code> to every harness enabled below.
                  </>
                ) : (
                  <>Fill in the agent contract, then pick the harnesses it is written to.</>
                )}
              </Dialog.Description>
            </div>
            <Dialog.Close className="dialog-close-btn" aria-label="Close" disabled={isPending}>
              <X size={16} aria-hidden="true" />
            </Dialog.Close>
          </div>

          <form onSubmit={handleSubmit} className="dialog-form agent-dialog-form">
            <div className="dialog-form-body agent-dialog-body ui-scrollbar">
              {error && (
                <ErrorBanner message={error} onDismiss={() => setError(null)} />
              )}

              {/* Sections mirror the detail view: identity, then the frontmatter
                  contract in AGENT_CONTRACT_KEYS order, then the document body,
                  then harness bindings — so the dialog and the detail view
                  present the same agent the same way round. */}
              <section className="detail-sheet__section">
                <h3 className="detail-sheet__section-heading">Identity</h3>
                <div className="dialog-form-fields">
                  <label className="form-field">
                    <span className="form-field__label">
                      Agent Name
                      <span className="form-field__required">Required</span>
                    </span>
                    <input
                      type="text"
                      className="form-field__input"
                      placeholder="e.g. Code Reviewer"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      disabled={isPending}
                      required
                      aria-invalid={Boolean(nameError)}
                      aria-describedby={nameError ? "agent-name-error" : undefined}
                    />
                    {nameError ? (
                      <small id="agent-name-error" className="form-field__error" role="alert">
                        {nameError}
                      </small>
                    ) : null}
                  </label>

                  <label className="form-field">
                    <span className="form-field__label">
                      Description
                      <span className="form-field__required">Required</span>
                    </span>
                    <textarea
                      className="form-field__textarea"
                      placeholder="Describe the agent's purpose and functionality..."
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      disabled={isPending}
                      rows={2}
                      required
                    />
                  </label>
                </div>
              </section>

              <section className="detail-sheet__section">
                <h3 className="detail-sheet__section-heading">Frontmatter</h3>
                <div className="dialog-fieldset">
                  <div className="dialog-form-fields dialog-form-fields--split">
                    <label className="form-field">
                      <span className="form-field__label">Color</span>
                      <select
                        className="form-field__input"
                        value={color}
                        onChange={(e) => setColor(e.target.value)}
                        disabled={isPending}
                      >
                        <option value="">(none)</option>
                        {COLOR_VALUES.map((val) => (
                          <option key={val} value={val}>
                            {val}
                          </option>
                        ))}
                      </select>
                    </label>

                    <label className="form-field">
                      <span className="form-field__label">Model</span>
                      <input
                        type="text"
                        className="form-field__input"
                        placeholder="e.g. sonnet, opus"
                        value={model}
                        onChange={(e) => setModel(e.target.value)}
                        disabled={isPending}
                      />
                    </label>

                    <label className="form-field">
                      <span className="form-field__label">Effort</span>
                      <select
                        className="form-field__input"
                        value={effort}
                        onChange={(e) => setEffort(e.target.value)}
                        disabled={isPending}
                      >
                        <option value="">(none)</option>
                        {EFFORT_VALUES.map((val) => (
                          <option key={val} value={val}>
                            {val}
                          </option>
                        ))}
                      </select>
                    </label>

                    <label className="form-field">
                      <span className="form-field__label">Max Turns</span>
                      <input
                        type="text"
                        className="form-field__input"
                        placeholder={`${MAX_TURNS_DEFAULT} (default)`}
                        value={maxTurns}
                        onChange={(e) => setMaxTurns(e.target.value)}
                        disabled={isPending}
                      />
                    </label>
                  </div>

                  <div className="dialog-form-fields">
                    <label className="form-field">
                      <span className="form-field__label">Tools (comma-separated)</span>
                      <input
                        type="text"
                        className="form-field__input"
                        placeholder="e.g. bash, edit, grep"
                        value={toolsStr}
                        onChange={(e) => setToolsStr(e.target.value)}
                        disabled={isPending}
                      />
                    </label>

                    <div className="form-field">
                      <span className="form-field__label">Skills</span>
                      <AgentSkillsFieldEditor
                        skills={skills}
                        knownSkills={adoptedSkills}
                        tagOptions={tagOptions}
                        onChange={setSkills}
                        disabled={isPending}
                      />
                    </div>

                    <div className="form-field">
                      <span className="form-field__label">Allowed Subagents</span>
                      <FrontmatterSegmentedField
                        label="Allowed Subagents"
                        value={allowedSubagents}
                        options={ALLOWED_SUBAGENTS_VALUES}
                        onChange={setAllowedSubagents}
                        disabled={isPending}
                      />
                    </div>

                    <div className="form-field">
                      <span className="form-field__label">Isolation</span>
                      <FrontmatterSegmentedField
                        label="Isolation"
                        value={isolation}
                        options={ISOLATION_VALUES}
                        onChange={setIsolation}
                        disabled={isPending}
                      />
                    </div>
                  </div>
                </div>
              </section>

              <section className="detail-sheet__section">
                <h3 className="detail-sheet__section-heading">System Prompt</h3>
                <label className="form-field">
                  <span className="form-field__label">
                    Prompt
                    <span className="form-field__required">Required</span>
                  </span>
                  <textarea
                    className="form-field__textarea form-field__textarea--mono"
                    placeholder="System instructions..."
                    value={prompt}
                    onChange={(e) => setPrompt(e.target.value)}
                    disabled={isPending}
                    rows={8}
                    required
                  />
                </label>
              </section>

              <fieldset className="agent-target-picker">
                <legend className="detail-sheet__section-heading">Harnesses</legend>
                <div className="detail-sheet__bindings">
                  {columns.map((col) => {
                    const checked = selectedHarnesses.includes(col.harness);
                    const disabled = isPending || !col.installed;
                    return (
                      <div
                        key={col.harness}
                        className="detail-sheet__binding-row agent-target-binding-row"
                        data-state={checked ? "enabled" : "disabled"}
                      >
                        <DetailBindingIdentity
                          harness={col.harness}
                          label={col.label}
                          logoKey={col.logoKey}
                          statusLabel={!col.installed ? "Not installed" : checked ? "Enabled" : "Disabled"}
                          tone={!col.installed ? "warning" : checked ? "enabled" : "disabled"}
                        />
                        <div className="detail-sheet__binding-actions">
                          <button
                            type="button"
                            className={`action-pill ${checked ? "action-pill--danger" : "action-pill--accent"}`}
                            disabled={disabled}
                            onClick={() => toggleHarness(col.harness)}
                            aria-pressed={checked}
                            aria-label={
                              !col.installed
                                ? `${col.label} is not installed`
                                : checked
                                  ? `Disable ${col.label} for ${trimmedName || "agent"}`
                                  : `Enable ${col.label} for ${trimmedName || "agent"}`
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
                  <p className="agent-dialog-harness-hint" role="status">
                    This agent won't be available in any harness yet. Pick one above, or set defaults in Settings → Auto-adopt.
                  </p>
                ) : null}
              </fieldset>
            </div>

            <div className="dialog-footer agent-dialog-footer">
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
                {isPending ? <Loader2 className="animate-spin" size={16} /> : null}
                Create Agent
              </button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
