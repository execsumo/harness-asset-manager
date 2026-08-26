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
    hasRecord: true,
  },
  cursor: {
    managed: false,
    keyCount: 0,
    driftState: "—",
    sourceFile: "/home/dev/.cursor/settings.json",
    capturedAt: null,
    preferences: {},
    hasRecord: false,
  },
  // Managed on another machine, or left behind: a record with no local file.
  opencode: {
    managed: false,
    keyCount: 0,
    driftState: "—",
    sourceFile: "/home/dev/.opencode/opencode.jsonc",
    capturedAt: "2026-08-26T04:00:00Z",
    preferences: {},
    hasRecord: true,
  },
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

  it("offers to stop managing a managed harness, and posts to disable", async () => {
    const calls: string[] = [];
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (init?.method === "POST") {
        calls.push(url);
        return okJson({ status: "ok" });
      }
      if (url === "/api/configs/") return okJson(CONFIGS);
      if (url.includes("/api/asset-tags")) return okJson({});
      if (url.endsWith("/diff")) return okJson({ state: "managed", missing: [], extra: [], changed: [] });
      throw new Error(`Unhandled URL ${url}`);
    });

    renderWithAppProviders(<ConfigsPage />);
    fireEvent.click(await screen.findByText("claude"));

    const stop = await screen.findByRole("button", { name: /Stop Managing/ });
    fireEvent.click(stop);

    await waitFor(() => {
      expect(calls).toContain("/api/configs/claude/disable");
    });
  });

  it("flags a record whose config file is absent, without assuming it is stale", async () => {
    renderWithAppProviders(<ConfigsPage />);

    // opencode: not managed here, but a record exists — it may be live on another
    // machine, so the notice must say so rather than offering a silent cleanup.
    fireEvent.click(await screen.findByText("opencode"));

    expect(await screen.findByText(/Stale Record Detected/)).toBeTruthy();
    expect(screen.getByText(/managed on another machine/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /Remove Record/ })).toBeTruthy();
  });

  it("does not flag a harness that has no record at all", async () => {
    renderWithAppProviders(<ConfigsPage />);

    // cursor has no record, so there is nothing to clean up — only Enable.
    fireEvent.click(await screen.findByText("cursor"));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Enable/ })).toBeTruthy();
    });
    expect(screen.queryByText(/Stale Record Detected/)).toBeNull();
  });
});
