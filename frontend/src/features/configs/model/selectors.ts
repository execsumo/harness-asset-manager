import type { ConfigsPayload } from "../api/types";

export interface ConfigRowData {
  harness: string;
  managed: boolean;
  keyCount: number;
  driftState: string;
  sourceFile: string;
  capturedAt: string | null;
  preferences: Record<string, unknown>;
  tags: string[];
}

export function selectConfigsRows(
  data: ConfigsPayload | undefined
): ConfigRowData[] {
  if (!data) return [];
  
  return Object.entries(data).map(([harness, record]) => {
    return {
      harness,
      ...record,
      tags: record.tags || [],
    };
  });
}
