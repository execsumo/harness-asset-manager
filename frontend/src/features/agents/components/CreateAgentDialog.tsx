import "../agents.css";
import { useEffect, useMemo, useRef, useState } from "react";
import * as Dialog from "@radix-ui/react-dialog";
import { Loader2, X } from "lucide-react";

import {
  useCreateAgentMutation,
  useAgentsInventoryQuery,
  useHermesOptionsQuery,
} from "../api/queries";
import { useSettingsQuery } from "../../settings/public";
import { useSkillsListQuery } from "../../skills/public";
import { useToast } from "../../../components/Toast";
import { ErrorBanner } from "../../../components/ErrorBanner";
import { DetailBindingIdentity } from "../../../components/detail/DetailBindingIdentity";
import {
  FrontmatterChoiceSelect,
  type FrontmatterChoiceOption,
} from "../../../components/detail/editing/FrontmatterChoiceSelect";
import {
  AgentSkillsFieldEditor,
  deriveSkillTagOptions,
  type AdoptedSkillOption,
  type SkillTagOption,
} from "./detail/AgentSkillsFieldEditor";
import {
  BACKGROUND_VALUES,
  COLOR_VALUES,
  EFFORT_VALUES,
  ISOLATION_VALUES,
  MAX_TURNS_DEFAULT,
  MEMORY_VALUES,
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
  const [role, setRole] = useState("");
  const [harness, setHarness] = useState("");
  const [color, setColor] = useState("");
  const [model, setModel] = useState("");
  const [hermesProvider, setHermesProvider] = useState("");
  const [hermesModel, setHermesModel] = useState("");
  const [effort, setEffort] = useState("");
  const [skills, setSkills] = useState<string[]>([]);
  const [disallowedTools, setDisallowedTools] = useState("");
  const [mcpServers, setMcpServers] = useState("");
  const [background, setBackground] = useState("");
  const [memory, setMemory] = useState("");
  const [maxTurns, setMaxTurns] = useState("");
  const [isolation, setIsolation] = useState("");
  const [prompt, setPrompt] = useState("");
  const [selectedHarnesses, setSelectedHarnesses] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const { toast } = useToast();
  const createMutation = useCreateAgentMutation();
  const settingsQuery = useSettingsQuery();
  const inventoryQuery = useAgentsInventoryQuery();
  const hermesOptionsQuery = useHermesOptionsQuery();
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
    setRole("");
    setHarness("");
    setColor("");
    setModel("");
    setHermesProvider("");
    setHermesModel("");
    setEffort("");
    setSkills([]);
    setDisallowedTools("");
    setMcpServers("");
    setBackground("");
    setMemory("");
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
  // Every known harness stays selectable, with the uninstalled ones marked -- the same
  // vocabulary, from the same inventory, that Agent Details offers. Agents are authored
  // on one machine for another, so filtering to what happens to be installed here would
  // make a cross-device target unpickable rather than merely unusual.
  const harnessOptions = useMemo<FrontmatterChoiceOption[]>(
    () =>
      columns.map((column) => ({
        value: column.harness,
        label: column.label,
        note: column.installed ? undefined : "not installed here",
      })),
    [columns],
  );
  const hermesProviders = hermesOptionsQuery.data?.providers ?? [];
  const selectedHermesProvider = hermesProviders.find((provider) => provider.id === hermesProvider);
  const hermesModels = Array.from(new Set([
    model,
    hermesModel,
    ...(selectedHermesProvider ? selectedHermesProvider.models : hermesProviders.flatMap((provider) => provider.models)),
  ].filter(Boolean)));

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

    if (role.trim()) {
      payload.role = role.trim();
    }
    if (harness.trim()) {
      payload.harness = harness.trim();
    }

    if (color) {
      payload.color = color;
    }
    if (model.trim()) {
      payload.model = model.trim();
    }
    if (hermesProvider.trim()) {
      payload.hermesProvider = hermesProvider.trim();
    }
    if (hermesModel.trim()) {
      payload.hermesModel = hermesModel.trim();
    }
    if (effort) {
      payload.effort = effort;
    }
    if (skills.length > 0) {
      payload.skills = skills;
    }
    if (maxTurns.trim()) {
      payload.maxTurns = maxTurns.trim();
    }
    if (isolation) {
      payload.isolation = isolation;
    }
    const disallowed = disallowedTools
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    if (disallowed.length > 0) {
      payload.disallowedTools = disallowed;
    }
    const mcpServerRefs = mcpServers
      .split(",")
      .map((server) => server.trim())
      .filter(Boolean);
    if (mcpServerRefs.length > 0) {
      payload.mcpServers = mcpServerRefs;
    }
    if (background) {
      payload.background = background;
    }
    if (memory) {
      payload.memory = memory;
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

              <section className="detail-sheet__section">
                <h3 className="detail-sheet__section-heading">Frontmatter</h3>
                <div className="dialog-fieldset">
                  <div className="dialog-form-fields agent-frontmatter-grid">
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
                      <span className="form-field__label">Role</span>
                      <input
                        type="text"
                        className="form-field__input"
                        placeholder="Describe this agent's role"
                        value={role}
                        onChange={(e) => setRole(e.target.value)}
                        disabled={isPending}
                      />
                    </label>

                    <label className="form-field">
                      <span className="form-field__label">Color</span>
                      <FrontmatterChoiceSelect
                        label="Color"
                        value={color}
                        options={COLOR_VALUES}
                        onChange={setColor}
                        disabled={isPending}
                        className="form-field__input"
                      />
                    </label>

                    <label className="form-field agent-frontmatter-grid__description">
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

                    <label className="form-field">
                      <span className="form-field__label">Harness</span>
                      <FrontmatterChoiceSelect
                        label="Harness"
                        value={harness}
                        options={harnessOptions}
                        onChange={setHarness}
                        disabled={isPending}
                        clearLabel={harnessOptions.length > 0 ? "(none)" : "(no harnesses discovered)"}
                        className="form-field__input"
                      />
                    </label>

                    <label className="form-field">
                      <span className="form-field__label">Model</span>
                      <input
                        type="text"
                        className="form-field__input"
                        placeholder="Model identifier"
                        value={model}
                        onChange={(e) => setModel(e.target.value)}
                        disabled={isPending}
                      />
                    </label>

                    <label className="form-field">
                      <span className="form-field__label">Effort</span>
                      <FrontmatterChoiceSelect
                        label="Effort"
                        value={effort}
                        options={EFFORT_VALUES}
                        onChange={setEffort}
                        disabled={isPending}
                        className="form-field__input"
                      />
                    </label>
                  </div>

                  {/* Capabilities, then Execution -- the same order, and the same
                      order within each, as the structured editor in Agent Details.
                      Fields this dialog does not offer (deny-tools, mode, spawning,
                      trust-project) are skipped, not reordered around. */}
                  <div className="dialog-form-fields agent-frontmatter-grid__additional">
                    <div className="form-field agent-frontmatter-grid__skills">
                      <span className="form-field__label">Skills</span>
                      <AgentSkillsFieldEditor
                        skills={skills}
                        knownSkills={adoptedSkills}
                        tagOptions={tagOptions}
                        onChange={setSkills}
                        disabled={isPending}
                      />
                    </div>

                    {/* The format and the key a field writes belong in a help line, not
                        crammed into its label -- the same split the structured editor in
                        Agent Details makes. Each input names itself with its own
                        `aria-label` so the help line does not widen the accessible name. */}
                    <label className="form-field">
                      <span className="form-field__label">MCP Servers</span>
                      <input
                        type="text"
                        className="form-field__input"
                        placeholder="Comma-separated server references"
                        value={mcpServers}
                        onChange={(e) => setMcpServers(e.target.value)}
                        disabled={isPending}
                        aria-label="MCP Servers"
                      />
                      <span className="form-field__hint">Comma-separated. Written as an mcpServers list.</span>
                    </label>

                    <label className="form-field">
                      <span className="form-field__label">Disallowed Tools</span>
                      <input
                        type="text"
                        className="form-field__input"
                        placeholder="e.g. Write, Edit, Agent(Explore)"
                        value={disallowedTools}
                        onChange={(e) => setDisallowedTools(e.target.value)}
                        disabled={isPending}
                        aria-label="Disallowed Tools"
                      />
                      <span className="form-field__hint">Comma-separated. Written as disallowedTools.</span>
                    </label>

                    <label className="form-field">
                      <span className="form-field__label">Background</span>
                      <FrontmatterChoiceSelect
                        label="Background"
                        value={background}
                        options={BACKGROUND_VALUES}
                        onChange={setBackground}
                        disabled={isPending}
                        className="form-field__input"
                      />
                    </label>

                    <label className="form-field">
                      <span className="form-field__label">Isolation</span>
                      <FrontmatterChoiceSelect
                        label="Isolation"
                        value={isolation}
                        options={ISOLATION_VALUES}
                        onChange={setIsolation}
                        disabled={isPending}
                        className="form-field__input"
                      />
                    </label>

                    <label className="form-field">
                      <span className="form-field__label">Memory</span>
                      <FrontmatterChoiceSelect
                        label="Memory"
                        value={memory}
                        options={MEMORY_VALUES}
                        onChange={setMemory}
                        disabled={isPending}
                        className="form-field__input"
                      />
                    </label>

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
                  </div>

                  <div className="dialog-form-fields dialog-form-fields--split">
                    <label className="form-field">
                      <span className="form-field__label">Hermes Provider</span>
                      <input
                        type="text"
                        className="form-field__input"
                        list="hermes-provider-options"
                        placeholder="Auto / choose a configured provider"
                        value={hermesProvider}
                        onChange={(e) => setHermesProvider(e.target.value)}
                        disabled={isPending}
                        aria-label="Hermes Provider"
                      />
                      <datalist id="hermes-provider-options">
                        {hermesProviders.map((provider) => (
                          <option key={provider.id} value={provider.id} />
                        ))}
                      </datalist>
                    </label>

                    <label className="form-field">
                      <span className="form-field__label">Hermes Model</span>
                      <input
                        type="text"
                        className="form-field__input"
                        list="hermes-model-options"
                        placeholder={model.trim() ? `Uses Model above (${model.trim()})` : "Uses Hermes default or enter a model id"}
                        value={hermesModel}
                        onChange={(e) => setHermesModel(e.target.value)}
                        disabled={isPending}
                        aria-label="Hermes Model"
                      />
                      <datalist id="hermes-model-options">
                        {hermesModels.map((modelId) => (
                          <option key={modelId} value={modelId} />
                        ))}
                      </datalist>
                    </label>
                  </div>
                  <p className="agent-dialog-harness-hint">
                    Hermes profile skills and agents are verified supported targets. Hermes uses the
                    shared Model field unless Hermes Model overrides it; provider choices come from
                    Hermes configuration and can still be entered manually. HAM-managed Bots are addressed as hermes -p
                    &lt;name&gt; and do not install PATH wrapper scripts. External CLI backends and
                    sharing this profile's skills with a Codex app-server subprocess are out of scope.
                  </p>
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
