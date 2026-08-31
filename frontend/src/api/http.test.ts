import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, authHeaders, deleteJson, fetchJson, getApiToken, postJson, putJson } from "./http";

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
    document.head.innerHTML = "";
  });

  it("reads token from meta tag when available", () => {
    const meta = document.createElement("meta");
    meta.name = "ham-api-token";
    meta.content = "test-token-12345";
    document.head.appendChild(meta);

    expect(getApiToken()).toBe("test-token-12345");
    expect(authHeaders()).toEqual({ Authorization: "Bearer test-token-12345" });
    expect(authHeaders({ "Content-Type": "application/json" })).toEqual({
      "Content-Type": "application/json",
      Authorization: "Bearer test-token-12345",
    });
  });

  it("attaches Authorization header to all HTTP helpers", async () => {
    const meta = document.createElement("meta");
    meta.name = "ham-api-token";
    meta.content = "test-token-abc";
    document.head.appendChild(meta);

    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ok: true }),
    });
    vi.stubGlobal("fetch", mockFetch);

    await fetchJson("/test-get");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/test-get"),
      expect.objectContaining({
        headers: { Authorization: "Bearer test-token-abc" },
      }),
    );

    await postJson("/test-post", { data: 1 });
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/test-post"),
      expect.objectContaining({
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer test-token-abc",
        },
        body: JSON.stringify({ data: 1 }),
      }),
    );

    await putJson("/test-put", { data: 2 });
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/test-put"),
      expect.objectContaining({
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: "Bearer test-token-abc",
        },
        body: JSON.stringify({ data: 2 }),
      }),
    );

    await deleteJson("/test-delete");
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining("/test-delete"),
      expect.objectContaining({
        method: "DELETE",
        headers: { Authorization: "Bearer test-token-abc" },
      }),
    );
  });
});
