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
  type AdoptedSkillOption,
} from "./detail/AgentSkillsFieldEditor";
import {
  ALLOWED_SUBAGENTS_VALUES,
  COLOR_VALUES,
  EFFORT_VALUES,
  ISOLATION_VALUES,
  MAX_TURNS_DEFAULT,
  type AgentCreateRequest,
} from "../api/types";

export function slugify(name: string): string {
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

  const prevOpenRef = useRef(false);
  const initializedHarnessesRef = useRef(false);

  useEffect(() => {
    if (open && !prevOpenRef.current) {
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
      initializedHarnessesRef.current = false;
    }
    prevOpenRef.current = open;
  }, [open]);

  useEffect(() => {
    if (!open) {
      initializedHarnessesRef.current = false;
      return;
    }
    if (!initializedHarnessesRef.current && settingsQuery.data !== undefined) {
      const autoAdopt = settingsQuery.data?.autoAdoptHarnesses?.agents;
      setSelectedHarnesses(autoAdopt && autoAdopt.length > 0 ? autoAdopt : []);
      initializedHarnessesRef.current = true;
    }
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
      }));
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
      const result = await createMutation.mutateAsync(payload);
      if (result?.harnessFailures && result.harnessFailures.length > 0) {
        const failed = result.harnessFailures.map((f) => f.harness).join(", ");
        toast(`Created agent ${result.name || trimmedName}, but failed to bind to: ${failed}`);
      } else {
        toast(`Successfully created agent ${result?.name || trimmedName}`);
      }
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
          <div className="dialog-header">
            <Dialog.Title className="dialog-title">
              Create New Agent Persona
            </Dialog.Title>
            <Dialog.Close className="dialog-close-btn" disabled={isPending}>
              <X size={18} />
            </Dialog.Close>
          </div>

          <form onSubmit={handleSubmit} className="dialog-form agent-dialog-form">
            <div className="dialog-form-fields agent-dialog-form-fields">
              {error && (
                <ErrorBanner message={error} onDismiss={() => setError(null)} />
              )}

              {/* 1. Name */}
              <label className="form-field">
                <span className="form-field__label">Agent Name *</span>
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

              {/* 2. Description */}
              <label className="form-field">
                <span className="form-field__label">Description *</span>
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

              {/* 3. Color */}
              <label className="form-field">
                <span className="form-field__label">Color</span>
                <select
                  className="form-field__input"
                  value={color}
                  onChange={(e) => setColor(e.target.value)}
                  disabled={isPending}
                  aria-label="Color"
                >
                  <option value="">(none)</option>
                  {COLOR_VALUES.map((val) => (
                    <option key={val} value={val}>
                      {val}
                    </option>
                  ))}
                </select>
              </label>

              {/* 4. Model */}
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

              {/* 5. Effort */}
              <label className="form-field">
                <span className="form-field__label">Effort</span>
                <select
                  className="form-field__input"
                  value={effort}
                  onChange={(e) => setEffort(e.target.value)}
                  disabled={isPending}
                  aria-label="Effort"
                >
                  <option value="">(none)</option>
                  {EFFORT_VALUES.map((val) => (
                    <option key={val} value={val}>
                      {val}
                    </option>
                  ))}
                </select>
              </label>

              {/* 6. Tools */}
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

              {/* 7. Skills */}
              <div className="form-field">
                <span className="form-field__label">Skills</span>
                <AgentSkillsFieldEditor
                  skills={skills}
                  knownSkills={adoptedSkills}
                  onChange={setSkills}
                  disabled={isPending}
                />
              </div>

              {/* 8. Allowed Subagents */}
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

              {/* 9. Max Turns */}
              <label className="form-field">
                <span className="form-field__label">Max Turns</span>
                <input
                  type="text"
                  className="form-field__input"
                  placeholder={`${MAX_TURNS_DEFAULT} — the default when the key is absent`}
                  value={maxTurns}
                  onChange={(e) => setMaxTurns(e.target.value)}
                  disabled={isPending}
                />
              </label>

              {/* 10. Isolation */}
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

              {/* Prompt */}
              <label className="form-field">
                <span className="form-field__label">Prompt *</span>
                <textarea
                  className="form-field__textarea"
                  placeholder="System instructions..."
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  disabled={isPending}
                  rows={4}
                  required
                />
              </label>

              {/* Harness Picker */}
              <fieldset className="agent-target-picker">
                <legend className="form-field__label">Harnesses</legend>
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
