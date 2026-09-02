import { fetchJson, postJson } from "../../api/http";
import type {
  AdoptionActionDto,
  AdoptionApplyResponse,
  AdoptionDismissResponse,
  AdoptionPlanDto,
} from "./types";

export function fetchAdoptionPlan(): Promise<AdoptionPlanDto> {
  return fetchJson<AdoptionPlanDto>("/api/adopt/plan");
}

export function applyAdoption(
  actions: AdoptionActionDto[],
  allowConflicts = false,
): Promise<AdoptionApplyResponse> {
  return postJson<AdoptionApplyResponse>("/api/adopt/apply", {
    actions,
    allowConflicts,
  });
}

export function dismissAdoption(): Promise<AdoptionDismissResponse> {
  return postJson<AdoptionDismissResponse>("/api/adopt/dismiss", {});
}

export function resetDismissAdoption(): Promise<AdoptionDismissResponse> {
  return postJson<AdoptionDismissResponse>("/api/adopt/reset-dismiss", {});
}
