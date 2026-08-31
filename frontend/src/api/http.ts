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

export function getApiToken(): string | null {
  if (typeof document !== "undefined") {
    const meta = document.querySelector('meta[name="ham-api-token"]');
    const content = meta?.getAttribute("content");
    if (content && content.trim() !== "") {
      return content.trim();
    }
  }
  const devToken = import.meta.env?.VITE_API_TOKEN;
  if (typeof devToken === "string" && devToken.trim() !== "") {
    return devToken.trim();
  }
  return null;
}

export function authHeaders(existing?: Record<string, string>): Record<string, string> {
  const token = getApiToken();
  const headers: Record<string, string> = { ...existing };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
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
  if (response.status === 401) {
    return {
      code: "unauthorized",
      message: "Authentication failed or token expired. If the server restarted, please refresh the page.",
    };
  }
  return {
    code: fallbackErrorCode(response.status),
    message: `${response.status} ${response.statusText}`,
  };
}

function fallbackErrorCode(status: number): string {
  if (status === 401) return "unauthorized";
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
  const headers = authHeaders();
  return expectJson<T>(
    Object.keys(headers).length > 0 ? fetch(apiPath(path), { headers }) : fetch(apiPath(path)),
  );
}

export async function postJson<T>(path: string, body?: object): Promise<T> {
  return expectJson<T>(
    fetch(apiPath(path), {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: body ? JSON.stringify(body) : undefined,
    }),
  );
}

export async function putJson<T>(path: string, body?: object): Promise<T> {
  return expectJson<T>(
    fetch(apiPath(path), {
      method: "PUT",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: body ? JSON.stringify(body) : undefined,
    }),
  );
}

export async function deleteJson<T>(path: string): Promise<T> {
  const headers = authHeaders();
  return expectJson<T>(
    fetch(apiPath(path), {
      method: "DELETE",
      ...(Object.keys(headers).length > 0 ? { headers } : {}),
    }),
  );
}
