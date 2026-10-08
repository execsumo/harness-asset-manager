import "../../agents.css";
import { lazy, Suspense, useEffect, useId, useMemo, useState } from "react";
import { Loader2, Star } from "lucide-react";
import { DetailHeader } from "../../../../components/detail/DetailHeader";
import { DetailSection } from "../../../../components/detail/DetailSection";
import { DetailTags } from "../../../../components/detail/DetailTags";
import { ErrorBanner } from "../../../../components/ErrorBanner";
import { LoadingSpinner } from "../../../../components/LoadingSpinner";
import { ConfirmActionDialog } from "../../../../components/ConfirmActionDialog";
import { DetailActionFooter } from "../../../../components/detail/DetailActionFooter";
import { DocumentSection } from "../../../../components/detail/editing/DocumentSection";
import {
  FrontmatterEditor,
  parseFrontmatterFromYaml,
  type FrontmatterFieldGroup,
  type KnownFieldConfig,
  type OtherFrontmatterEntry,
} from "../../../../components/detail/editing/FrontmatterEditor";
import { useToast } from "../../../../components/Toast";
import { DetailBindingIdentity, type DetailBindingTone } from "../../../../components/detail/DetailBindingIdentity";
import { UiTooltip } from "../../../../components/ui/UiTooltip";
import { UiTooltipTriggerBoundary } from "../../../../components/ui/UiTooltipTriggerBoundary";
import {
  FrontmatterChoiceSelect,
  type FrontmatterChoiceOption,
} from "../../../../components/detail/editing/FrontmatterChoiceSelect";
import {
  useAdoptAgentMutation,
  useDeleteAgentMutation,
  useHermesOptionsQuery,
  useSetAgentTagsMutation,
  useUnmanageAgentMutation,
  useUpdateAgentMutation,
} from "../../api/queries";
import { AdoptConflictDialog } from "../AdoptConflictDialog";
import { useSkillsListQuery } from "../../../skills/public";
import { useMcpInventoryQuery } from "../../../mcp/public";
import {
  AGENT_CONTRACT_KEYS,
  RETIRED_AGENT_KEYS,
  EFFORT_VALUES,
  MAX_TURNS_DEFAULT,
  MEMORY_VALUES,
} from "../../api/types";
import { stripFrontmatter } from "../../model/document";
import type { AgentAdoptConflict, AgentDetailDto } from "../../api/types";
import {
  AgentSkillsFieldEditor,
  deriveSkillTagOptions,
  type AdoptedSkillOption,
  type SkillTagOption,
} from "./AgentSkillsFieldEditor";

const MarkdownDocument = lazy(() => import("../../../../components/MarkdownDocument"));

/**
 * The four questions a reader of an agent file actually asks, in the order they ask
 * them: what is this, what runs it, what can it reach for, and how does it run. The
 * flat list this replaced interleaved all four -- a block list, a turn budget and an
 * MCP list shared one row -- so finding a field meant scanning all eighteen.
 *
 * The groups are a reading order, not a contract: the file is still written in
 * `AGENT_CONTRACT_KEYS` order by the backend renderer.
 */
const AGENT_FRONTMATTER_GROUPS: FrontmatterFieldGroup[] = [
  { id: "identity", title: "Identity", hint: "What this agent is called and how it presents." },
  // Not plain "Model": the group is announced by name, and a heading identical to a
  // field label inside it makes "Model" ambiguous to a screen reader and to a test.
  { id: "model", title: "Harness & Model", hint: "Which harness runs it, and with what model." },
  { id: "capabilities", title: "Capabilities", hint: "What it may reach for." },
  { id: "execution", title: "Execution", hint: "The envelope it runs in." },
];

function parseMcpServerRefs(value: string): string[] {
  return value
    .split(",")
    .map((server) => server.trim())
    .filter(Boolean);
}

function serializeMcpServerRefs(value: string): string | null {
  const servers = parseMcpServerRefs(value);
  return servers.length > 0
    ? `mcpServers:\n${servers.map((server) => `  - ${server}`).join("\n")}`
    : null;
}

