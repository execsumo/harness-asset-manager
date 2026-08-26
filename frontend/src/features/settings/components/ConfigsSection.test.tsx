import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { okJson } from "../../../test/fetch";
import { renderWithAppProviders } from "../../../test/render";
import { ConfigsSection } from "./ConfigsSection";

const fetchMock = vi.fn();

const CONFIGS = {
  claude: {
    capturedAt: "2026-08-26T04:00:00Z",
    revision: "a1b2c3d4",
    preferences: { model: "opus", theme: "auto" },
  },
};

describe("ConfigsSection", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("lists each captured harness with its preferences", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/api/configs/") {
        return okJson(CONFIGS);
      }
      throw new Error(`Unhandled URL ${url}`);
    });

    renderWithAppProviders(<ConfigsSection />);

    expect(await screen.findByText("claude")).toBeTruthy();
    expect(screen.getByText(/"model": "opus"/)).toBeTruthy();
  });

  it("reports drift as the named keys, not just a status", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/api/configs/") {
        return okJson(CONFIGS);
      }
      if (url === "/api/configs/claude/diff") {
        return okJson({
          state: "drifted",
          missing: ["theme"],
          extra: [],
          changed: ["model"],
        });
      }
      throw new Error(`Unhandled URL ${url}`);
    });

    renderWithAppProviders(<ConfigsSection />);

    // The diff is only requested once the row is opened, so the list view costs
    // one request regardless of how many harnesses are captured.
    const row = await screen.findByText("claude");
    const details = row.closest("details") as HTMLDetailsElement;
    details.open = true;
    fireEvent(details, new Event("toggle"));

    await waitFor(() => {
      expect(screen.getByText(/Missing: theme/)).toBeTruthy();
    });
    expect(screen.getByText(/Changed: model/)).toBeTruthy();
    // An empty bucket must not render an empty "Extra:" line.
    expect(screen.queryByText(/Extra:/)).toBeNull();
  });

  it("renders nothing to restore when no harness has been captured", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/api/configs/") {
        return okJson({});
      }
      throw new Error(`Unhandled URL ${url}`);
    });

    renderWithAppProviders(<ConfigsSection />);

    expect(await screen.findByText("No preferences synced.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Restore/ })).toBeNull();
  });
});
