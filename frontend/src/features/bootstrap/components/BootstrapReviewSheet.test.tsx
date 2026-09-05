import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import * as api from "../api";
import type { BootstrapPlanDto } from "../types";
import { BootstrapReviewSheet } from "./BootstrapReviewSheet";

function renderWithClient(ui: ReactNode) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

const mockPlan: BootstrapPlanDto = {
  actions: [
    {
      family: "skills",
      ref: "shared:my-skill",
      displayName: "My Skill",
      harness: "claude",
      action: "link",
      targetPath: "/Users/alice/.claude/skills/my-skill",
    },
    {
      family: "agents",
      ref: "reviewer",
      displayName: "Reviewer",
      harness: "codex",
      action: "conflict",
      targetPath: "/Users/alice/.codex/agents/reviewer.md",
      reason: "target-occupied",
      detail: "collision",
    },
  ],
  linkableCount: 1,
  conflictCount: 1,
  skippedCount: 0,
  totalCount: 2,
  dismissed: false,
};

describe("BootstrapReviewSheet", () => {
  it("renders grouped actions with link checked and conflict unchecked", () => {
    renderWithClient(
      <BootstrapReviewSheet
        open={true}
        onOpenChange={vi.fn()}
        plan={mockPlan}
      />,
    );

    expect(screen.getByText("Skills (1)")).toBeInTheDocument();
    expect(screen.getByText("Agents (1)")).toBeInTheDocument();
    expect(screen.getByText("My Skill")).toBeInTheDocument();
    expect(screen.getByText("Reviewer")).toBeInTheDocument();
    expect(screen.getByText("Conflict")).toBeInTheDocument();

    const checkboxes = screen.getAllByRole("checkbox") as HTMLInputElement[];
    expect(checkboxes).toHaveLength(2);
    // First (link) is checked, second (conflict) is unchecked
    expect(checkboxes[0].checked).toBe(true);
    expect(checkboxes[1].checked).toBe(false);

    expect(screen.getByText("1 of 2 selected")).toBeInTheDocument();
  });

  it("applies selected items when clicking Bootstrap Selected", async () => {
    const applySpy = vi.spyOn(api, "applyBootstrap").mockResolvedValueOnce({
      results: [
        {
          family: "skills",
          ref: "shared:my-skill",
          harness: "claude",
          status: "applied",
          target: "/Users/alice/.claude/skills/my-skill",
        },
      ],
      appliedCount: 1,
      failedCount: 0,
    });

    renderWithClient(
      <BootstrapReviewSheet
        open={true}
        onOpenChange={vi.fn()}
        plan={mockPlan}
      />,
    );

    const bootstrapBtn = screen.getByRole("button", { name: /bootstrap selected/i });
    fireEvent.click(bootstrapBtn);

    await vi.waitFor(() => {
      expect(applySpy).toHaveBeenCalledWith(
        [
          expect.objectContaining({
            family: "skills",
            ref: "shared:my-skill",
            harness: "claude",
          }),
        ],
        false,
      );
    });

    expect(await screen.findByText(/✓ Applied/i)).toBeInTheDocument();
  });
});
