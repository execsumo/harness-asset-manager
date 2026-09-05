import { fetchJson, postJson } from "../../api/http";
import type {
  BootstrapActionDto,
  BootstrapApplyResponse,
  BootstrapDismissResponse,
  BootstrapPlanDto,
} from "./types";

export function fetchBootstrapPlan(): Promise<BootstrapPlanDto> {
  return fetchJson<BootstrapPlanDto>("/api/bootstrap/plan");
}

export function applyBootstrap(
  actions: BootstrapActionDto[],
  allowConflicts = false,
): Promise<BootstrapApplyResponse> {
  return postJson<BootstrapApplyResponse>("/api/bootstrap/apply", {
    actions,
    allowConflicts,
  });
}

export function dismissBootstrap(): Promise<BootstrapDismissResponse> {
  return postJson<BootstrapDismissResponse>("/api/bootstrap/dismiss", {});
}

export function resetDismissBootstrap(): Promise<BootstrapDismissResponse> {
  return postJson<BootstrapDismissResponse>("/api/bootstrap/reset-dismiss", {});
}
