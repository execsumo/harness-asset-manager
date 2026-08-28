export type SlashTargetId = "claude" | "codex" | "agy" | "cursor" | "opencode" | "hermes" | "droid";
export type SlashRenderFormat = "frontmatter_markdown" | "cursor_plaintext";
export type SlashCommandScope = "global" | "project";

export type SlashSyncStatus =
  | "synced"
  | "removed"
  | "not_selected"
  | "blocked_manual_file"
  | "blocked_modified_file"
  | "missing"
  | "drifted"
  | "failed";

export type SlashReviewKind = "unmanaged" | "drifted" | "missing";
export type SlashReviewAction = "import" | "restore_managed" | "adopt_target" | "remove_binding";

export interface SlashTargetDto {
  id: SlashTargetId;
  label: string;
  rootPath: string;
  outputDir: string;
  invocationPrefix: string;
  renderFormat: SlashRenderFormat;
  scope: SlashCommandScope;
  docsUrl: string;
  fileGlob: string;
  supportsFrontmatter: boolean;
  supportNote?: string | null;
  defaultSelected: boolean;
  enabled: boolean;
  available: boolean;
  installed?: boolean;
}

export interface SlashSyncEntryDto {
  target: SlashTargetId;
  path: string;
  status: SlashSyncStatus;
  error?: string | null;
}

export interface SlashCommandDto {
  name: string;
  description: string;
  prompt: string;
  syncTargets: SlashSyncEntryDto[];
  metadata?: Array<{ key: string; value: string }>;
  tags?: string[];
}

export interface SlashCommandListDto {
  storePath: string;
  syncStatePath: string;
  targets: SlashTargetDto[];
  defaultTargets: SlashTargetId[];
  commands: SlashCommandDto[];
  reviewCommands: SlashCommandReviewDto[];
}

export interface SlashCommandMutationRequest {
  name: string;
  description: string;
  prompt: string;
  targets?: SlashTargetId[];
}

export interface SlashCommandUpdateRequest {
  description: string;
  prompt: string;
  targets?: SlashTargetId[];
  metadata?: Array<{ key: string; value: string }>;
}

export interface SlashSyncRequest {
  targets?: SlashTargetId[];
}

export interface SlashCommandReviewDto {
  reviewRef: string;
  kind: SlashReviewKind;
  target: SlashTargetId;
  targetLabel: string;
  name: string;
  path: string;
  description: string;
  prompt: string;
  commandExists: boolean;
  canImport: boolean;
  actions: SlashReviewAction[];
  error?: string | null;
  tags?: string[];
}

export interface SlashCommandImportRequest {
  target: SlashTargetId;
  name: string;
}

export interface SlashCommandResolveRequest {
  target: SlashTargetId;
  name: string;
  action: Exclude<SlashReviewAction, "import">;
}

export interface SlashCommandMutationResponse {
  ok: boolean;
  command: SlashCommandDto | null;
  sync: SlashSyncEntryDto[];
}

export interface SlashCommandDeleteResponse {
  ok: boolean;
  sync: SlashSyncEntryDto[];
}
