import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const hoisted = vi.hoisted(() => ({
  setHarnessesMutate: vi.fn(),
  enableMutate: vi.fn(),
  availabilityMutate: vi.fn(),
  setTagsMutate: vi.fn(),
}));

vi.mock("../api/management-queries", () => ({
  useMcpInventoryQuery: () => ({
    data: {
      columns: [],
      entries: [
        { name: "server-a", kind: "managed", tags: ["core"], mcpStatus: { kind: "running" } },
        { name: "server-b", kind: "managed", tags: ["starred", "database"], mcpStatus: { kind: "running" } },
      ],
    },
    isPending: false,
    error: null,
  }),
  useMcpNeedsReviewByServerQuery: () => ({
    data: { harnesses: [], servers: [], issues: [] },
    isPending: false,
    error: null,
  }),
  useSetMcpServerHarnessesMutation: () => ({
    mutateAsync: hoisted.setHarnessesMutate,
  }),
  useEnableMcpServerMutation: () => ({
    mutateAsync: hoisted.enableMutate,
  }),
  useCheckMcpServerAvailabilityMutation: () => ({
    mutateAsync: hoisted.availabilityMutate,
  }),
  useSetMcpServerTagsMutation: () => ({
    mutateAsync: hoisted.setTagsMutate,
  }),
  useDisableMcpServerMutation: () => ({ mutateAsync: vi.fn() }),
  useUninstallMcpServerMutation: () => ({ mutateAsync: vi.fn() }),
  useAdoptMcpServerMutation: () => ({ mutateAsync: vi.fn() }),
  useReconcileMcpServerMutation: () => ({ mutateAsync: vi.fn() }),
}));

import { useMcpManagementController } from "./use-mcp-management-controller";

describe("useMcpManagementController availability refresh", () => {
  beforeEach(() => {
    hoisted.setHarnessesMutate.mockReset();
    hoisted.enableMutate.mockReset();
    hoisted.availabilityMutate.mockReset();
    hoisted.setHarnessesMutate.mockResolvedValue({ ok: true, succeeded: ["cursor"], failed: [] });
    hoisted.enableMutate.mockResolvedValue({ ok: true });
    hoisted.availabilityMutate.mockReturnValue(new Promise(() => undefined));
  });

  it("does not keep enable-all pending while availability check is still running", async () => {
    const { result } = renderHook(() => useMcpManagementController());
    let settled = false;

    await act(async () => {
      void result.current.handleSetServerHarnesses("exa", "enabled").then(() => {
        settled = true;
      });
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(hoisted.setHarnessesMutate).toHaveBeenCalledWith({ name: "exa", target: "enabled" });
    expect(hoisted.availabilityMutate).toHaveBeenCalledWith("exa");
    expect(settled).toBe(true);
  });

  it("does not keep single-harness enable pending while availability check is still running", async () => {
    const { result } = renderHook(() => useMcpManagementController());
    let settled = false;

    await act(async () => {
      void result.current.handleEnableInHarness("exa", "cursor").then(() => {
        settled = true;
      });
      await new Promise((resolve) => setTimeout(resolve, 0));
    });

    expect(hoisted.enableMutate).toHaveBeenCalledWith({ name: "exa", harness: "cursor" });
    expect(hoisted.availabilityMutate).toHaveBeenCalledWith("exa");
    expect(settled).toBe(true);
  });
});

describe("useMcpManagementController handleMultiSelectTag", () => {
  beforeEach(() => {
    hoisted.setTagsMutate.mockReset();
    hoisted.setTagsMutate.mockResolvedValue({});
  });

  it("merges tags into selected managed servers and clears selection", async () => {
    const { result } = renderHook(() => useMcpManagementController());

    act(() => {
      result.current.handleToggleMultiSelect("server-a");
      result.current.handleToggleMultiSelect("server-b");
    });

    expect(result.current.multiSelectedNames.size).toBe(2);

    await act(async () => {
      await result.current.handleMultiSelectTag(["analytics", "database"]);
    });

    // server-a gets ["core", "analytics", "database"]
    // server-b already had "database", so gets ["starred", "database", "analytics"]
    expect(hoisted.setTagsMutate).toHaveBeenCalledWith({
      name: "server-a",
      tags: ["core", "analytics", "database"],
    });
    expect(hoisted.setTagsMutate).toHaveBeenCalledWith({
      name: "server-b",
      tags: ["starred", "database", "analytics"],
    });

    expect(result.current.multiSelectedNames.size).toBe(0);
    expect(result.current.actionErrorMessage).toBe("");
  });

  it("skips server if all tags are already present", async () => {
    const { result } = renderHook(() => useMcpManagementController());

    act(() => {
      result.current.handleToggleMultiSelect("server-a");
    });

    await act(async () => {
      await result.current.handleMultiSelectTag(["core"]);
    });

    expect(hoisted.setTagsMutate).not.toHaveBeenCalled();
    expect(result.current.multiSelectedNames.size).toBe(0);
  });

  it("handles per-server failures and sets error message", async () => {
    hoisted.setTagsMutate.mockImplementation(async ({ name }: { name: string }) => {
      if (name === "server-a") throw new Error("Permission denied");
      return {};
    });

    const { result } = renderHook(() => useMcpManagementController());

    act(() => {
      result.current.handleToggleMultiSelect("server-a");
      result.current.handleToggleMultiSelect("server-b");
    });

    await act(async () => {
      await result.current.handleMultiSelectTag(["new-tag"]);
    });

    expect(hoisted.setTagsMutate).toHaveBeenCalledWith({
      name: "server-b",
      tags: ["starred", "database", "new-tag"],
    });

    expect(result.current.actionErrorMessage).toContain("server-a");
    expect(result.current.multiSelectedNames.size).toBe(0);
  });
});

describe("useMcpManagementController handleMultiSelectStar", () => {
  beforeEach(() => {
    hoisted.setTagsMutate.mockReset();
    hoisted.setTagsMutate.mockResolvedValue({});
  });

  it("adds starred tag to unstarred servers and skips already starred ones", async () => {
    const { result } = renderHook(() => useMcpManagementController());

    act(() => {
      result.current.handleToggleMultiSelect("server-a");
      result.current.handleToggleMultiSelect("server-b");
    });

    expect(result.current.multiSelectedNames.size).toBe(2);

    await act(async () => {
      await result.current.handleMultiSelectStar();
    });

    // server-a has tags: ["core"], so gets ["starred", "core"]
    expect(hoisted.setTagsMutate).toHaveBeenCalledWith({
      name: "server-a",
      tags: ["starred", "core"],
    });

    // server-b already had "starred", so should not have a second mutate call for it
    expect(hoisted.setTagsMutate).toHaveBeenCalledTimes(1);
    expect(result.current.multiSelectedNames.size).toBe(0);
  });

  it("reports failures and preserves the selection for retry", async () => {
    hoisted.setTagsMutate.mockRejectedValue(new Error("Permission denied"));
    const { result } = renderHook(() => useMcpManagementController());

    act(() => {
      result.current.handleToggleMultiSelect("server-a");
    });

    await act(async () => {
      await result.current.handleMultiSelectStar();
    });

    expect(result.current.actionErrorMessage).toContain("server-a: Permission denied");
    expect(result.current.multiSelectedNames).toEqual(new Set(["server-a"]));
  });
});
