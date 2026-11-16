import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { WRITE_TIMEOUT_MS } from "../api/http";
import ConfigsPage from "../features/configs/screens/ConfigsPage";
import { createRouteFetchMock, errorJson, okJson } from "./fetch";
import { renderWithAppProviders } from "./render";

type Outcome = "ok" | "hang" | "http-500" | "offline";

const fetchMock = vi.fn();

// A small stateful backend: enable and disable really change what the list returns.
const server = {
  managed: { claude: true, cursor: false },
  outcome: { enable: "ok" as Outcome, disable: "ok" as Outcome, restore: "ok" as Outcome },
  posts: [] as string[],
};

function configsPayload() {
  const entry = (harness: "claude" | "cursor") => ({
    managed: server.managed[harness],
    keyCount: server.managed[harness] ? 2 : 0,
    driftState: server.managed[harness] ? "managed" : "—",
    sourceFile: `/home/dev/.${harness}/settings.json`,
    capturedAt: server.managed[harness] ? "2026-08-26T04:00:00Z" : null,
    preferences: server.managed[harness] ? { model: "opus" } : {},
    hasRecord: server.managed[harness],
  });
  return { claude: entry("claude"), cursor: entry("cursor") };
}

const SETTINGS = {
  autoAdopt: {},
  autoAdoptHarnessOptions: {},
  autoAdoptHarnesses: {},
  harnesses: [
    { harness: "claude", label: "Claude", logoKey: "claude", installed: true, managedLocation: null, supportEnabled: true },
    { harness: "cursor", label: "Cursor", logoKey: "cursor", installed: true, managedLocation: null, supportEnabled: true },
  ],
};

/** A POST that follows the scripted outcome; a hang never resolves and ignores the abort signal. */
function action(kind: keyof typeof server.outcome, apply: () => void) {
  return (url: string) => {
    server.posts.push(url);
    const outcome = server.outcome[kind];
    if (outcome === "hang") return new Promise<Response>(() => undefined);
    if (outcome === "offline") return Promise.reject(new TypeError("Failed to fetch"));
    if (outcome === "http-500") return errorJson("backend exploded", { status: 500 });
    apply();
    return okJson({ status: "ok" });
  };
}

function installServer() {
  fetchMock.mockImplementation(
    createRouteFetchMock([
      { match: "/api/configs/cursor/enable", response: action("enable", () => (server.managed.cursor = true)) },
      { match: "/api/configs/claude/disable", response: action("disable", () => (server.managed.claude = false)) },
      { match: "/api/configs/claude/restore", response: action("restore", () => undefined) },
      { match: "/diff", response: { state: "managed", missing: [], extra: [], changed: [] } },
      { match: "/api/configs/", response: () => configsPayload() },
      { match: "/api/settings", response: SETTINGS },
      { match: "/api/asset-tags", response: { tags: [] } },
      { match: "/api/home", response: { home: "/home/dev" } },
    ]),
  );
}

async function advance(ms: number) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

function pendingRequests(path: string) {
  return server.posts.filter((url) => url === path).length;
}

describe("request failure pressure: Configs page", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.stubGlobal("fetch", fetchMock);
    server.managed = { claude: true, cursor: false };
    server.outcome = { enable: "ok", disable: "ok", restore: "ok" };
    server.posts = [];
    installServer();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("never stays pending past the timeout, always shows the failure, and recovers on the next success", async () => {
    renderWithAppProviders(<ConfigsPage />);
    const manage = (await screen.findByRole("button", { name: "Manage" })) as HTMLButtonElement;

    // 1. Hung backend: the button stays pending until the write timeout, then the failure shows.
    server.outcome.enable = "hang";
    fireEvent.click(manage);
    fireEvent.click(manage);
    await waitFor(() => expect(manage.disabled).toBe(true));
    await advance(WRITE_TIMEOUT_MS - 1_000);
    expect(manage.disabled).toBe(true);
    expect(screen.queryByRole("alert")).toBeNull();
    await advance(1_000);
    await waitFor(() => expect(manage.disabled).toBe(false));
    let alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/Could not start managing Cursor\. The server did not respond in time/);
    expect(alert.textContent).not.toMatch(/ApiError/);
    expect(pendingRequests("/api/configs/cursor/enable")).toBe(1);

    // 2. A failure on a different action while the first banner is still up: the new message wins.
    server.outcome.disable = "offline";
    fireEvent.click(screen.getByRole("button", { name: "Stop managing" }));
    alert = await screen.findByText(/Could not stop managing Claude\. Could not reach the server/);
    expect(alert.textContent).not.toMatch(/ApiError|Failed to fetch/);
    expect(screen.getByRole("button", { name: "Stop managing" })).toHaveProperty("disabled", false);

    // 3. A plain 500 shows the backend's own message.
    server.outcome.enable = "http-500";
    fireEvent.click(screen.getByRole("button", { name: "Manage" }));
    await screen.findByText(/Could not start managing Cursor\. backend exploded/);
    expect(screen.queryByText(/ApiError/)).toBeNull();

    // 4. The backend recovers: the same button works, the list updates, the pending state clears.
    server.outcome.enable = "ok";
    fireEvent.click(screen.getByRole("button", { name: "Manage" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Manage" })).toBeNull());
    expect(screen.getAllByRole("button", { name: "Stop managing" })).toHaveLength(2);
    for (const button of screen.getAllByRole("button", { name: "Stop managing" })) {
      expect((button as HTMLButtonElement).disabled).toBe(false);
    }

    // 5. The failure banner leaves on its own and does not come back.
    await advance(6_000);
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  });

  it("times out a hung restore inside the drawer, then lets the retry succeed", async () => {
    renderWithAppProviders(<ConfigsPage />);
    fireEvent.click(await screen.findByText("Claude"));
    const dialog = await screen.findByRole("dialog");
    const restore = (await within(dialog).findByRole("button", { name: /Restore/ })) as HTMLButtonElement;

    server.outcome.restore = "hang";
    fireEvent.click(restore);
    fireEvent.click(restore);
    await waitFor(() => expect(restore.disabled).toBe(true));
    await advance(WRITE_TIMEOUT_MS);
    await waitFor(() => expect(restore.disabled).toBe(false));
    const alert = await within(dialog).findByRole("alert");
    expect(alert.textContent).toMatch(/Could not restore Claude\. The server did not respond in time/);
    expect(alert.textContent).not.toMatch(/ApiError/);
    expect(pendingRequests("/api/configs/claude/restore")).toBe(1);

    fireEvent.click(within(alert).getByRole("button", { name: "Dismiss error" }));
    await waitFor(() => expect(within(dialog).queryByRole("alert")).toBeNull());

    server.outcome.restore = "ok";
    fireEvent.click(restore);
    await waitFor(() => expect(pendingRequests("/api/configs/claude/restore")).toBe(2));
    await waitFor(() => expect(restore.disabled).toBe(false));
    expect(within(dialog).queryByRole("alert")).toBeNull();
  });

  it("keeps showing a drawer failure on the page after the drawer closes mid-request", async () => {
    renderWithAppProviders(<ConfigsPage />);
    fireEvent.click(await screen.findByText("Claude"));
    const dialog = await screen.findByRole("dialog");

    server.outcome.restore = "hang";
    fireEvent.click(await within(dialog).findByRole("button", { name: /Restore/ }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Close config details" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());

    await advance(WRITE_TIMEOUT_MS);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/Could not restore Claude\. The server did not respond in time/);
  });
});
