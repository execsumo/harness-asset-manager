import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";
import { optimisticTags } from "./optimistic-tags";

describe("optimisticTags", () => {
  it("updates all list variants and detail, and rolls back only the changed asset", async () => {
    const client = new QueryClient();
    const key = ["assets", "list", true];
    client.setQueryData(key, { entries: [{ id: "a", tags: [] }, { id: "b", tags: [] }] });
    client.setQueryData(["assets", "list", false], { entries: [{ id: "a", tags: [] }] });
    client.setQueryData(["assets", "detail", "a"], { id: "a", tags: [] });
    const shape = { prefix: ["assets"], collections: ["entries"], identity: "id", detail: ["assets", "detail", "a"] };
    const rollback = await optimisticTags(client, shape, "a", ["starred"]);
    expect(client.getQueryData(key)).toEqual({ entries: [{ id: "a", tags: ["starred"] }, { id: "b", tags: [] }] });
    expect(client.getQueryData(["assets", "detail", "a"])).toEqual({ id: "a", tags: ["starred"] });
    await optimisticTags(client, shape, "b", ["starred"]);
    rollback();
    expect(client.getQueryData(key)).toEqual({ entries: [{ id: "a", tags: [] }, { id: "b", tags: ["starred"] }] });
    expect(client.getQueryData(["assets", "list", false])).toEqual({ entries: [{ id: "a", tags: [] }] });
  });

  it("removes a star immediately and restores it after a failure", async () => {
    const client = new QueryClient();
    const key = ["assets", "list"];
    client.setQueryData(key, { rows: [{ ref: "a", tags: ["starred", "work"] }] });
    const rollback = await optimisticTags(client, { prefix: ["assets"], collections: ["rows"], identity: "ref" }, "a", ["work"]);
    expect(client.getQueryData(key)).toEqual({ rows: [{ ref: "a", tags: ["work"] }] });
    rollback();
    expect(client.getQueryData(key)).toEqual({ rows: [{ ref: "a", tags: ["starred", "work"] }] });
  });

  it("handles config dictionaries and review references", async () => {
    const client = new QueryClient();
    client.setQueryData(["configs", "list"], { codex: { tags: [] } });
    client.setQueryData(["commands", "list"], { reviewCommands: [{ name: "x", reviewRef: "review:x", tags: [] }] });
    const rollback = await optimisticTags(client, { prefix: ["configs"], identity: "harness", config: true }, "codex", ["starred"]);
    await optimisticTags(client, { prefix: ["commands"], identity: "name", collections: ["reviewCommands"] }, "review:x", ["starred"]);
    expect(client.getQueryData(["commands", "list"])).toEqual({ reviewCommands: [{ name: "x", reviewRef: "review:x", tags: ["starred"] }] });
    rollback();
    expect(client.getQueryData(["configs", "list"])).toEqual({ codex: { tags: [] } });
  });
});
