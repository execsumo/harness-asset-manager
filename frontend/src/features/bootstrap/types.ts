export type BootstrapActionType = "link" | "skip" | "conflict";

export interface BootstrapActionDto {
  family: string;
  ref: string;
  displayName: string;
  harness: string;
  action: BootstrapActionType;
  targetPath: string;
  reason?: string | null;
  detail?: string | null;
}

export interface BootstrapPlanDto {
  actions: BootstrapActionDto[];
  linkableCount: number;
  conflictCount: number;
  skippedCount: number;
  totalCount: number;
  dismissed: boolean;
}

export interface BootstrapApplyResultDto {
  family: string;
  ref: string;
  harness: string;
  status: "applied" | "failed" | "skipped";
  target: string;
  error?: string | null;
}

export interface BootstrapApplyResponse {
  results: BootstrapApplyResultDto[];
  appliedCount: number;
  failedCount: number;
}

export interface BootstrapDismissResponse {
  ok: boolean;
  dismissed: boolean;
}
