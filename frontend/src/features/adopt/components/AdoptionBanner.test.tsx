import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import * as api from "../api";
import { AdoptionBanner } from "./AdoptionBanner";

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

describe("AdoptionBanner", () => {
  it("renders nothing when plan has no linkable actions", async () => {
    vi.spyOn(api, "fetchAdoptionPlan").mockResolvedValueOnce({
      actions: [],
      linkableCount: 0,
      conflictCount: 0,
      skippedCount: 0,
      totalCount: 0,
      dismissed: false,
    });

    const { container } = renderWithClient(<AdoptionBanner />);
    // Wait a tick for query
    await vi.waitFor(() => {
      expect(container.querySelector(".adoption-banner")).toBeNull();
    });
  });

  it("renders nothing when plan is dismissed", async () => {
    vi.spyOn(api, "fetchAdoptionPlan").mockResolvedValueOnce({
      actions: [
        {
          family: "skills",
          ref: "shared:my-skill",
          displayName: "My Skill",
          harness: "claude",
          action: "link",
          targetPath: "/Users/alice/.claude/skills/my-skill",
        },
      ],
      linkableCount: 1,
      conflictCount: 0,
      skippedCount: 0,
      totalCount: 1,
      dismissed: true,
    });

    const { container } = renderWithClient(<AdoptionBanner />);
    await vi.waitFor(() => {
      expect(container.querySelector(".adoption-banner")).toBeNull();
    });
  });

  it("renders banner and allows dismissal", async () => {
    vi.spyOn(api, "fetchAdoptionPlan").mockResolvedValueOnce({
      actions: [
        {
          family: "skills",
          ref: "shared:my-skill",
          displayName: "My Skill",
          harness: "claude",
          action: "link",
          targetPath: "/Users/alice/.claude/skills/my-skill",
        },
      ],
      linkableCount: 1,
      conflictCount: 0,
      skippedCount: 0,
      totalCount: 1,
      dismissed: false,
    });
    const dismissSpy = vi.spyOn(api, "dismissAdoption").mockResolvedValueOnce({
      ok: true,
      dismissed: true,
    });

    renderWithClient(<AdoptionBanner />);

    await screen.findByText(/New device detected:/i);
    expect(
      screen.getByText(/1 asset from your synced store can be adopted/i),
    ).toBeInTheDocument();

    const dismissBtn = screen.getByRole("button", { name: /dismiss/i });
    fireEvent.click(dismissBtn);

    await vi.waitFor(() => {
      expect(dismissSpy).toHaveBeenCalled();
    });
  });
});
