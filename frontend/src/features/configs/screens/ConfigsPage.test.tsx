import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { okJson } from "../../../test/fetch";
import { renderWithAppProviders } from "../../../test/render";
import ConfigsPage from "./ConfigsPage";

const fetchMock = vi.fn();

const CONFIGS = {
  claude: {
    managed: true,
    keyCount: 2,
    driftState: "drifted",
    sourceFile: "/home/dev/.claude/settings.json",
    capturedAt: "2026-08-26T04:00:00Z",
    preferences: { model: "opus", theme: "auto" },
  },
  cursor: {
    managed: false,
    keyCount: 0,
    driftState: "—",
    sourceFile: "/home/dev/.cursor/settings.json",
    capturedAt: null,
    preferences: {},
  }
};

describe("ConfigsPage", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    
    // Tag mock
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/api/configs/") {
        return okJson(CONFIGS);
      }
      if (url.includes("/api/asset-tags")) {
        return okJson({});
      }
      throw new Error(`Unhandled URL ${url}`);
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("lists each captured harness with its preferences", async () => {
    renderWithAppProviders(<ConfigsPage />);

    expect(await screen.findByText("claude")).toBeTruthy();
    expect(await screen.findByText("cursor")).toBeTruthy();
    
    // Check table headers and content
    expect(screen.getByText("Managed")).toBeTruthy();
    expect(screen.getByText("Not managed")).toBeTruthy();
    
    expect(screen.getByText("2")).toBeTruthy();
    expect(screen.getByText("0")).toBeTruthy();
    
    expect(screen.getByText("drifted")).toBeTruthy();
    
    // The details drawer opens on click
    fireEvent.click(screen.getByText("claude"));
    
    // Now diff should be fetched, wait for the mock
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
      if (url.includes("/api/asset-tags")) {
        return okJson({});
      }
      throw new Error(`Unhandled URL ${url}`);
    });

    await waitFor(() => {
      expect(screen.getByText(/Missing in file: theme/)).toBeTruthy();
    });
    expect(screen.getByText(/Changed values: model/)).toBeTruthy();
    
    // An empty bucket must not render an empty "Extra:" line.
    expect(screen.queryByText(/Extra in file:/)).toBeNull();
  });

  it("renders disabled state actions properly", async () => {
    renderWithAppProviders(<ConfigsPage />);

    expect(await screen.findByText("cursor")).toBeTruthy();
    
    fireEvent.click(screen.getByText("cursor"));
    
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Enable/ })).toBeTruthy();
    });
  });
});
