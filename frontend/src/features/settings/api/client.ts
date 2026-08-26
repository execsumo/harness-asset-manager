import { fetchJson, postJson, putJson } from "../../../api/http";
import type { SetHarnessSupportRequest, SettingsData } from "./types";

export async function fetchSettings(): Promise<SettingsData> {
  return fetchJson<SettingsData>("/settings");
}

export async function updateHarnessSupport(harness: string, enabled: boolean): Promise<{ ok: boolean; enabled: boolean }> {
  const body: SetHarnessSupportRequest = { enabled };
  return putJson<{ ok: boolean; enabled: boolean }>(
    `/settings/harnesses/${encodeURIComponent(harness)}/support`,
    body,
  );
}

export async function updateAutoAdopt(
  family: string,
  enabled: boolean,
): Promise<{ ok: boolean; autoAdopt: Record<string, boolean> }> {
  const body = { enabled };
  return putJson<{ ok: boolean; autoAdopt: Record<string, boolean> }>(
    `/settings/auto-adopt/${encodeURIComponent(family)}`,
    body,
  );
}

export async function updateAutoAdoptHarnesses(
  family: string,
  harnesses: string[],
): Promise<{ ok: boolean; autoAdoptHarnesses: Record<string, string[]> }> {
  return putJson<{ ok: boolean; autoAdoptHarnesses: Record<string, string[]> }>(
    `/settings/auto-adopt/${encodeURIComponent(family)}/harnesses`,
    { harnesses },
  );
}

export async function fetchConfigs(): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>("/configs/");
}

export async function fetchConfigDiff(harness: string): Promise<Record<string, unknown>> {
  return fetchJson<Record<string, unknown>>(`/configs/${encodeURIComponent(harness)}/diff`);
}


export async function captureConfigs(explicit: boolean = false): Promise<void> {
  return postJson<void>(`/configs/capture?explicit=${explicit}`);
}

export async function restoreConfig(harness: string): Promise<void> {
  return postJson<void>(`/configs/${encodeURIComponent(harness)}/restore`);
}
