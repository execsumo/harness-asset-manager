import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  READ_TIMEOUT_MS,
  WRITE_TIMEOUT_MS,
  authHeaders,
  deleteJson,
  fetchJson,
  getApiToken,
  postJson,
  putJson,
} from "./http";

describe("API errors", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    document.head.innerHTML = "";
  });

  it("preserves the backend code, message, and status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: async () => ({ code: "skill_not_found", error: "unknown skill ref: missing" }),
      }),
    );

    await expect(fetchJson("/skills/missing")).rejects.toMatchObject({
      name: "ApiError",
      code: "skill_not_found",
      status: 404,
      message: "unknown skill ref: missing",
    });
  });

  it("maps legacy validation payloads to a stable code", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        statusText: "Unprocessable Entity",
        json: async () => ({
          detail: [{ loc: ["body", "name"], msg: "Field required" }],
        }),
      }),
    );

    const request = fetchJson("/agents");
    await expect(request).rejects.toEqual(
      expect.objectContaining({
        code: "validation_error",
        status: 422,
        message: "name: Field required",
      }),
    );
    try {
      await request;
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
    }
  });

  it("handles 401 with clear authentication error message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        statusText: "Unauthorized",
        json: async () => {
          throw new Error("No JSON body");
        },
      }),
    );

    await expect(fetchJson("/settings")).rejects.toMatchObject({
      name: "ApiError",
      code: "unauthorized",
      status: 401,
      message: "Authentication failed or token expired. If the server restarted, please refresh the page.",
    });
  });

  it("extracts custom backend error message on 401 if present", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        statusText: "Unauthorized",
        json: async () => ({ error: "unauthorized: invalid bearer token" }),
      }),
    );

    await expect(fetchJson("/settings")).rejects.toMatchObject({
      name: "ApiError",
      code: "unauthorized",
      status: 401,
      message: "unauthorized: invalid bearer token",
    });
  });
});

describe("API Bearer Token Delivery", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns null when no dev token is configured", () => {
    expect(getApiToken()).toBeNull();
    expect(authHeaders()).toEqual({});
    expect(authHeaders({ "Content-Type": "application/json" })).toEqual({
      "Content-Type": "application/json",
    });
  });

  it("attaches Authorization header when authHeaders has token", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ok: true }),
    });
    vi.stubGlobal("fetch", mockFetch);

    await fetchJson("/test-get");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/test-get"),
      expect.objectContaining({ method: "GET", signal: expect.any(AbortSignal) }),
    );

    await postJson("/test-post", { data: 1 });
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/test-post"),
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data: 1 }),
      }),
    );
  });
});

describe("request timeouts and network failures", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  function hangingFetch() {
    // Never resolves and ignores the abort signal, like a stuck backend.
    return vi.fn(() => new Promise<Response>(() => undefined));
  }

  it("rejects a GET that never resolves with a timeout ApiError after the read timeout", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", hangingFetch());

    const outcome = fetchJson("/skills").then(
      () => null,
      (error: unknown) => error,
    );
    await vi.advanceTimersByTimeAsync(READ_TIMEOUT_MS - 1);
    let settled = false;
    void outcome.then(() => {
      settled = true;
    });
    await Promise.resolve();
    expect(settled).toBe(false);

    await vi.advanceTimersByTimeAsync(1);
    const error = await outcome;
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      code: "timeout",
      status: 0,
      message: "The server did not respond in time. Check that harness-asset-manager is still running.",
    });
  });

  it.each([
    ["POST", () => postJson("/x", {})],
    ["PUT", () => putJson("/x", {})],
    ["DELETE", () => deleteJson("/x")],
  ])("gives %s the longer write timeout", async (_method, call) => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", hangingFetch());

    const outcome = call().then(
      () => null,
      (error: unknown) => error,
    );
    await vi.advanceTimersByTimeAsync(READ_TIMEOUT_MS + 1);
    let settled = false;
    void outcome.then(() => {
      settled = true;
    });
    await Promise.resolve();
    expect(settled).toBe(false);

    await vi.advanceTimersByTimeAsync(WRITE_TIMEOUT_MS);
    expect(await outcome).toMatchObject({ code: "timeout", status: 0 });
  });

  it("honours a per-call timeout override", async () => {
    vi.useFakeTimers();
    vi.stubGlobal("fetch", hangingFetch());

    const outcome = postJson("/slow", {}, { timeoutMs: 500 }).then(
      () => null,
      (error: unknown) => error,
    );
    await vi.advanceTimersByTimeAsync(500);
    expect(await outcome).toMatchObject({ code: "timeout" });
  });

  it("clears the timer once a request succeeds", async () => {
    vi.useFakeTimers();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ ok: true }) }),
    );

    await expect(fetchJson("/ok")).resolves.toEqual({ ok: true });
    expect(vi.getTimerCount()).toBe(0);
  });

  it("maps a rejected fetch to a network_error ApiError", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    const error = await fetchJson("/skills").catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ code: "network_error", status: 0 });
    expect((error as ApiError).message).toMatch(/could not reach the server/i);
    expect((error as ApiError).message).not.toMatch(/failed to fetch/i);
  });

  it("keeps a caller abort as an abort, not a timeout", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((_url: string, init?: RequestInit) => {
        return new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () =>
            reject(new DOMException("The operation was aborted.", "AbortError")),
          );
        });
      }),
    );
    const caller = new AbortController();

    const outcome = fetchJson("/skills", { signal: caller.signal }).catch((error: unknown) => error);
    caller.abort();
    const error = await outcome;

    expect(error).not.toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ name: "AbortError" });
  });

  it("keeps a caller abort an abort even when fetch ignores the signal", async () => {
    vi.stubGlobal("fetch", hangingFetch());
    const caller = new AbortController();

    const outcome = postJson("/x", {}, { signal: caller.signal }).catch((error: unknown) => error);
    caller.abort();

    const error = await outcome;
    expect(error).not.toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ name: "AbortError" });
  });

  it("rejects immediately when the caller signal is already aborted", async () => {
    vi.stubGlobal("fetch", hangingFetch());
    const caller = new AbortController();
    caller.abort();

    const error = await fetchJson("/skills", { signal: caller.signal }).catch((caught: unknown) => caught);
    expect(error).not.toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ name: "AbortError" });
  });
});
