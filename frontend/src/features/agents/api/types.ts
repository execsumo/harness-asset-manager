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
  "role",
  "harness",
  "color",
  // Which model runs it
  "model",
  "effort",
  // What it may reach for
  "tools",
  "disallowedTools",
  "skills",
  "memory",
  // The envelope it runs in
  "maxTurns",
  "isolation",
  "background",
] as const;

/**
 * The fixed vocabularies, each plus the empty choice that clears the key. Global, not
 * per-harness. Mirror the tuples of the same names in application/agents/model.py,
 * which reject anything else with a 400; keep the two sides in step or a picker offers
 * a value the API refuses. `model` is deliberately absent: its value set is open.
 */
export const EFFORT_VALUES = ["low", "medium", "high", "xhigh", "max"] as const;
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
export const ISOLATION_VALUES = ["worktree"] as const;
export const BACKGROUND_VALUES = ["true", "false"] as const;
export const MEMORY_VALUES = ["user", "project", "local"] as const;

/**
 * What a harness assumes when `maxTurns` is absent. Shown as the field's placeholder
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
  role?: string;
  harness?: string;
  tools?: string[];
  skills?: string[];
  color?: string;
  model?: string;
  effort?: string;
  maxTurns?: string;
  isolation?: string;
  disallowedTools?: string[];
  background?: string;
  memory?: string;
  /** Hermes profile routing; values are passed through without a HAM vocabulary. */
  hermesProvider?: string;
  hermesModel?: string;
  harnesses?: string[];
}

export interface AgentUpdateRequest {
  name?: string;
  description?: string;
  prompt?: string;
  role?: string;
  harness?: string;
  tools?: string[];
  skills?: string[];
  /** Omitted carries the current value forward; an explicit empty string clears the key. */
  color?: string;
  model?: string;
  effort?: string;
  maxTurns?: string;
  isolation?: string;
  disallowedTools?: string[];
  background?: string;
  memory?: string;
  hermesProvider?: string;
  hermesModel?: string;
  metadata?: Array<{ key: string; value: string }>;
}

export interface AgentDetailDto {
  ref: string;
  name: string;
  description: string;
  prompt: string;
  role?: string | null;
  harness?: string | null;
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
  /** False for unmanaged agents that cannot be edited in place. */
  canEdit: boolean;
  tags?: string[];
  skills?: AgentSkillDto[];
  color?: string | null;
  model?: string | null;
  effort?: string | null;
  maxTurns?: string | null;
  isolation?: string | null;
  disallowedTools?: string[];
  background?: string | null;
  memory?: string | null;
  hermesProvider?: string | null;
  hermesModel?: string | null;
  ok?: boolean;
  autoEnabled?: AutoEnabledSkillDto[];
  failed?: AutoEnableFailureDto[];
  harnessFailures?: AgentMutationFailureDto[];
}
