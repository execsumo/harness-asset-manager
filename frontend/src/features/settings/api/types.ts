import type { components } from "../../../api/generated";

export type SetHarnessSupportRequest = components["schemas"]["SetHarnessSupportRequest"];
export type SettingsData = components["schemas"]["SettingsResponse"];
export type SettingsHarness = components["schemas"]["SettingsHarnessResponse"];

export interface ConfigSnapshotItem {
  snapshot_id: string;
  harness: string;
  config_name: string;
  timestamp: string;
  trigger: "manual" | "external" | "pre_write";
  sha256: string;
  snapshot_path: string;
}

export interface ConfigSnapshotsResponse {
  snapshots: ConfigSnapshotItem[];
}
