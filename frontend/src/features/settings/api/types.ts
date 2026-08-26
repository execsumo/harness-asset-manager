import type { components } from "../../../api/generated";

export type SetHarnessSupportRequest = components["schemas"]["SetHarnessSupportRequest"];
export type SettingsData = components["schemas"]["SettingsResponse"];
export type SettingsHarness = components["schemas"]["SettingsHarnessResponse"];

/** One harness's captured preferences, as returned by `GET /api/configs/`. */
export interface ConfigRecordResponse {
  capturedAt: string;
  revision: string;
  preferences: Record<string, unknown>;
}

export type ConfigsResponse = Record<string, ConfigRecordResponse>;

/** `GET /api/configs/{harness}/diff` — key-level comparison against the manifest. */
export interface ConfigDiffResponse {
  state: "managed" | "drifted" | "unmanaged";
  missing: string[];
  extra: string[];
  changed: string[];
}
