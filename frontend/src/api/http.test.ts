import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, fetchJson } from "./http";

describe("API errors", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
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
});
