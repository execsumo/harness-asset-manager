import { describe, expect, it, vi } from "vitest";
import type { QueryClient } from "@tanstack/react-query";

import { invalidateCapabilityQueries } from "./invalidation";

describe("capability invalidation", () => {
  it("invalidates every capability-backed app surface", async () => {
    const invalidateQueries = vi.fn().mockResolvedValue(undefined);
    const queryClient = { invalidateQueries } as unknown as QueryClient;
    const dispatch = vi.spyOn(window, "dispatchEvent");

    await invalidateCapabilityQueries(queryClient);

    expect(dispatch).toHaveBeenCalledWith(expect.objectContaining({ type: "asset-tags-changed" }));
    dispatch.mockRestore();

    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ["skills", "list"] });
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ["skills", "detail"] });
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ["skills", "source-status"] });
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ["mcp"] });
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ["settings"] });
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ["marketplace"] });
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ["slash-commands"] });
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ["hooks"] });
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ["agents"] });
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ["permissions"] });
    expect(invalidateQueries).toHaveBeenCalledWith({ queryKey: ["configs"] });
  });
});
