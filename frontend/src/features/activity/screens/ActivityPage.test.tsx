import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { okJson } from "../../../test/fetch";
import { renderWithAppProviders } from "../../../test/render";
import ActivityPage from "./ActivityPage";

const fetchMock = vi.fn();

describe("ActivityPage", () => {
  beforeEach(() => {
    fetchMock.mockResolvedValue(
      okJson({
        events: [
          {
            version: 1,
            timestamp: "2026-08-07T11:00:00Z",
            family: "slash_commands",
            operation: "sync_command",
            parameters: { name: "review", harnesses: ["claude", "codex"] },
            targetPaths: ["/home/dev/.claude/commands/review.md"],
            outcome: "partial",
          },
        ],
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  it("renders recent events and discloses safe parameters and changed paths", async () => {
    renderWithAppProviders(<ActivityPage />);

    expect(await screen.findByRole("heading", { name: "Activity" })).toBeInTheDocument();
    expect(await screen.findByText("Slash commands")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Sync command" })).toBeInTheDocument();
    expect(screen.getByText("Partial")).toBeInTheDocument();
    expect(screen.getAllByText("review")).toHaveLength(2);

    fireEvent.click(screen.getByText("Details"));

    expect(screen.getByText("claude, codex")).toBeInTheDocument();
    expect(screen.getByText("/home/dev/.claude/commands/review.md")).toBeInTheDocument();
    expect(screen.getByText("Changed paths")).toBeInTheDocument();
  });

  it("shows an empty state and can refresh", async () => {
    fetchMock.mockResolvedValue(okJson({ events: [] }));
    renderWithAppProviders(<ActivityPage />);

    expect(await screen.findByRole("heading", { name: "No activity yet" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Refresh" }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
  });

  it("shows an error without also claiming the journal is empty", async () => {
    fetchMock.mockRejectedValue(new Error("offline"));
    renderWithAppProviders(<ActivityPage />);

    expect(await screen.findByText("Unable to load recent activity.")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "No activity yet" })).not.toBeInTheDocument();
  });
});
