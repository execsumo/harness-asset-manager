import { fetchJson } from "../../../api/http";
import type { ActivityResponse } from "./types";

export async function fetchActivity(limit = 100): Promise<ActivityResponse> {
  return fetchJson<ActivityResponse>(`/activity?limit=${limit}`);
}
