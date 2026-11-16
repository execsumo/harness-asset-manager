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

export const READ_TIMEOUT_MS = 30_000;
export const WRITE_TIMEOUT_MS = 120_000;
/** For calls that clone a repository, probe many servers or process a whole batch. */
export const LONG_RUNNING_TIMEOUT_MS = 300_000;

const TIMEOUT_MESSAGE =
  "The server did not respond in time. Check that harness-asset-manager is still running.";
const NETWORK_MESSAGE =
  "Could not reach the server. Check that harness-asset-manager is still running.";

export interface RequestOptions {
  /** Abort and fail with a `timeout` ApiError after this many milliseconds. */
  timeoutMs?: number;
  /** Caller-owned cancellation (for example TanStack Query's `signal`). Surfaces as an abort, not a timeout. */
  signal?: AbortSignal;
}

interface RequestSpec {
  method: "GET" | "POST" | "PUT" | "DELETE";
  path: string;
  body?: object;
  defaultTimeoutMs: number;
  options?: RequestOptions;
}

function abortError(reason?: unknown): unknown {
  return reason ?? new DOMException("The request was aborted.", "AbortError");
}

async function request<T>({ method, path, body, defaultTimeoutMs, options }: RequestSpec): Promise<T> {
  const timeoutMs = options?.timeoutMs ?? defaultTimeoutMs;
  const callerSignal = options?.signal;
  const controller = new AbortController();
  let timedOut = false;
  let onCallerAbort: (() => void) | null = null;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  // Settles when the request is aborted, even if fetch itself ignores the signal.
  const aborted = new Promise<never>((_resolve, reject) => {
    const fail = () => reject(timedOut ? new DOMException("Timed out.", "TimeoutError") : abortError(callerSignal?.reason));
    controller.signal.addEventListener("abort", fail, { once: true });
  });
  aborted.catch(() => undefined);

  if (callerSignal) {
    onCallerAbort = () => controller.abort();
    if (callerSignal.aborted) {
      onCallerAbort();
    } else {
      callerSignal.addEventListener("abort", onCallerAbort, { once: true });
    }
  }

  try {
    const hasBody = body !== undefined && body !== null;
    const headers =
      method === "POST" || method === "PUT"
        ? authHeaders({ "Content-Type": "application/json" })
        : authHeaders();
    const init: RequestInit = { method, signal: controller.signal };
    if (Object.keys(headers).length > 0) init.headers = headers;
    if (hasBody) init.body = JSON.stringify(body);
    const response = await Promise.race([fetch(apiPath(path), init), aborted]);
    const payload = await Promise.race([response.json().catch(() => null), aborted]);
    if (!response.ok) {
      const error = extractApiError(payload, response);
      throw new ApiError(error.message, error.code, response.status);
    }
    return payload as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (timedOut) throw new ApiError(TIMEOUT_MESSAGE, "timeout", 0);
    if (callerSignal?.aborted) throw error;
    if (error instanceof TypeError) throw new ApiError(NETWORK_MESSAGE, "network_error", 0);
    throw error;
  } finally {
    clearTimeout(timer);
    if (callerSignal && onCallerAbort) callerSignal.removeEventListener("abort", onCallerAbort);
  }
}

export async function fetchJson<T>(path: string, options?: RequestOptions): Promise<T> {
  return request<T>({ method: "GET", path, defaultTimeoutMs: READ_TIMEOUT_MS, options });
}

export async function postJson<T>(path: string, body?: object, options?: RequestOptions): Promise<T> {
  return request<T>({ method: "POST", path, body, defaultTimeoutMs: WRITE_TIMEOUT_MS, options });
}

export async function putJson<T>(path: string, body?: object, options?: RequestOptions): Promise<T> {
  return request<T>({ method: "PUT", path, body, defaultTimeoutMs: WRITE_TIMEOUT_MS, options });
}

export async function deleteJson<T>(path: string, options?: RequestOptions): Promise<T> {
  return request<T>({ method: "DELETE", path, defaultTimeoutMs: WRITE_TIMEOUT_MS, options });
}
