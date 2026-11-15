import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mergeSharedTagCounts, useSharedTagCounts } from "./useSharedTagCounts";
import { okJson } from "../../test/fetch";

afterEach(() => vi.unstubAllGlobals());

describe("useSharedTagCounts", () => {
  it("refreshes shared tags on focus without changing local counts", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(okJson({ tags: ["Initial"] }))
      .mockResolvedValueOnce(okJson({ tags: ["Initial", "Research"] }));
    vi.stubGlobal("fetch", fetchMock);
    const counts = [{ tag: "Local", count: 2, isStarred: false }];
    const { result, unmount } = renderHook(() => useSharedTagCounts(counts));
    await waitFor(() => expect(result.current.map((item) => item.tag)).toContain("Initial"));
    act(() => window.dispatchEvent(new Event("focus")));
    await waitFor(() => expect(result.current).toContainEqual({ tag: "Research", count: 0, isStarred: false }));
    expect(result.current).toContainEqual(counts[0]);
    unmount();
    act(() => window.dispatchEvent(new Event("focus")));
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

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