export interface AgentDetailContentProps {
  detail: AgentDetailDto;
  knownTags?: string[];
  knownSkills?: AdoptedSkillOption[];
  tagOptions?: SkillTagOption[];
  pendingPerHarnessKeys: ReadonlySet<string>;
  onToggleHarness: (ref: string, harness: string, disable: boolean) => Promise<void>;
  actionErrorMessage: string | null;
  onClose: () => void;
  onDismissActionError: () => void;
}

export function AgentDetailContent({
  detail,
  knownTags,
  knownSkills,
  tagOptions: tagOptionsProp,
  pendingPerHarnessKeys,
  onToggleHarness,
  actionErrorMessage,
  onClose,
  onDismissActionError,
}: AgentDetailContentProps) {
  const headingId = useId();
  const { toast } = useToast();
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [discardDialogOpen, setDiscardDialogOpen] = useState(false);
  
  const deleteMutation = useDeleteAgentMutation();
  const updateMutation = useUpdateAgentMutation();
  const setTagsMutation = useSetAgentTagsMutation();
  const adoptMutation = useAdoptAgentMutation();
  const unmanageMutation = useUnmanageAgentMutation();
  const skillsListQuery = useSkillsListQuery();
  const mcpInventoryQuery = useMcpInventoryQuery();
  const hermesOptionsQuery = useHermesOptionsQuery();

  const [conflict, setConflict] = useState<AgentAdoptConflict | null>(null);
  const [conflictPending, setConflictPending] = useState(false);
  const [removeDialogOpen, setRemoveDialogOpen] = useState(false);

  const adoptedSkills = useMemo<AdoptedSkillOption[]>(() => {
    if (knownSkills && knownSkills.length > 0) {
      return knownSkills;
    }
    if (!skillsListQuery.data?.rows) return [];
    return skillsListQuery.data.rows
      .filter((row) => row.skillRef.startsWith("shared:") || row.displayStatus === "Managed")
      .map((row) => ({
        slug: row.skillRef.replace(/^shared:/, ""),
        name: row.name,
        tags: row.tags ?? [],
      }));
  }, [knownSkills, skillsListQuery.data?.rows]);

  const managedMcpServers = useMemo<AdoptedSkillOption[]>(
    () => (mcpInventoryQuery.data?.entries ?? [])
      .filter((entry) => entry.kind === "managed" && entry.spec !== null)
      .map((entry) => ({ slug: entry.name, name: entry.displayName })),
    [mcpInventoryQuery.data?.entries],
  );

  const effectiveTagOptions = useMemo<SkillTagOption[]>(() => {
    if (tagOptionsProp !== undefined) {
      return tagOptionsProp;
    }
    if (skillsListQuery.data?.rows && skillsListQuery.data.rows.length > 0) {
      return deriveSkillTagOptions(skillsListQuery.data.rows);
    }
    if (adoptedSkills.length > 0) {
      return deriveSkillTagOptions(adoptedSkills);
    }
    return [];
  }, [tagOptionsProp, skillsListQuery.data?.rows, adoptedSkills]);

  const [localActionError, setLocalActionError] = useState<string | null>(null);
  const errorMessage = actionErrorMessage || localActionError;
  const dismissError = () => {
    onDismissActionError();
    setLocalActionError(null);
  };

  const isStarred = (detail.tags || []).some((t) => t.toLowerCase() === "starred");

  const handleToggleStar = async () => {
    const nextTags = isStarred
      ? (detail.tags || []).filter((t) => t.toLowerCase() !== "starred")
      : ["starred", ...(detail.tags || []).filter((t) => t.toLowerCase() !== "starred")];
    try {
      await setTagsMutation.mutateAsync({
        ref: detail.ref,
        tags: nextTags,
      });
    } catch (err) {
      setLocalActionError(err instanceof Error ? err.message : "Failed to toggle star.");
    }
  };

  const handleAddTag = async (newTag: string) => {
    const nextTags = [...(detail.tags || []), newTag];
    await setTagsMutation.mutateAsync({
      ref: detail.ref,
      tags: nextTags,
    });
  };

  const handleRemoveTag = async (tagToRemove: string) => {
    const nextTags = (detail.tags || []).filter(
      (t) => t.toLowerCase() !== tagToRemove.toLowerCase(),
    );
    await setTagsMutation.mutateAsync({
      ref: detail.ref,
      tags: nextTags,
    });
  };

  // Frontmatter & Document editing state
  const initialOtherEntries = useMemo<OtherFrontmatterEntry[]>(() => {
    return (detail.configuration || [])
      .filter(
        (c) =>
          !(AGENT_CONTRACT_KEYS as readonly string[]).includes(c.key) &&
          !(RETIRED_AGENT_KEYS as readonly string[]).includes(c.key) &&
          c.key !== "mcpServers",
      )
      .map((c, idx) => ({
        id: `entry-${idx}-${c.key}`,
        key: c.key,
        value: c.value,
        ...(c.rawValue !== undefined && c.rawValue !== null
          ? { rawValue: c.rawValue }
          : {}),
      }));
  }, [detail.configuration]);

  const initialSkills = useMemo(() => (detail.skills || []).map((s) => s.slug), [detail.skills]);

  const [frontmatterMode, setFrontmatterMode] = useState<"structured" | "raw">("structured");
  const [name, setName] = useState(detail.name);
  const [description, setDescription] = useState(detail.description);
  const [roleStr, setRoleStr] = useState(detail.role ?? "");
  const [harnessStr, setHarnessStr] = useState(detail.harness ?? "");
  const [toolsStr, setToolsStr] = useState(detail.tools.join(", "));
  const [skills, setSkills] = useState<string[]>(initialSkills);
  const [modelStr, setModelStr] = useState(detail.model ?? "");
  const [hermesProviderStr, setHermesProviderStr] = useState(detail.hermesProvider ?? "");
  const [effortStr, setEffortStr] = useState(detail.effort ?? "");
  const [maxTurnsStr, setMaxTurnsStr] = useState(detail.maxTurns ?? "");
  const [memoryStr, setMemoryStr] = useState(detail.memory ?? "");
  const [disallowedToolsStr, setDisallowedToolsStr] = useState((detail.disallowedTools ?? []).join(", "));
  const [mcpServersStr, setMcpServersStr] = useState(
    (detail.mcpServers ?? []).map((binding) => binding.name).join(", "),
  );
  const [otherEntries, setOtherEntries] = useState<OtherFrontmatterEntry[]>(initialOtherEntries);
  const [rawYaml, setRawYaml] = useState("");
  const [prompt, setPrompt] = useState(detail.prompt);
  const [saveError, setSaveError] = useState<string | null>(null);
  const hermesProviders = hermesOptionsQuery.data?.providers ?? [];
  const hermesProviderOptions = hermesProviders.map((provider) => provider.id);

  useEffect(() => {
    setName(detail.name);
    setDescription(detail.description);
    setRoleStr(detail.role ?? "");
    setHarnessStr(detail.harness ?? "");
    setToolsStr(detail.tools.join(", "));
    setSkills((detail.skills || []).map((s) => s.slug));
    setModelStr(detail.model ?? "");
    setHermesProviderStr(detail.hermesProvider ?? "");
    setEffortStr(detail.effort ?? "");
    setMaxTurnsStr(detail.maxTurns ?? "");
    setMemoryStr(detail.memory ?? "");
    setDisallowedToolsStr((detail.disallowedTools ?? []).join(", "));
    setMcpServersStr((detail.mcpServers ?? []).map((binding) => binding.name).join(", "));
    setOtherEntries(
      (detail.configuration || [])
        .filter(
          (c) =>
            !(AGENT_CONTRACT_KEYS as readonly string[]).includes(c.key) &&
            !(RETIRED_AGENT_KEYS as readonly string[]).includes(c.key) &&
            c.key !== "mcpServers",
        )
        .map((c, idx) => ({
          id: `entry-${idx}-${c.key}`,
          key: c.key,
          value: c.value,
          ...(c.rawValue !== undefined && c.rawValue !== null
            ? { rawValue: c.rawValue }
            : {}),
        })),
    );
    setPrompt(detail.prompt);
    setSaveError(null);
  }, [detail.ref]);

  const parseSkillSlugs = (val: string): string[] => {
    return val
      .replace(/^[[\]]/g, "")
      .split(",")
      .map((s) => s.replace(/^[[\]\s'"]+|[[\]\s'"]+$/g, "").trim())
      .filter(Boolean);
  };

  // Every known harness stays selectable, with the uninstalled ones marked. Agents are
  // authored on one machine for another, so filtering to what happens to be installed
  // here would make a cross-device target unpickable rather than merely unusual.
  const harnessOptions = useMemo<FrontmatterChoiceOption[]>(
    () =>
      detail.harnesses.map((harness) => ({
        value: harness.harness,
        label: harness.label,
        note: harness.installed ? undefined : "not installed here",
      })),
    [detail.harnesses],
  );

  const knownFields: KnownFieldConfig[] = useMemo(
    () => [
      // Identity ------------------------------------------------------------
      {
        key: "name",
        label: "Agent Name",
        group: "identity",
        value: name,
        onChange: setName,
      },
      {
        key: "role",
        label: "Role",
        group: "identity",
        value: roleStr,
        onChange: setRoleStr,
        placeholder: "Describe this agent's role",
      },
      {
        key: "description",
        label: "Description",
        group: "identity",
        value: description,
        onChange: setDescription,
        placeholder: "Describe the agent's purpose and functionality",
      },
      // Model ---------------------------------------------------------------
      {
        key: "harness",
        label: "Harness",
        group: "model",
        value: harnessStr,
        onChange: setHarnessStr,
        renderInput: ({ disabled }) => (
          <FrontmatterChoiceSelect
            label="Harness"
            value={harnessStr}
            options={harnessOptions}
            onChange={setHarnessStr}
            disabled={disabled}
            clearLabel={harnessOptions.length > 0 ? "(none)" : "(no harnesses discovered)"}
          />
        ),
      },
      {
        key: "model",
        label: "Model",
        group: "model",
        value: modelStr,
        onChange: setModelStr,
        placeholder: "Model identifier — empty clears the key",
      },
      {
        key: "effort",
        label: "Effort",
        group: "model",
        value: effortStr,
        onChange: setEffortStr,
        renderInput: ({ disabled }) => (
          <FrontmatterChoiceSelect
            label="Effort"
            value={effortStr}
            options={EFFORT_VALUES}
            onChange={setEffortStr}
            disabled={disabled}
          />
        ),
      },
      // Capabilities --------------------------------------------------------
      {
        key: "skills",
        wrapInLabel: false,
        label: "Skills",
        group: "capabilities",
        value: skills.join(", "),
        onChange: (val) => setSkills(parseSkillSlugs(val)),
        serialize: () => {
          if (skills.length === 0) return null;
          return `skills:\n${skills.map((s) => `  - ${s}`).join("\n")}`;
        },
        renderInput: ({ disabled }) => (
          <AgentSkillsFieldEditor
            skills={skills}
            knownSkills={adoptedSkills}
            tagOptions={effectiveTagOptions}
            onChange={setSkills}
            disabled={disabled}
          />
        ),
      },
      {
        key: "mcpServers",
        label: "MCP Servers",
        group: "capabilities",
        value: mcpServersStr,
        onChange: setMcpServersStr,
        placeholder: "Comma-separated server references",
        helpText: detail.mcpServers?.length
          ? detail.mcpServers
              .map(({ name, mode }) => `${name}: ${mode === "inline" ? "inline per-agent" : "harness-level fallback"}`)
              .join("; ")
          : "Claude/Codex bind inline; other harnesses use a harness-level fallback.",
        serialize: serializeMcpServerRefs,
        renderInput: ({ disabled }) => (
          <AgentSkillsFieldEditor
            skills={parseMcpServerRefs(mcpServersStr)}
            knownSkills={managedMcpServers}
            onChange={(servers) => setMcpServersStr(servers.join(", "))}
            disabled={disabled}
            placeholder="Add MCP server..."
            itemLabel="MCP server"
            inputLabel="MCP Servers"
          />
        ),
      },
      {
        // The two block lists are different keys, not duplicates, so they sit
        // side by side with the key each one writes spelled out.
        key: "disallowedTools",
        label: "Disallowed Tools",
        group: "capabilities",
        value: disallowedToolsStr,
        onChange: setDisallowedToolsStr,
        placeholder: "e.g. Write, Edit, Agent(Explore)",
        helpText: "Comma-separated. Written as disallowedTools.",
      },
      {
        // Keep tools available when switching to raw YAML, but do not expose it in
        // the structured editor per the Claude-facing layout.
        key: "tools",
        hidden: true,
        label: "Tools (comma-separated)",
        group: "capabilities",
        value: toolsStr,
        onChange: setToolsStr,
        placeholder: "e.g. bash, edit, grep",
      },
      // Execution -----------------------------------------------------------
      {
        key: "memory",
        label: "Memory",
        group: "execution",
        value: memoryStr,
        onChange: setMemoryStr,
        renderInput: ({ disabled }) => (
          <FrontmatterChoiceSelect
            label="Memory"
            value={memoryStr}
            options={MEMORY_VALUES}
            onChange={setMemoryStr}
            disabled={disabled}
          />
        ),
      },
      {
        key: "maxTurns",
        label: "Max Turns",
        group: "execution",
        value: maxTurnsStr,
        onChange: setMaxTurnsStr,
        placeholder: `${MAX_TURNS_DEFAULT} — the default when the key is absent`,
      },
    ],
    [
      name,
      description,
      roleStr,
      harnessStr,
      harnessOptions,
      modelStr,
      effortStr,
      skills,
      adoptedSkills,
      effectiveTagOptions,
      maxTurnsStr,
      memoryStr,
      disallowedToolsStr,
      mcpServersStr,
      toolsStr,
    ],
  );

  const isDirty = useMemo(() => {
    if (name !== detail.name) return true;
    if (description !== detail.description) return true;
    if (roleStr !== (detail.role ?? "")) return true;
    if (harnessStr !== (detail.harness ?? "")) return true;
    if (toolsStr !== detail.tools.join(", ")) return true;
    if (prompt !== detail.prompt) return true;

    if (modelStr !== (detail.model ?? "")) return true;
    if (hermesProviderStr !== (detail.hermesProvider ?? "")) return true;
    if (effortStr !== (detail.effort ?? "")) return true;
    if (maxTurnsStr !== (detail.maxTurns ?? "")) return true;
    if (memoryStr !== (detail.memory ?? "")) return true;
    if (disallowedToolsStr !== (detail.disallowedTools ?? []).join(", ")) return true;
    if (mcpServersStr !== (detail.mcpServers ?? []).map((binding) => binding.name).join(", ")) return true;

    if (skills.length !== initialSkills.length) return true;
    for (let i = 0; i < skills.length; i++) {
      if (skills[i].toLowerCase() !== (initialSkills[i] || "").toLowerCase()) return true;
    }

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
  }, [name, description, roleStr, harnessStr, toolsStr, prompt, skills, initialSkills, otherEntries, detail, initialOtherEntries, modelStr, hermesProviderStr, effortStr, maxTurnsStr, memoryStr, disallowedToolsStr, mcpServersStr]);

  const handleCancelEdit = () => {
    setName(detail.name);
    setDescription(detail.description);
    setRoleStr(detail.role ?? "");
    setHarnessStr(detail.harness ?? "");
    setToolsStr(detail.tools.join(", "));
    setSkills(initialSkills);
    setModelStr(detail.model ?? "");
    setHermesProviderStr(detail.hermesProvider ?? "");
    setEffortStr(detail.effort ?? "");
    setMaxTurnsStr(detail.maxTurns ?? "");
    setMemoryStr(detail.memory ?? "");
    setDisallowedToolsStr((detail.disallowedTools ?? []).join(", "));
    setMcpServersStr((detail.mcpServers ?? []).map((binding) => binding.name).join(", "));
    setOtherEntries(initialOtherEntries);
    setPrompt(detail.prompt);
    setSaveError(null);
    setFrontmatterMode("structured");
  };

  const handleSaveDocument = async () => {
    setSaveError(null);

    let finalName = name;
    let finalDesc = description;
    let finalRole = roleStr;
    let finalHarness = harnessStr;
    let finalToolsStr = toolsStr;
    let finalSkills = skills;
    let finalModel = modelStr;
    let finalEffort = effortStr;
    let finalMaxTurns = maxTurnsStr;
    let finalMemory = memoryStr;
    let finalDisallowedToolsStr = disallowedToolsStr;
    const finalMcpServersStr = mcpServersStr;
    let finalOther = otherEntries;

    if (frontmatterMode === "raw") {
      const parsed = parseFrontmatterFromYaml(rawYaml, [...AGENT_CONTRACT_KEYS, ...RETIRED_AGENT_KEYS, "mcpServers"]);
      if (parsed.error) {
        setSaveError(parsed.error);
        return;
      }
      finalName = parsed.known.name ?? name;
      finalDesc = parsed.known.description ?? description;
      finalRole = parsed.known.role ?? roleStr;
      finalHarness = parsed.known.harness ?? harnessStr;
      finalToolsStr = parsed.known.tools ?? toolsStr;
      finalSkills = parseSkillSlugs(parsed.known.skills ?? "");
      finalModel = parsed.known.model ?? "";
      finalEffort = parsed.known.effort ?? "";
      finalMaxTurns = parsed.known.maxTurns ?? "";
      finalMemory = parsed.known.memory ?? "";
      finalDisallowedToolsStr = parsed.known.disallowedTools ?? "";
      finalOther = parsed.other;
      setName(finalName);
      setDescription(finalDesc);
      setRoleStr(finalRole);
      setHarnessStr(finalHarness);
      setToolsStr(finalToolsStr);
      setSkills(finalSkills);
      setModelStr(finalModel);
      setEffortStr(finalEffort);
      setMaxTurnsStr(finalMaxTurns);
      setMemoryStr(finalMemory);
      setDisallowedToolsStr(finalDisallowedToolsStr);
      setMcpServersStr(finalMcpServersStr);
      setOtherEntries(finalOther);
    }

    if (!finalName.trim()) {
      setSaveError("Agent name cannot be empty.");
      return;
    }

    const toolsList = frontmatterMode === "raw"
      ? finalToolsStr.split(",").map((t) => t.trim()).filter(Boolean)
      : undefined;

    const metadataPayload = [
      ...finalOther
      .filter((e) => e.key.trim().length > 0)
      .map((e) => ({
        key: e.key.trim(),
        value: e.value,
        ...(e.rawValue !== undefined && e.rawValue !== null
          ? { rawValue: e.rawValue }
          : {}),
      })),
    ];

    try {
      const result = await updateMutation.mutateAsync({
        ref: detail.ref,
        request: {
          name: finalName.trim(),
          description: finalDesc.trim(),
          prompt: prompt,
          role: finalRole.trim(),
          harness: finalHarness.trim(),
          ...(toolsList ? { tools: toolsList } : {}),
          skills: finalSkills,
          mcpServers: parseMcpServerRefs(finalMcpServersStr),
          model: finalModel.trim(),
          effort: finalEffort.trim(),
          maxTurns: finalMaxTurns.trim(),
          memory: finalMemory.trim(),
          disallowedTools: finalDisallowedToolsStr.split(",").map((tool) => tool.trim()).filter(Boolean),
          hermesProvider: hermesProviderStr.trim(),
          hermesModel: "",
          metadata: metadataPayload,
        },
      });

      const autoList = result?.autoEnabled || [];
      const failList = result?.failed || [];

      if (autoList.length > 0 && failList.length === 0) {
        const items = autoList
          .map((item) => `enabled ${item.skillRef.replace(/^shared:/, "")} on ${item.harness}`)
          .join(", ");
        toast(`Updated ${finalName.trim()}. Auto-enabled: ${items}`);
      } else if (failList.length > 0) {
        const autoItems = autoList.length > 0
          ? ` Auto-enabled: ${autoList.map((item) => `${item.skillRef.replace(/^shared:/, "")} on ${item.harness}`).join(", ")}.`
          : "";
        const failItems = failList
          .map((f) => `${f.skillRef.replace(/^shared:/, "")} on ${f.harness}: ${f.error}`)
          .join(", ");
        toast(`Updated ${finalName.trim()}.${autoItems} Failed on: ${failItems}`);
      } else {
        toast(`Successfully updated ${finalName.trim()}`);
      }

      setFrontmatterMode("structured");
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
      await deleteMutation.mutateAsync(detail.ref);
      setDeleteDialogOpen(false);
      onClose();
    } catch (err) {
      // Keep the detail view mounted when deletion fails so the user can see why
      // the action did not complete (for example, a permission or binding error).
      setLocalActionError(err instanceof Error ? err.message : "Failed to delete agent");
      setDeleteDialogOpen(false);
    }
  };

  const handleAdopt = async () => {
    setLocalActionError(null);
    try {
      const result = await adoptMutation.mutateAsync({ ref: detail.ref });
      if (result && "conflict" in result) {
        setConflict(result);
      } else {
        toast("Agent added to Harness Asset Manager");
        onClose();
      }
    } catch (err) {
      setLocalActionError(err instanceof Error ? err.message : "Could not adopt agent");
    }
  };

  const handleResolveConflict = async (onConflict: "keep_store" | "replace_store") => {
    if (!conflict) return;
    setConflictPending(true);
    try {
      await adoptMutation.mutateAsync({ ref: conflict.slug, onConflict });
      setConflict(null);
      toast("Agent added to Harness Asset Manager");
      onClose();
    } catch (err) {
      setLocalActionError(err instanceof Error ? err.message : "Could not resolve conflict");
    } finally {
      setConflictPending(false);
    }
  };

  const handleUnmanage = async () => {
    setLocalActionError(null);
    try {
      const promise = unmanageMutation.mutateAsync(detail.ref);
      setRemoveDialogOpen(false);
      onClose();
      await promise;
      toast("Agent removed from Harness Asset Manager");
    } catch (err) {
      setLocalActionError(err instanceof Error ? err.message : "Failed to remove agent from Harness Asset Manager");
      setRemoveDialogOpen(false);
    }
  };

  const isDeleting = deleteMutation.isPending;
  const isAdopting = adoptMutation.isPending;
  const isUnmanaging = unmanageMutation.isPending;
  const isUnmanaged = detail.storePath === null;
  const hasEnabledHarness = detail.harnesses.some((h) => h.state === "enabled");
  const isRemoveBlocked = !hasEnabledHarness || isUnmanaging || isDeleting;
  const removeTooltip = !hasEnabledHarness
    ? "Enable at least one harness before removing this agent from Harness Asset Manager."
    : "Removes this agent from the Harness Asset Manager store and restores local copies only for the harnesses that are currently enabled.";


  return (
    <>
      <div className="skill-detail-shell__chrome">
        <div className="skill-detail__chrome">
          <DetailHeader
            title={<h2 id={headingId} className="skill-detail__title">{detail.name}</h2>}
            titleAction={(
              <button
                type="button"
                className={`skill-star-btn ${isStarred ? "skill-star-btn--active" : ""}`}
                aria-label={isStarred ? `Unstar ${detail.name}` : `Star ${detail.name}`}
                onClick={handleToggleStar}
              >
                <Star
                  size={18}
                  className={`skill-star-icon ${isStarred ? "skill-star-icon--filled" : ""}`}
                />
              </button>
            )}
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
          <DetailSection heading="Tags">
            <DetailTags
              tags={detail.tags || []}
              knownTags={knownTags}
              canEdit={true}
              onAddTag={handleAddTag}
              onRemoveTag={handleRemoveTag}
              disabled={setTagsMutation.isPending}
            />
          </DetailSection>

          <DocumentSection
            title="Document"
            editable={detail.canEdit}
            previewContent={(
              <Suspense fallback={<LoadingSpinner size="sm" label="Loading document" />}>
                <MarkdownDocument markdown={stripFrontmatter(detail.document) || detail.prompt} />
              </Suspense>
            )}
            editFrontmatter={(
              <>
                <div className="agent-frontmatter-editor">
                  <FrontmatterEditor
                    knownFields={knownFields}
                    fieldGroups={AGENT_FRONTMATTER_GROUPS}
                    otherEntries={otherEntries}
                    onChangeOtherEntries={setOtherEntries}
                    rawYaml={rawYaml}
                    onChangeRawYaml={setRawYaml}
                    mode={frontmatterMode}
                    onModeChange={setFrontmatterMode}
                    validationError={null}
                    disabled={updateMutation.isPending}
                  />
                </div>
                <div className="frontmatter-editor hermes-profile-editor">
                  <div className="frontmatter-editor__header">
                    <span className="frontmatter-editor__title">Hermes Profile</span>
                  </div>
                  <div className="frontmatter-editor__known-fields">
                    <label className="frontmatter-editor__field">
                      <span className="hermes-profile-editor__label">Hermes Provider</span>
                      <FrontmatterChoiceSelect
                        label="Hermes Provider"
                        value={hermesProviderStr}
                        options={hermesProviderOptions}
                        onChange={setHermesProviderStr}
                        disabled={updateMutation.isPending}
                      />
                    </label>
                  </div>
                  <p className="frontmatter-editor__note">
                    Hermes profile skills and agents are verified supported targets. Hermes always uses
                    the shared Model field; provider choices come from Hermes configuration. HAM-managed Bots are addressed as hermes -p
                    &lt;name&gt; and do not install PATH wrapper scripts. External CLI backends and
                    sharing this profile's skills with a Codex app-server subprocess are out of scope.
                  </p>
                </div>
              </>
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
        </div>
      </div>

      <DetailActionFooter ariaLabel="Agent actions">
        {isUnmanaged ? (
          <button
            type="button"
            className="action-pill action-pill--md action-pill--accent"
            disabled={isAdopting || isDeleting}
            onClick={handleAdopt}
          >
            {isAdopting ? <Loader2 size={14} className="animate-spin agent-action-spinner" /> : null}
            Add to HarnessAM
          </button>
        ) : null}

        {!isUnmanaged ? (
          isRemoveBlocked ? (
            <UiTooltipTriggerBoundary
              content={removeTooltip}
              contentClassName="ui-popup--tooltip--hint"
              align="end"
            >
              <button
                type="button"
                className="action-pill action-pill--md"
                disabled={isRemoveBlocked}
                onClick={() => setRemoveDialogOpen(true)}
              >
                {isUnmanaging ? <Loader2 size={14} className="animate-spin agent-action-spinner" /> : null}
                Remove from HarnessAM
              </button>
            </UiTooltipTriggerBoundary>
          ) : (
            <UiTooltip content={removeTooltip} contentClassName="ui-popup--tooltip--hint" align="end">
              <button
                type="button"
                className="action-pill action-pill--md"
                disabled={isRemoveBlocked}
                onClick={() => setRemoveDialogOpen(true)}
              >
                {isUnmanaging ? <Loader2 size={14} className="animate-spin agent-action-spinner" /> : null}
                Remove from HarnessAM
              </button>
            </UiTooltip>
          )
        ) : null}

        {detail.canDelete ? (
          <button
            type="button"
            className="action-pill action-pill--md action-pill--danger"
            disabled={isDeleting || isUnmanaging}
            onClick={() => setDeleteDialogOpen(true)}
          >
            {isDeleting ? <Loader2 size={14} className="animate-spin agent-action-spinner" /> : null}
            Delete
          </button>
        ) : null}
      </DetailActionFooter>

      {detail.canDelete ? (
        <ConfirmActionDialog
          open={deleteDialogOpen}
          title={isUnmanaged ? "Delete local agent" : "Delete Agent"}
          description={isUnmanaged
            ? <>Are you sure you want to remove <strong>{detail.name}</strong> from this harness? This action cannot be undone.</>
            : <>Are you sure you want to delete <strong>{detail.name}</strong>? This action cannot be undone.</>}
          confirmLabel={isUnmanaged ? "Delete local agent" : "Delete Agent"}
          pendingLabel="Deleting"
          isPending={isDeleting}
          onOpenChange={setDeleteDialogOpen}
          onConfirm={handleDelete}
        />
      ) : null}

      <ConfirmActionDialog
        open={removeDialogOpen}
        title="Remove from Harness Asset Manager"
        description={<>Are you sure you want to remove <strong>{detail.name}</strong> from Harness Asset Manager? This will restore raw local files for currently enabled harnesses and stop tracking this agent.</>}
        confirmLabel="Remove from HarnessAM"
        pendingLabel="Removing..."
        isPending={isUnmanaging}
        onOpenChange={setRemoveDialogOpen}
        onConfirm={handleUnmanage}
      />

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

      <AdoptConflictDialog
        open={conflict !== null}
        slug={conflict?.slug ?? ""}
        storePath={conflict?.storePath ?? ""}
        harnessPath={conflict?.harnessPath ?? ""}
        isPending={conflictPending}
        onOpenChange={(open) => {
          if (!open) setConflict(null);
        }}
        onConfirm={handleResolveConflict}
      />
    </>
  );
}

