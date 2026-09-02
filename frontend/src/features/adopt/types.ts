export type AdoptionActionType = "link" | "skip" | "conflict";

export interface AdoptionActionDto {
  family: string;
  ref: string;
  displayName: string;
  harness: string;
  action: AdoptionActionType;
  targetPath: string;
  reason?: string | null;
  detail?: string | null;
}

export interface AdoptionPlanDto {
  actions: AdoptionActionDto[];
  linkableCount: number;
  conflictCount: number;
  skippedCount: number;
  totalCount: number;
  dismissed: boolean;
}

export interface AdoptionApplyResultDto {
  family: string;
  ref: string;
  harness: string;
  status: "applied" | "failed" | "skipped";
  target: string;
  error?: string | null;
}

export interface AdoptionApplyResponse {
  results: AdoptionApplyResultDto[];
  appliedCount: number;
  failedCount: number;
}

export interface AdoptionDismissResponse {
  ok: boolean;
  dismissed: boolean;
}
