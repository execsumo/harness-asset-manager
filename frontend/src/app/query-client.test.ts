import { describe, expect, it } from "vitest";

import { assetTagKeys } from "../components/tags/asset-tag-vocabulary";
import { ApiError } from "../api/http";
import { createAppQueryClient, shouldRetryQuery } from "./query-client";

describe("createAppQueryClient", () => {
  it("marks the cached tag vocabulary stale whenever a mutation settles", async () => {
    const client = createAppQueryClient();
    client.setQueryData(assetTagKeys.vocabulary(), ["ops"]);
    const failing = client.getMutationCache().build(client, {
      mutationFn: () => Promise.reject(new Error("nope")),
    });
    const succeeding = client.getMutationCache().build(client, {
      mutationFn: () => Promise.resolve("ok"),
    });

    await succeeding.execute(undefined);
    expect(client.getQueryState(assetTagKeys.vocabulary())?.isInvalidated).toBe(true);

    client.setQueryData(assetTagKeys.vocabulary(), ["ops"]);
    await expect(failing.execute(undefined)).rejects.toThrow("nope");
    expect(client.getQueryState(assetTagKeys.vocabulary())?.isInvalidated).toBe(true);
  });

  it("uses the shared retry rule for queries", () => {
    const client = createAppQueryClient();
    expect(client.getDefaultOptions().queries?.retry).toBe(shouldRetryQuery);
  });
});

describe("shouldRetryQuery", () => {
  it.each([
    [404, "not_found"],
    [409, "conflict"],
    [422, "validation_error"],
    [401, "unauthorized"],
  ])("never retries a %i response", (status, code) => {
    expect(shouldRetryQuery(0, new ApiError("nope", code, status))).toBe(false);
  });

  it.each([
    ["500 response", new ApiError("boom", "internal_error", 500)],
    ["503 response", new ApiError("down", "request_failed", 503)],
    ["network error", new ApiError("offline", "network_error", 0)],
    ["timeout", new ApiError("slow", "timeout", 0)],
  ])("retries a %s once", (_label, error) => {
    expect(shouldRetryQuery(0, error)).toBe(true);
    expect(shouldRetryQuery(1, error)).toBe(false);
  });

  it("retries an unexpected non-ApiError once", () => {
    expect(shouldRetryQuery(0, new Error("odd"))).toBe(true);
    expect(shouldRetryQuery(1, new Error("odd"))).toBe(false);
  });
});
