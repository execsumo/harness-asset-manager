import { apiPath } from "./paths";

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(message: string, code: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

async function expectJson<T>(responsePromise: Promise<Response>): Promise<T> {
  const response = await responsePromise;
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const error = extractApiError(payload, response);
    throw new ApiError(error.message, error.code, response.status);
  }
  return payload as T;
}

function extractApiError(
  payload: unknown,
  response: Response,
): { code: string; message: string } {
  if (payload && typeof payload === "object") {
    const record = payload as Record<string, unknown>;
    const code = typeof record.code === "string" ? record.code : null;
    if (typeof record.error === "string") {
      return { code: code ?? fallbackErrorCode(response.status), message: record.error };
    }
    if (typeof record.detail === "string") {
      return { code: code ?? fallbackErrorCode(response.status), message: record.detail };
    }
    if (Array.isArray(record.detail) && record.detail.length > 0) {
      const first = record.detail[0] as { msg?: unknown; loc?: unknown };
      if (first && typeof first.msg === "string") {
        const fieldParts = Array.isArray(first.loc) ? first.loc.filter((part) => part !== "body") : [];
        const field = fieldParts.join(".");
        return {
          code: code ?? "validation_error",
          message: field ? `${field}: ${first.msg}` : first.msg,
        };
      }
    }
  }
  return {
    code: fallbackErrorCode(response.status),
    message: `${response.status} ${response.statusText}`,
  };
}

function fallbackErrorCode(status: number): string {
  if (status === 404) return "not_found";
  if (status === 409) return "conflict";
  if (status === 422) return "validation_error";
  if (status >= 500) return "internal_error";
  return "request_failed";
}

export function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}

export async function fetchJson<T>(path: string): Promise<T> {
  return expectJson<T>(fetch(apiPath(path)));
}

export async function postJson<T>(path: string, body?: object): Promise<T> {
  return expectJson<T>(
    fetch(apiPath(path), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    }),
  );
}

export async function putJson<T>(path: string, body?: object): Promise<T> {
  return expectJson<T>(
    fetch(apiPath(path), {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    }),
  );
}

export async function deleteJson<T>(path: string): Promise<T> {
  return expectJson<T>(fetch(apiPath(path), { method: "DELETE" }));
}
