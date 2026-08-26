export interface ConfigsPayload {
  [harness: string]: {
    managed: boolean;
    keyCount: number;
    driftState: string;
    sourceFile: string;
    capturedAt: string | null;
    preferences: Record<string, unknown>;
    tags: string[];
  };
}

export interface ConfigDiff {
  state: "managed" | "unmanaged" | "drifted";
  missing: string[];
  extra: string[];
  changed: string[];
}
