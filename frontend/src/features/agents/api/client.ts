import { fetchJson, postJson, putJson, deleteJson } from "../../../api/http";
import { apiPath } from "../../../api/paths";
import type {
  AgentInventoryDto,
  AgentCreateRequest,
  AgentUpdateRequest,
  AgentSummaryResponse,
  AgentAdoptConflict,
  AdoptAllResponse,
} from "./types";

export async function fetchAgentsInventory(): Promise<AgentInventoryDto> {
  return fetchJson<AgentInventoryDto>("/api/agents");
}

export async function createAgent(
  request: AgentCreateRequest,
): Promise<AgentSummaryResponse> {
  return postJson<AgentSummaryResponse>("/api/agents", request);
}

export async function updateAgent({
  ref,
  request,
}: {
  ref: string;
  request: AgentUpdateRequest;
}): Promise<AgentSummaryResponse> {
  return putJson<AgentSummaryResponse>(`/api/agents/${ref}`, request);
}

export async function adoptAgent(
  ref: string,
  onConflict?: "keep_store" | "replace_store",
): Promise<void | AgentAdoptConflict> {
  const body = onConflict ? { onConflict } : undefined;
  const response = await fetch(apiPath(`/api/agents/${ref}/adopt`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (response.status === 409) {
    return (await response.json()) as AgentAdoptConflict;
  }
  if (!response.ok) {
    const err = await response.json().catch(() => ({}));
    throw new Error(err.error ?? "Failed to adopt agent");
  }
}

export async function adoptAllAgents(): Promise<AdoptAllResponse> {
  return postJson<AdoptAllResponse>("/api/agents/adopt-all");
}

export async function deleteAgent(ref: string): Promise<void> {
  await deleteJson<void>(`/api/agents/${ref}`);
}

export async function enableAgent(ref: string, harness: string): Promise<void> {
  await postJson<void>(`/api/agents/${ref}/enable`, { harness });
}

export async function disableAgent(ref: string, harness: string): Promise<void> {
  await postJson<void>(`/api/agents/${ref}/disable`, { harness });
}

export async function setAgentHarnesses(ref: string, harnesses: string[]): Promise<void> {
  await postJson<void>(`/api/agents/${ref}/set-harnesses`, { harnesses });
}
