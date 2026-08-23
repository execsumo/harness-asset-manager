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
}

export interface AgentUpdateRequest {
  name?: string;
  description?: string;
  prompt?: string;
  tools?: string[];
  metadata?: Array<{ key: string; value: string }>;
}

export interface AgentSummaryResponse {
  ref: string;
  name: string;
  description: string;
  slug: string;
  prompt?: string;
  tools?: string[];
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
}
