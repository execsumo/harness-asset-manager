import { act, renderHook } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SkillsWorkspaceData } from "./types";

const hoisted = vi.hoisted(() => {
  const setHarnessesCalls: Array<{ skillRef: string; target: "enabled" | "disabled" }> = [];
  const setTagsCalls: Array<{ skillRef: string; tags: string[] }> = [];
  const failFor = new Set<string>();
  const failTagsFor = new Set<string>();
  let nextResponse: { succeeded: string[]; failed: Array<{ harness: string; error: string }> } | null = null;
  return {
    setHarnessesCalls,
    setTagsCalls,
    failFor,
    failTagsFor,
    setNextResponse(value: typeof nextResponse) {
      nextResponse = value;
    },
    takeNextResponse() {
      const value = nextResponse;
      nextResponse = null;
      return value;
    },
  };
});

const testData: SkillsWorkspaceData = {
  summary: { managed: 2, unmanaged: 0 },
  harnessColumns: [
    { harness: "codex", label: "Codex", installed: true },
    { harness: "cursor", label: "Cursor", installed: true },
    { harness: "claude", label: "Claude", installed: true },
  ],
  rows: [
    {
      skillRef: "shared:test-skill",
      name: "Test Skill",
      description: "",
      displayStatus: "Managed",
      tags: ["starred", "frontend"],
      actions: { canManage: false, canStopManaging: true, canDelete: false },
      cells: [
        { harness: "codex", label: "Codex", state: "enabled", interactive: true },
        { harness: "cursor", label: "Cursor", state: "disabled", interactive: true },
        { harness: "claude", label: "Claude", state: "empty", interactive: false },
      ],
    },
    {
      skillRef: "shared:other-skill",
      name: "Other Skill",
      description: "",
      displayStatus: "Managed",
      tags: ["backend"],
      actions: { canManage: false, canStopManaging: true, canDelete: false },
      cells: [
        { harness: "codex", label: "Codex", state: "enabled", interactive: true },
        { harness: "cursor", label: "Cursor", state: "disabled", interactive: true },
        { harness: "claude", label: "Claude", state: "empty", interactive: false },
      ],
    },
  ],
} as unknown as SkillsWorkspaceData;

vi.mock("../api/queries", () => ({
  useSkillsListQuery: () => ({
    data: testData,
    isPending: false,
    error: null,
  }),
  useToggleSkillMutation: () => ({
    mutateAsync: vi.fn(),
  }),
  useSetSkillHarnessesMutation: () => ({
    mutateAsync: async (vars: { skillRef: string; target: "enabled" | "disabled" }) => {
      hoisted.setHarnessesCalls.push(vars);
      const override = hoisted.takeNextResponse();
      if (override) {
        return { ok: override.failed.length === 0, ...override };
      }
      // Default behavior: mirror the current row's cells to derive who would flip.
      const row = testData.rows.find((r) => r.skillRef === vars.skillRef)!;
      const succeeded: string[] = [];
      const failed: Array<{ harness: string; error: string }> = [];
      for (const cell of row.cells) {
        if (!cell.interactive || cell.state === vars.target) continue;
        if (hoisted.failFor.has(cell.harness)) {
          failed.push({ harness: cell.harness, error: `${cell.harness} toggle failed` });
        } else {
          succeeded.push(cell.harness);
        }
      }
      return { ok: failed.length === 0, succeeded, failed };
    },
  }),
  useManageSkillMutation: () => ({ mutateAsync: vi.fn() }),
  useManageAllSkillsMutation: () => ({ mutateAsync: vi.fn() }),
  useSetSkillTagsMutation: () => ({
    mutateAsync: async (vars: { skillRef: string; tags: string[] }) => {
      if (hoisted.failTagsFor.has(vars.skillRef)) {
        throw new Error(`Failed tags for ${vars.skillRef}`);
      }
      hoisted.setTagsCalls.push(vars);
      return {};
    },
  }),
  useUpdateSkillMutation: () => ({ mutateAsync: vi.fn() }),
  useUnmanageSkillMutation: () => ({ mutateAsync: vi.fn() }),
  useDeleteSkillMutation: () => ({ mutateAsync: vi.fn() }),
}));

import { useSkillsWorkspaceController } from "./use-skills-workspace-controller";

