/**
 * The agent contract, in canonical render order — the frontmatter keys the backend
 * parses into their own fields and renders first. Mirrors CONTRACT_KEYS in
 * application/agents/model.py; anything not in this list is custom configuration
 * and is round-tripped verbatim.
 */
export const AGENT_CONTRACT_KEYS = [
  // Identity
  "name",
  "description",
  "color",
  // Which model runs it
  "model",
  "effort",
  // What it may reach for
  "tools",
  "skills",
  "allowed_subagents",
  // The envelope it runs in
  "max_turns",
  "isolation",
] as const;

/**
 * The fixed vocabularies, each plus the empty choice that clears the key. Global, not
 * per-harness. Mirror the tuples of the same names in application/agents/model.py,
 * which reject anything else with a 400; keep the two sides in step or a picker offers
 * a value the API refuses. `model` is deliberately absent: its value set is open.
 */
export const EFFORT_VALUES = ["low", "medium", "high"] as const;
export const COLOR_VALUES = [
  "red",
  "blue",
  "green",
  "yellow",
  "purple",
  "orange",
  "pink",
  "cyan",
] as const;
export const ISOLATION_VALUES = ["worktree", "none"] as const;
export const ALLOWED_SUBAGENTS_VALUES = ["true", "false"] as const;

/**
 * What a harness assumes when `max_turns` is absent. Shown as the field's placeholder
 * rather than written on save — filling every agent file with a value nobody asked for
 * would freeze an implicit default into an explicit setting.
 */
export const MAX_TURNS_DEFAULT = 30;

export interface AgentSkillDto {
  slug: string;
  name: string;
}

export interface AutoEnabledSkillDto {
  skillRef: string;
  harness: string;
}

export interface AutoEnableFailureDto {
  skillRef: string;
  harness: string;
  error: string;
}

export interface AgentMutationFailureDto {
  harness: string;
  error: string;
}

export interface AgentRepairDto {
  at: number;
  ref: string;
  harness: string;
  action: "relinked" | "adopted" | "conflict_preserved" | "refused";
  detail: string;
}

export interface AgentInventoryDto {
  columns: Array<{ harness: string; label: string; logoKey: string | null; installed: boolean }>;
  entries: AgentInventoryEntryDto[];
  issues: Array<{ name: string; reason: string }>;
  recentRepairs?: AgentRepairDto[];
}

export interface AgentInventoryEntryDto {
  ref: string;
  name: string;
  description: string;
  kind: "managed" | "unmanaged";
  harnessPath: string | null;
  bindings: Array<{
    harness: string;
    state: "enabled" | "disabled" | "unsupported";
    detail: string | null;
  }>;
  actions: { canAdopt: boolean; canDelete: boolean };
  tags?: string[];
  skills?: AgentSkillDto[];
}

export interface AgentAdoptConflict {
  conflict: "store-name-exists";
  slug: string;
  storePath: string;
  harnessPath: string;
}

export interface AdoptAllResponse {
  ok: boolean;
  adopted: string[];
  skipped: Array<{ ref: string; reason: string }>;
}

export interface AgentCreateRequest {
  name: string;
  description: string;
  prompt: string;
  tools?: string[];
  skills?: string[];
  color?: string;
  model?: string;
  effort?: string;
  allowedSubagents?: string;
  maxTurns?: string;
  isolation?: string;
  harnesses?: string[];
}

export interface AgentUpdateRequest {
  name?: string;
  description?: string;
  prompt?: string;
  tools?: string[];
  skills?: string[];
  /** Omitted carries the current value forward; an explicit empty string clears the key. */
  color?: string;
  model?: string;
  effort?: string;
  allowedSubagents?: string;
  maxTurns?: string;
  isolation?: string;
  metadata?: Array<{ key: string; value: string }>;
}

export interface AgentSummaryResponse {
  ref: string;
  name: string;
  description: string;
  slug: string;
  prompt?: string;
  tools?: string[];
  skills?: AgentSkillDto[];
}

export interface AgentDetailDto {
  ref: string;
  name: string;
  description: string;
  prompt: string;
  tools: string[];
  document: string;
  /** Null for unmanaged inspections — there is no store copy until adoption. */
  storePath: string | null;
  harnesses: Array<{
    harness: string;
    label: string;
    logoKey: string | null;
    state: "enabled" | "disabled" | "unsupported";
    detail: string | null;
    path: string;
    installMethod: "symlink" | "rendered" | "none";
    installed: boolean;
  }>;
  /** Frontmatter beyond name/description, verbatim and in file order. */
  configuration: Array<{ key: string; value: string }>;
  canDelete: boolean;
  /** False for unmanaged agents: read-only until adopted. */
  canEdit: boolean;
  tags?: string[];
  skills?: AgentSkillDto[];
  color?: string | null;
  model?: string | null;
  effort?: string | null;
  allowedSubagents?: string | null;
  maxTurns?: string | null;
  isolation?: string | null;
  ok?: boolean;
  autoEnabled?: AutoEnabledSkillDto[];
  failed?: AutoEnableFailureDto[];
  harnessFailures?: AgentMutationFailureDto[];
}
