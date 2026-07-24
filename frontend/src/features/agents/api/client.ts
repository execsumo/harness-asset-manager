import { fetchJson, postJson, putJson, deleteJson } from "../../../api/http";
import { apiPath } from "../../../api/paths";
import type {
  AgentInventoryDto,
  AgentScaffoldRequest,
  AgentScaffoldResponse,
  AgentUpdateRequest,
  AgentSummaryResponse,
  AgentAdoptConflict,
  AdoptAllResponse,
} from "./types";

export async function fetchAgentsInventory(): Promise<AgentInventoryDto> {
  return fetchJson<AgentInventoryDto>("/api/v1/agents");
}

export async function scaffoldAgent(
  request: AgentScaffoldRequest,
): Promise<AgentScaffoldResponse> {
  return postJson<AgentScaffoldResponse>("/api/v1/agents/scaffold", request);
}

export async function updateAgent({
  ref,
  request,
}: {
  ref: string;
  request: AgentUpdateRequest;
}): Promise<AgentSummaryResponse> {
  // Using patch is correct, we can use fetch for it since patchJson doesn't exist.
  const response = await fetch(apiPath(`/api/v1/agents/${ref}`), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail ?? err.message ?? "Failed to update agent");
  }
  return response.json() as Promise<AgentSummaryResponse>;
}

export async function adoptAgent(
  ref: string,
  onConflict?: "keep_store" | "replace_store",
): Promise<void | AgentAdoptConflict> {
  const query = onConflict ? `?on_conflict=${onConflict}` : "";
  const response = await fetch(apiPath(`/api/v1/agents/${ref}/adopt${query}`), {
    method: "POST",
  });
  if (response.status === 409) {
    return (await response.json()) as AgentAdoptConflict;
  }
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.detail ?? err.message ?? "Failed to adopt agent");
  }
}

export async function adoptAllAgents(): Promise<AdoptAllResponse> {
  return postJson<AdoptAllResponse>("/api/v1/agents/adopt-all");
}

export async function deleteAgent(ref: string): Promise<void> {
  await deleteJson<void>(`/api/v1/agents/${ref}`);
}

export async function enableAgent(ref: string, harness: string): Promise<void> {
  await postJson<void>(`/api/v1/agents/${ref}/bindings/${harness}`);
}

export async function disableAgent(ref: string, harness: string): Promise<void> {
  await deleteJson<void>(`/api/v1/agents/${ref}/bindings/${harness}`);
}