function wrapper({ children }: { children: React.ReactNode }) {
  const client = new QueryClient();
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/skills/use"]}>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe("useSkillsWorkspaceController > onSetSkillAllHarnesses", () => {
  beforeEach(() => {
    hoisted.setHarnessesCalls.length = 0;
    hoisted.failFor.clear();
    hoisted.setNextResponse(null);
  });

  it("dispatches a single bulk request with the target and returns the server's succeeded list", async () => {
    const { result } = renderHook(() => useSkillsWorkspaceController(), { wrapper });

    let outcome: Awaited<ReturnType<typeof result.current.context.onSetSkillAllHarnesses>> | undefined;
    await act(async () => {
      outcome = await result.current.context.onSetSkillAllHarnesses("shared:test-skill", "enabled");
    });

    expect(hoisted.setHarnessesCalls).toEqual([
      { skillRef: "shared:test-skill", target: "enabled" },
    ]);
    expect(outcome?.succeeded).toEqual(["cursor"]);
    expect(outcome?.failed).toEqual([]);
    expect(result.current.actionErrorMessage).toBe("");
  });

  it("surfaces partial failures from the server and sets an error message", async () => {
    hoisted.failFor.add("cursor");
    const { result } = renderHook(() => useSkillsWorkspaceController(), { wrapper });

    let outcome: Awaited<ReturnType<typeof result.current.context.onSetSkillAllHarnesses>> | undefined;
    await act(async () => {
      outcome = await result.current.context.onSetSkillAllHarnesses("shared:test-skill", "enabled");
    });

    expect(outcome?.succeeded).toEqual([]);
    expect(outcome?.failed).toHaveLength(1);
    expect(outcome?.failed[0]?.harness).toBe("cursor");
    expect(result.current.actionErrorMessage).toContain("cursor");
  });

  it("issues the bulk call for the opposite direction too", async () => {
    const { result } = renderHook(() => useSkillsWorkspaceController(), { wrapper });

    let outcome: Awaited<ReturnType<typeof result.current.context.onSetSkillAllHarnesses>> | undefined;
    await act(async () => {
      outcome = await result.current.context.onSetSkillAllHarnesses("shared:test-skill", "disabled");
    });

    expect(hoisted.setHarnessesCalls).toEqual([
      { skillRef: "shared:test-skill", target: "disabled" },
    ]);
    expect(outcome?.succeeded).toEqual(["codex"]);
  });
});

describe("useSkillsWorkspaceController > onMultiSelectTag", () => {
  beforeEach(() => {
    hoisted.setTagsCalls.length = 0;
    hoisted.failTagsFor.clear();
  });

  it("merges new tags into existing tags case-insensitively and preserves casing", async () => {
    const { result } = renderHook(() => useSkillsWorkspaceController(), { wrapper });

    // Select both skills
    act(() => {
      result.current.context.onToggleMultiSelect("shared:test-skill");
      result.current.context.onToggleMultiSelect("shared:other-skill");
    });

    expect(result.current.context.multiSelectedRefs.size).toBe(2);

    // Apply tags ["frontend", "analytics", "v2"]
    await act(async () => {
      await result.current.context.onMultiSelectTag(["FRONTEND", "analytics", "v2"]);
    });

    // test-skill had ["starred", "frontend"]. "FRONTEND" was already present, so it gets ["starred", "frontend", "analytics", "v2"].
    // other-skill had ["backend"]. It gets ["backend", "FRONTEND", "analytics", "v2"].
    expect(hoisted.setTagsCalls).toEqual([
      {
        skillRef: "shared:test-skill",
        tags: ["starred", "frontend", "analytics", "v2"],
      },
      {
        skillRef: "shared:other-skill",
        tags: ["backend", "FRONTEND", "analytics", "v2"],
      },
    ]);

    // Multi-selection should be cleared
    expect(result.current.context.multiSelectedRefs.size).toBe(0);
    expect(result.current.actionErrorMessage).toBe("");
  });

  it("skips assets silently if they already have all requested tags", async () => {
    const { result } = renderHook(() => useSkillsWorkspaceController(), { wrapper });

    act(() => {
      result.current.context.onToggleMultiSelect("shared:test-skill");
    });

    // test-skill already has "frontend" and "starred"
    await act(async () => {
      await result.current.context.onMultiSelectTag(["frontend", "STARRED"]);
    });

    expect(hoisted.setTagsCalls).toHaveLength(0);
    expect(result.current.context.multiSelectedRefs.size).toBe(0);
  });

  it("continues on per-ref failure and surfaces error summary listing failed refs", async () => {
    hoisted.failTagsFor.add("shared:test-skill");

    const { result } = renderHook(() => useSkillsWorkspaceController(), { wrapper });

    act(() => {
      result.current.context.onToggleMultiSelect("shared:test-skill");
      result.current.context.onToggleMultiSelect("shared:other-skill");
    });

    await act(async () => {
      await result.current.context.onMultiSelectTag(["new-tag"]);
    });

    // other-skill still succeeded
    expect(hoisted.setTagsCalls).toEqual([
      {
        skillRef: "shared:other-skill",
        tags: ["backend", "new-tag"],
      },
    ]);

    expect(result.current.actionErrorMessage).toContain("shared:test-skill");
    expect(result.current.context.multiSelectedRefs.size).toBe(0);
  });
});
