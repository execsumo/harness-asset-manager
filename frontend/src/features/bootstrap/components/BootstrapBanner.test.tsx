import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import * as api from "../api";
import { BootstrapBanner } from "./BootstrapBanner";

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

describe("BootstrapBanner", () => {
  it("renders nothing when plan has no linkable actions", async () => {
    vi.spyOn(api, "fetchBootstrapPlan").mockResolvedValueOnce({
      actions: [],
      linkableCount: 0,
      conflictCount: 0,
      skippedCount: 0,
      totalCount: 0,
      dismissed: false,
    });

    const { container } = renderWithClient(<BootstrapBanner />);
    // Wait a tick for query
    await vi.waitFor(() => {
      expect(container.querySelector(".bootstrap-banner")).toBeNull();
    });
  });

  it("renders nothing when plan is dismissed", async () => {
    vi.spyOn(api, "fetchBootstrapPlan").mockResolvedValueOnce({
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

    const { container } = renderWithClient(<BootstrapBanner />);
    await vi.waitFor(() => {
      expect(container.querySelector(".bootstrap-banner")).toBeNull();
    });
  });

  it("renders banner and allows dismissal", async () => {
    vi.spyOn(api, "fetchBootstrapPlan").mockResolvedValueOnce({
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
    const dismissSpy = vi.spyOn(api, "dismissBootstrap").mockResolvedValueOnce({
      ok: true,
      dismissed: true,
    });

    renderWithClient(<BootstrapBanner />);

    await screen.findByText(/New device detected:/i);
    expect(
      screen.getByText(/1 asset from your synced store are ready to bootstrap/i),
    ).toBeInTheDocument();

    const dismissBtn = screen.getByRole("button", { name: /dismiss/i });
    fireEvent.click(dismissBtn);

    await vi.waitFor(() => {
      expect(dismissSpy).toHaveBeenCalled();
    });
  });
});
