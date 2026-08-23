import { renderHook, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { SkillsWorkspaceData } from "./types";
import { useSkillWorkspaceSelection } from "./use-skill-workspace-selection";

const data = {
  summary: { managed: 1, unmanaged: 1 },
  harnessColumns: [],
  rows: [
    {
      skillRef: "local:untracked-skill",
      name: "Untracked Skill",
      displayStatus: "Unmanaged",
    },
    {
      skillRef: "shared:managed-skill",
      name: "Managed Skill",
      displayStatus: "Managed",
    },
  ],
} as unknown as SkillsWorkspaceData;

describe("useSkillWorkspaceSelection", () => {
  it("keeps an untracked detail open on the unified family page", async () => {
    const wrapper = ({ children }: { children: React.ReactNode }) => (
      <MemoryRouter initialEntries={["/skills?skill=local%3Auntracked-skill"]}>
        {children}
      </MemoryRouter>
    );
    const { result } = renderHook(() => useSkillWorkspaceSelection(data), { wrapper });

    await waitFor(() => expect(result.current.selectedSkillRef).toBe("local:untracked-skill"));
  });
});
