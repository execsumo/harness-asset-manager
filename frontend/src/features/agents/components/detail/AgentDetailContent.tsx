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
import {
  AGENT_CONTRACT_KEYS,
  BACKGROUND_VALUES,
  MODE_DEFAULT,
  MODE_VALUES,
  SPAWNING_DEFAULT,
  TRUST_PROJECT_DEFAULT,
  COLOR_VALUES,
  EFFORT_VALUES,
  ISOLATION_VALUES,
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
  const [colorStr, setColorStr] = useState(detail.color ?? "");
  const [modelStr, setModelStr] = useState(detail.model ?? "");
  const [hermesProviderStr, setHermesProviderStr] = useState(detail.hermesProvider ?? "");
  const [hermesModelStr, setHermesModelStr] = useState(detail.hermesModel ?? "");
  const [effortStr, setEffortStr] = useState(detail.effort ?? "");
  const [maxTurnsStr, setMaxTurnsStr] = useState(detail.maxTurns ?? "");
  const [isolationStr, setIsolationStr] = useState(detail.isolation ?? "");
  const [backgroundStr, setBackgroundStr] = useState(detail.background ?? "");
  const [memoryStr, setMemoryStr] = useState(detail.memory ?? "");
  const [disallowedToolsStr, setDisallowedToolsStr] = useState((detail.disallowedTools ?? []).join(", "));
  const [mcpServersStr, setMcpServersStr] = useState(
    detail.configuration.find((entry) => entry.key === "mcpServers")?.value ?? "",
  );
  const [modeStr, setModeStr] = useState(detail.mode ?? MODE_DEFAULT);
  const [spawningStr, setSpawningStr] = useState(detail.spawning ?? SPAWNING_DEFAULT);
  const [trustProjectStr, setTrustProjectStr] = useState(detail.trustProject ?? TRUST_PROJECT_DEFAULT);
  const [denyToolsStr, setDenyToolsStr] = useState((detail.denyTools ?? []).join(", "));
  const [otherEntries, setOtherEntries] = useState<OtherFrontmatterEntry[]>(initialOtherEntries);
  const [rawYaml, setRawYaml] = useState("");
  const [prompt, setPrompt] = useState(detail.prompt);
  const [saveError, setSaveError] = useState<string | null>(null);
  const hermesProviders = hermesOptionsQuery.data?.providers ?? [];
  const selectedHermesProvider = hermesProviders.find((provider) => provider.id === hermesProviderStr);
  const hermesModels = Array.from(new Set([
    detail.model,
    detail.hermesModel,
    hermesModelStr,
    ...(selectedHermesProvider ? selectedHermesProvider.models : hermesProviders.flatMap((provider) => provider.models)),
  ].filter((value): value is string => Boolean(value))));

  useEffect(() => {
    setName(detail.name);
    setDescription(detail.description);
    setRoleStr(detail.role ?? "");
    setHarnessStr(detail.harness ?? "");
    setToolsStr(detail.tools.join(", "));
    setSkills((detail.skills || []).map((s) => s.slug));
    setColorStr(detail.color ?? "");
    setModelStr(detail.model ?? "");
    setHermesProviderStr(detail.hermesProvider ?? "");
    setHermesModelStr(detail.hermesModel ?? "");
    setEffortStr(detail.effort ?? "");
    setMaxTurnsStr(detail.maxTurns ?? "");
    setIsolationStr(detail.isolation ?? "");
    setBackgroundStr(detail.background ?? "");
    setMemoryStr(detail.memory ?? "");
    setDisallowedToolsStr((detail.disallowedTools ?? []).join(", "));
    setMcpServersStr(
      detail.configuration.find((entry) => entry.key === "mcpServers")?.value ?? "",
    );
    setModeStr(detail.mode ?? MODE_DEFAULT);
    setSpawningStr(detail.spawning ?? SPAWNING_DEFAULT);
    setTrustProjectStr(detail.trustProject ?? TRUST_PROJECT_DEFAULT);
    setDenyToolsStr((detail.denyTools ?? []).join(", "));
    setOtherEntries(
      (detail.configuration || [])
        .filter(
          (c) =>
            !(AGENT_CONTRACT_KEYS as readonly string[]).includes(c.key) &&
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
      {
        key: "name",
        label: "Agent Name",
        value: name,
        onChange: setName,
      },
      {
        key: "role",
        label: "Role",
        value: roleStr,
        onChange: setRoleStr,
        placeholder: "Describe this agent's role",
      },
      {
        key: "color",
        label: "Color",
        value: colorStr,
        onChange: setColorStr,
        renderInput: ({ disabled }) => (
          <FrontmatterChoiceSelect
            label="Color"
            value={colorStr}
            options={COLOR_VALUES}
            onChange={setColorStr}
            disabled={disabled}
          />
        ),
      },
      {
        key: "description",
        label: "Description",
        value: description,
        onChange: setDescription,
        placeholder: "Describe the agent's purpose and functionality",
      },
      {
        key: "harness",
        label: "Harness",
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
        value: modelStr,
        onChange: setModelStr,
        placeholder: "Model identifier — empty clears the key",
      },
      {
        key: "effort",
        label: "Effort",
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
      {
        key: "disallowedTools",
        label: "Disallowed Tools (comma-separated)",
        value: disallowedToolsStr,
        onChange: setDisallowedToolsStr,
        placeholder: "e.g. Write, Edit, Agent(Explore)",
      },
      {
        key: "maxTurns",
        label: "Max Turns",
        value: maxTurnsStr,
        onChange: setMaxTurnsStr,
        placeholder: `${MAX_TURNS_DEFAULT} — the default when the key is absent`,
      },
      {
        key: "mcpServers",
        label: "MCP Servers",
        value: mcpServersStr,
        onChange: setMcpServersStr,
        placeholder: "Comma-separated server references",
        serialize: serializeMcpServerRefs,
      },
      {
        key: "memory",
        label: "Memory",
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
        key: "isolation",
        label: "Isolation",
        value: isolationStr,
        onChange: setIsolationStr,
        renderInput: ({ disabled }) => (
          <FrontmatterChoiceSelect
            label="Isolation"
            value={isolationStr}
            options={ISOLATION_VALUES}
            onChange={setIsolationStr}
            disabled={disabled}
          />
        ),
      },
      {
        key: "background",
        label: "Background",
        value: backgroundStr,
        onChange: setBackgroundStr,
        renderInput: ({ disabled }) => (
          <FrontmatterChoiceSelect
            label="Background"
            value={backgroundStr}
            options={BACKGROUND_VALUES}
            onChange={setBackgroundStr}
            disabled={disabled}
          />
        ),
      },
      {
        key: "skills",
        wrapInLabel: false,
        label: "Skills",
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
        // Keep tools available when switching to raw YAML, but do not expose it in
        // the structured editor per the Claude-facing layout.
        key: "tools",
        hidden: true,
        label: "Tools (comma-separated)",
        value: toolsStr,
        onChange: setToolsStr,
        placeholder: "e.g. bash, edit, grep",
      },
      {
        key: "mode",
        label: "Mode",
        value: modeStr,
        onChange: setModeStr,
        renderInput: ({ disabled }) => (
          <select className="frontmatter-editor__input" value={modeStr} onChange={(event) => setModeStr(event.target.value)} disabled={disabled} aria-label="Mode">
            {MODE_VALUES.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        ),
      },
      {
        key: "spawning",
        label: "Spawning",
        value: spawningStr,
        onChange: setSpawningStr,
        renderInput: ({ disabled }) => (
          <FrontmatterChoiceSelect
            label="Spawning"
            value={spawningStr}
            options={BACKGROUND_VALUES}
            onChange={setSpawningStr}
            disabled={disabled}
          />
        ),
      },
      {
        key: "trust-project",
        label: "Trust Project",
        value: trustProjectStr,
        onChange: setTrustProjectStr,
        renderInput: ({ disabled }) => (
          <FrontmatterChoiceSelect
            label="Trust Project"
            value={trustProjectStr}
            options={BACKGROUND_VALUES}
            onChange={setTrustProjectStr}
            disabled={disabled}
          />
        ),
      },
      {
        key: "deny-tools",
        label: "Deny Tools (comma-separated)",
        value: denyToolsStr,
        onChange: setDenyToolsStr,
        placeholder: "e.g. web_search, shell",
      },
    ],
    [
      name,
      description,
      roleStr,
      harnessStr,
      harnessOptions,
      colorStr,
      modelStr,
      effortStr,
      skills,
      adoptedSkills,
      effectiveTagOptions,
      maxTurnsStr,
      isolationStr,
      backgroundStr,
      memoryStr,
      disallowedToolsStr,
      mcpServersStr,
      toolsStr,
      modeStr,
      spawningStr,
      trustProjectStr,
      denyToolsStr,
    ],
  );

  const isDirty = useMemo(() => {
    if (name !== detail.name) return true;
    if (description !== detail.description) return true;
    if (roleStr !== (detail.role ?? "")) return true;
    if (harnessStr !== (detail.harness ?? "")) return true;
    if (toolsStr !== detail.tools.join(", ")) return true;
    if (prompt !== detail.prompt) return true;

    if (colorStr !== (detail.color ?? "")) return true;
    if (modelStr !== (detail.model ?? "")) return true;
    if (hermesProviderStr !== (detail.hermesProvider ?? "")) return true;
    if (hermesModelStr !== (detail.hermesModel ?? "")) return true;
    if (effortStr !== (detail.effort ?? "")) return true;
    if (maxTurnsStr !== (detail.maxTurns ?? "")) return true;
    if (isolationStr !== (detail.isolation ?? "")) return true;
    if (backgroundStr !== (detail.background ?? "")) return true;
    if (memoryStr !== (detail.memory ?? "")) return true;
    if (disallowedToolsStr !== (detail.disallowedTools ?? []).join(", ")) return true;
    if (
      mcpServersStr !==
      (detail.configuration.find((entry) => entry.key === "mcpServers")?.value ?? "")
    ) return true;
    if (modeStr !== (detail.mode ?? MODE_DEFAULT)) return true;
    if (spawningStr !== (detail.spawning ?? SPAWNING_DEFAULT)) return true;
    if (trustProjectStr !== (detail.trustProject ?? TRUST_PROJECT_DEFAULT)) return true;
    if (denyToolsStr !== (detail.denyTools ?? []).join(", ")) return true;

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
  }, [name, description, roleStr, harnessStr, toolsStr, prompt, skills, initialSkills, otherEntries, detail, initialOtherEntries, colorStr, modelStr, hermesProviderStr, hermesModelStr, effortStr, maxTurnsStr, isolationStr, backgroundStr, memoryStr, disallowedToolsStr, mcpServersStr, modeStr, spawningStr, trustProjectStr, denyToolsStr]);

  const handleCancelEdit = () => {
    setName(detail.name);
    setDescription(detail.description);
    setRoleStr(detail.role ?? "");
    setHarnessStr(detail.harness ?? "");
    setToolsStr(detail.tools.join(", "));
    setSkills(initialSkills);
    setColorStr(detail.color ?? "");
    setModelStr(detail.model ?? "");
    setHermesProviderStr(detail.hermesProvider ?? "");
    setHermesModelStr(detail.hermesModel ?? "");
    setEffortStr(detail.effort ?? "");
    setMaxTurnsStr(detail.maxTurns ?? "");
    setIsolationStr(detail.isolation ?? "");
    setBackgroundStr(detail.background ?? "");
    setMemoryStr(detail.memory ?? "");
    setDisallowedToolsStr((detail.disallowedTools ?? []).join(", "));
    setMcpServersStr(
      detail.configuration.find((entry) => entry.key === "mcpServers")?.value ?? "",
    );
    setModeStr(detail.mode ?? MODE_DEFAULT);
    setSpawningStr(detail.spawning ?? SPAWNING_DEFAULT);
    setTrustProjectStr(detail.trustProject ?? TRUST_PROJECT_DEFAULT);
    setDenyToolsStr((detail.denyTools ?? []).join(", "));
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
    let finalColor = colorStr;
    let finalModel = modelStr;
    let finalEffort = effortStr;
    let finalMaxTurns = maxTurnsStr;
    let finalIsolation = isolationStr;
    let finalBackground = backgroundStr;
    let finalMemory = memoryStr;
    let finalDisallowedToolsStr = disallowedToolsStr;
    let finalMcpServersStr = mcpServersStr;
    let finalMode = modeStr;
    let finalSpawning = spawningStr;
    let finalTrustProject = trustProjectStr;
    let finalDenyToolsStr = denyToolsStr;
    let finalOther = otherEntries;

    if (frontmatterMode === "raw") {
      const parsed = parseFrontmatterFromYaml(rawYaml, [...AGENT_CONTRACT_KEYS, "mcpServers"]);
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
      finalColor = parsed.known.color ?? "";
      finalModel = parsed.known.model ?? "";
      finalEffort = parsed.known.effort ?? "";
      finalMaxTurns = parsed.known.maxTurns ?? "";
      finalIsolation = parsed.known.isolation ?? "";
      finalBackground = parsed.known.background ?? "";
      finalMemory = parsed.known.memory ?? "";
      finalDisallowedToolsStr = parsed.known.disallowedTools ?? "";
      finalMcpServersStr = parsed.known.mcpServers ?? "";
      finalMode = parsed.known.mode ?? MODE_DEFAULT;
      finalSpawning = parsed.known.spawning ?? SPAWNING_DEFAULT;
      finalTrustProject = parsed.known["trust-project"] ?? TRUST_PROJECT_DEFAULT;
      finalDenyToolsStr = parsed.known["deny-tools"] ?? "";
      finalOther = parsed.other;
      setName(finalName);
      setDescription(finalDesc);
      setRoleStr(finalRole);
      setHarnessStr(finalHarness);
      setToolsStr(finalToolsStr);
      setSkills(finalSkills);
      setColorStr(finalColor);
      setModelStr(finalModel);
      setEffortStr(finalEffort);
      setMaxTurnsStr(finalMaxTurns);
      setIsolationStr(finalIsolation);
      setBackgroundStr(finalBackground);
      setMemoryStr(finalMemory);
      setDisallowedToolsStr(finalDisallowedToolsStr);
      setMcpServersStr(finalMcpServersStr);
      setModeStr(finalMode);
      setSpawningStr(finalSpawning);
      setTrustProjectStr(finalTrustProject);
      setDenyToolsStr(finalDenyToolsStr);
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
      ...(parseMcpServerRefs(finalMcpServersStr).length > 0
        ? [{
            key: "mcpServers",
            value: JSON.stringify(parseMcpServerRefs(finalMcpServersStr)),
          }]
        : []),
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
          color: finalColor.trim(),
          model: finalModel.trim(),
          effort: finalEffort.trim(),
          maxTurns: finalMaxTurns.trim(),
          isolation: finalIsolation.trim(),
          background: finalBackground.trim(),
          memory: finalMemory.trim(),
          disallowedTools: finalDisallowedToolsStr.split(",").map((tool) => tool.trim()).filter(Boolean),
          mode: finalMode.trim(),
          spawning: finalSpawning.trim(),
          trustProject: finalTrustProject.trim(),
          denyTools: finalDenyToolsStr.split(",").map((tool) => tool.trim()).filter(Boolean),
          hermesProvider: hermesProviderStr.trim(),
          hermesModel: hermesModelStr.trim(),
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
                      <input
                        type="text"
                        className="frontmatter-editor__input"
                        list={`hermes-provider-options-${detail.ref}`}
                        value={hermesProviderStr}
                        onChange={(event) => setHermesProviderStr(event.target.value)}
                        disabled={updateMutation.isPending}
                        placeholder="Auto / choose a configured provider"
                        aria-label="Hermes Provider"
                      />
                      <datalist id={`hermes-provider-options-${detail.ref}`}>
                        {hermesProviders.map((provider) => (
                          <option key={provider.id} value={provider.id} />
                        ))}
                      </datalist>
                    </label>
                    <label className="frontmatter-editor__field">
                      <span className="hermes-profile-editor__label">Hermes Model</span>
                      <input
                        type="text"
                        className="frontmatter-editor__input"
                        list={`hermes-model-options-${detail.ref}`}
                        value={hermesModelStr}
                        onChange={(event) => setHermesModelStr(event.target.value)}
                        disabled={updateMutation.isPending}
                        placeholder={detail.model ? `Uses Model above (${detail.model})` : "Uses Hermes default or enter a model id"}
                        aria-label="Hermes Model"
                      />
                      <datalist id={`hermes-model-options-${detail.ref}`}>
                        {hermesModels.map((modelId) => (
                          <option key={modelId} value={modelId} />
                        ))}
                      </datalist>
                    </label>
                  </div>
                  <p className="frontmatter-editor__note">
                    Hermes profile skills and agents are verified supported targets. Hermes uses the
                    shared Model field unless Hermes Model overrides it; provider choices come from
                    Hermes configuration and can still be entered manually. HAM-managed Bots are addressed as hermes -p
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

