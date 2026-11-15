import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { mergeSharedTagCounts, useSharedTagCounts } from "./useSharedTagCounts";
import { okJson } from "../../test/fetch";
import { extractAssetTagCounts, matchesAssetTags } from "./tag-counts";

afterEach(() => vi.unstubAllGlobals());

describe("useSharedTagCounts", () => {
  it("retries a failed vocabulary request without requiring focus", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce(okJson({ tags: ["Recovered"] }));
    vi.stubGlobal("fetch", fetchMock);
    const counts: Array<{ tag: string; count: number; isStarred: boolean }> = [];
    const { result, unmount } = renderHook(() => useSharedTagCounts(counts));
    await act(async () => { await Promise.resolve(); });
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(result.current).toContainEqual({ tag: "Recovered", count: 0, isStarred: false });
    unmount();
    vi.useRealTimers();
  });

  it("treats a malformed vocabulary response as empty instead of crashing", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(okJson({}))
      .mockResolvedValueOnce(okJson({ tags: ["Valid", 7, null] }));
    vi.stubGlobal("fetch", fetchMock);
    const counts = [{ tag: "Local", count: 1, isStarred: false }];
    const { result, unmount } = renderHook(() => useSharedTagCounts(counts));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    expect(result.current).toEqual(counts);
    act(() => window.dispatchEvent(new Event("focus")));
    await waitFor(() => expect(result.current.map((item) => item.tag)).toEqual(["Local", "Valid"]));
    unmount();
  });

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
  it("shares Unicode case-folded identities while retaining family counts", () => {
    const items = [{ tags: ["Straße"] }, { tags: ["STRASSE"] }];
    const counts = extractAssetTagCounts(items);
    expect(mergeSharedTagCounts(counts, ["strasse"])).toEqual([
      { tag: "starred", count: 0, isStarred: true },
      { tag: "Straße", count: 2, isStarred: false },
    ]);
    expect(matchesAssetTags(items[0], ["STRASSE"])).toBe(true);
    expect(matchesAssetTags({ tags: ["ς"] }, ["Σ"])).toBe(true);
  });
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
