import { describe, expect, it } from "vitest";
import { mergeSharedTagCounts } from "./useSharedTagCounts";

describe("mergeSharedTagCounts", () => {
  it("shows tags from other families with zero local count and deduplicates casing", () => {
    expect(mergeSharedTagCounts(
      [{ tag: "starred", count: 0, isStarred: true }, { tag: "Ops", count: 2, isStarred: false }],
      ["ops", "Research"],
    )).toEqual([
      { tag: "starred", count: 0, isStarred: true },
      { tag: "Ops", count: 2, isStarred: false },
      { tag: "Research", count: 0, isStarred: false },
    ]);
  });
});
