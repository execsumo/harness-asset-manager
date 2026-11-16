import { describe, expect, it } from "vitest";

import { assetTagKeys } from "../components/tags/asset-tag-vocabulary";
import { createAppQueryClient } from "./query-client";

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

  it("keeps the app's single query retry default", () => {
    const client = createAppQueryClient();
    expect(client.getDefaultOptions().queries?.retry).toBe(1);
  });
});
