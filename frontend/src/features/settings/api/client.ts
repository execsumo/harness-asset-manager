import { fetchJson, postJson, putJson } from "../../../api/http";
import type { ConfigSnapshotsResponse, SetHarnessSupportRequest, SettingsData } from "./types";

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

export async function fetchConfigSnapshots(harness?: string): Promise<ConfigSnapshotsResponse> {
  const url = harness ? `/config-snapshots?harness=${encodeURIComponent(harness)}` : "/config-snapshots";
  return fetchJson<ConfigSnapshotsResponse>(url);
}

export async function triggerConfigSnapshot(): Promise<{ ok: boolean; captured_count: number; captured: string[] }> {
  return postJson<{ ok: boolean; captured_count: number; captured: string[] }>("/config-snapshots/trigger", {});
}
