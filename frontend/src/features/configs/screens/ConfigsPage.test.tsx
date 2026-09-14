import { fireEvent, screen, waitFor, within } from "@testing-library/react";
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

const SETTINGS = {
  autoAdopt: {},
  autoAdoptHarnessOptions: {},
  autoAdoptHarnesses: {},
  harnesses: [
    { harness: "claude", label: "Claude", logoKey: "claude", installed: true, managedLocation: null, supportEnabled: true },
    { harness: "cursor", label: "Cursor", logoKey: "cursor", installed: true, managedLocation: null, supportEnabled: true },
    { harness: "opencode", label: "OpenCode", logoKey: "opencode", installed: true, managedLocation: null, supportEnabled: true },
  ],
};

function respond(url: string) {
  if (url === "/api/configs/") return okJson(CONFIGS);
  if (url.startsWith("/api/settings")) return okJson(SETTINGS);
  if (url.includes("/api/asset-tags")) return okJson({});
  if (url.includes("/api/home")) return okJson({ home: "/home/dev" });
  return null;
}

describe("ConfigsPage", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      const response = respond(url);
      if (response) return response;
      throw new Error(`Unhandled URL ${url}`);
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("lists each detected harness with its status, key count, and config path", async () => {
    renderWithAppProviders(<ConfigsPage />);

    expect(await screen.findByText("Claude")).toBeTruthy();
    expect(screen.getByText("Cursor")).toBeTruthy();
    expect(screen.getByText("OpenCode")).toBeTruthy();

    // "Drifted" / "Not managed" also label summary tiles, so scope to the table.
    const table = within(screen.getByRole("table"));
    expect(table.getByText("Drifted")).toBeTruthy();
    // cursor has no record; opencode has one without a local file.
    expect(table.getByText("Not managed")).toBeTruthy();
    expect(table.getByText("Record only")).toBeTruthy();

    // Paths pass through unabbreviated here — the home dir context defaults to null.
    expect(screen.getByText("/home/dev/.claude/settings.json")).toBeTruthy();
    expect(table.getByText("2")).toBeTruthy();
  });

  it("summarises the fleet and lets a tile filter the table", async () => {
    renderWithAppProviders(<ConfigsPage />);

    const drifted = await screen.findByRole("button", { name: /Drifted/ });
    expect(within(drifted).getByText("1")).toBeTruthy();

    fireEvent.click(drifted);

    await waitFor(() => {
      expect(screen.queryByText("Cursor")).toBeNull();
    });
    expect(screen.getByText("Claude")).toBeTruthy();
  });

  it("opens the detail sheet and reports drift for a managed harness", async () => {
    renderWithAppProviders(<ConfigsPage />);

    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/api/configs/claude/diff") {
        return okJson({ state: "drifted", missing: ["theme"], extra: [], changed: ["model"] });
      }
      const response = respond(url);
      if (response) return response;
      throw new Error(`Unhandled URL ${url}`);
    });

    fireEvent.click(await screen.findByText("Claude"));

    expect(await screen.findByText("Drift detected")).toBeTruthy();
    expect(screen.getByText("Missing in file")).toBeTruthy();
    expect(screen.getByText("theme")).toBeTruthy();
    expect(screen.getByText("Changed values")).toBeTruthy();

    // An empty bucket must not render an empty "Extra in file" row.
    expect(screen.queryByText("Extra in file")).toBeNull();
  });

  it("offers to stop managing a managed harness, and posts to disable", async () => {
    const calls: string[] = [];
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (init?.method === "POST") {
        calls.push(url);
        return okJson({ status: "ok" });
      }
      if (url.endsWith("/diff")) {
        return okJson({ state: "managed", missing: [], extra: [], changed: [] });
      }
      const response = respond(url);
      if (response) return response;
      throw new Error(`Unhandled URL ${url}`);
    });

    renderWithAppProviders(<ConfigsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Stop managing" }));

    await waitFor(() => {
      expect(calls).toContain("/api/configs/claude/disable");
    });
  });

  it("manages an unmanaged harness straight from its row", async () => {
    const calls: string[] = [];
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (init?.method === "POST") {
        calls.push(url);
        return okJson({ status: "ok" });
      }
      const response = respond(url);
      if (response) return response;
      throw new Error(`Unhandled URL ${url}`);
    });

    renderWithAppProviders(<ConfigsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Manage" }));

    await waitFor(() => {
      expect(calls).toContain("/api/configs/cursor/enable");
    });
  });

  it("flags a record whose config file is absent, without assuming it is stale", async () => {
    renderWithAppProviders(<ConfigsPage />);

    fireEvent.click(await screen.findByText("OpenCode"));

    expect(await screen.findByText("Record without a local file")).toBeTruthy();
    expect(screen.getByText(/managed on another machine/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /Remove record/ })).toBeTruthy();
  });

  it("does not flag a harness that has no record at all", async () => {
    renderWithAppProviders(<ConfigsPage />);

    fireEvent.click(await screen.findByText("Cursor"));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Manage/ })).toBeTruthy();
    });
    expect(screen.queryByText("Record without a local file")).toBeNull();
  });
});
