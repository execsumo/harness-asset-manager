import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { errorJson, okJson } from "../../../test/fetch";
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
  if (url.includes("/api/asset-tags")) return okJson({ tags: [] });
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

  it("assigns a shared tag to a config and preserves existing tags", async () => {
    let tags = ["starred"];
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/api/asset-tags/") return okJson({ tags: ["Research"] });
      if (url === "/api/configs/cursor/tags" && init?.method === "PUT") {
        tags = JSON.parse(String(init.body)).tags;
        return okJson({ tags });
      }
      if (url === "/api/configs/") return okJson({ ...CONFIGS, cursor: { ...CONFIGS.cursor, tags } });
      const response = respond(url);
      if (response) return response;
      throw new Error(`Unhandled URL ${url}`);
    });

    renderWithAppProviders(<ConfigsPage />);
    fireEvent.click(await screen.findByText("Cursor"));
    fireEvent.click(screen.getByRole("button", { name: "Add tag" }));
    fireEvent.mouseDown(await screen.findByRole("option", { name: "Research" }));
    await waitFor(() => expect(tags).toEqual(["starred", "Research"]));
    expect(await screen.findByRole("button", { name: "Remove tag Research" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Remove tag Research" }));
    await waitFor(() => expect(tags).toEqual(["starred"]));
  });

  it("toggles a case-folded starred tag off", async () => {
    let tags = ["ſtarred", "Research"];
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/api/configs/cursor/tags" && init?.method === "PUT") {
        tags = JSON.parse(String(init.body)).tags;
        return okJson({ tags });
      }
      if (url === "/api/configs/") return okJson({ ...CONFIGS, cursor: { ...CONFIGS.cursor, tags } });
      const response = respond(url);
      if (response) return response;
      throw new Error(`Unhandled URL ${url}`);
    });
    renderWithAppProviders(<ConfigsPage />);
    const row = (await screen.findByText("Cursor")).closest("tr")!;
    const button = within(row).getByRole("button", { name: "Remove star" });
    expect(button.getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(button);
    await waitFor(() => expect(tags).toEqual(["Research"]));
    await waitFor(() => expect(within(row).getByRole("button", { name: /^star$/i }).getAttribute("aria-pressed")).toBe("false"));
  });

  it("reports tag removal failures and permits retry", async () => {
    let attempts = 0;
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/api/configs/cursor/tags" && init?.method === "PUT") {
        attempts++;
        if (attempts === 1) throw new Error("Network unavailable");
        return okJson({ tags: [] });
      }
      if (url === "/api/configs/") return okJson({ ...CONFIGS, cursor: { ...CONFIGS.cursor, tags: attempts > 1 ? [] : ["Research"] } });
      const response = respond(url);
      if (response) return response;
      throw new Error(`Unhandled URL ${url}`);
    });
    renderWithAppProviders(<ConfigsPage />);
    fireEvent.click(await screen.findByText("Cursor"));
    fireEvent.click(screen.getByRole("button", { name: "Remove tag Research" }));
    expect(await screen.findByText("Network unavailable")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Remove tag Research" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Remove tag Research" })).toBeNull());
    expect(screen.queryByText("Network unavailable")).toBeNull();
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

describe("ConfigsPage action failures", () => {
  const posts: string[] = [];

  function route(overrides: (url: string, init?: RequestInit) => Response | Promise<Response> | null) {
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (init?.method === "POST") posts.push(url);
      const custom = overrides(url, init);
      if (custom) return custom;
      if (url.endsWith("/diff")) return okJson({ state: "managed", missing: [], extra: [], changed: [] });
      const response = respond(url);
      if (response) return response;
      throw new Error(`Unhandled URL ${url}`);
    });
  }

  async function expectReadableAlert(message: RegExp) {
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(message);
    expect(alert.textContent).not.toMatch(/ApiError/);
    return alert;
  }

  beforeEach(() => {
    posts.length = 0;
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("shows a readable alert when enabling a harness fails, and lets the user dismiss it", async () => {
    route((url) =>
      url === "/api/configs/cursor/enable" ? errorJson("config file is locked", { status: 409 }) : null,
    );
    renderWithAppProviders(<ConfigsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Manage" }));

    const alert = await expectReadableAlert(/Could not start managing Cursor\. config file is locked/);
    fireEvent.click(within(alert).getByRole("button", { name: "Dismiss error" }));
    await waitFor(() => expect(screen.queryByRole("alert")).toBeNull());
  });

  it("shows a readable alert when disabling a harness fails", async () => {
    route((url) =>
      url === "/api/configs/claude/disable" ? errorJson("cannot remove record", { status: 500 }) : null,
    );
    renderWithAppProviders(<ConfigsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Stop managing" }));

    await expectReadableAlert(/Could not stop managing Claude\. cannot remove record/);
  });

  it("shows a readable alert inside the drawer when restoring fails", async () => {
    route((url) =>
      url === "/api/configs/claude/restore" ? errorJson("snapshot is corrupt", { status: 500 }) : null,
    );
    renderWithAppProviders(<ConfigsPage />);

    fireEvent.click(await screen.findByText("Claude"));
    fireEvent.click(await screen.findByRole("button", { name: /Restore/ }));

    const alert = await expectReadableAlert(/Could not restore Claude\. snapshot is corrupt/);
    expect(screen.getByRole("dialog").contains(alert)).toBe(true);
  });

  it("shows a readable alert when capture fails", async () => {
    route((url) => (url.startsWith("/api/configs/capture") ? errorJson("disk full", { status: 500 }) : null));
    renderWithAppProviders(<ConfigsPage />);

    fireEvent.click(await screen.findByRole("button", { name: /Capture all/ }));

    await expectReadableAlert(/Could not capture configs\. disk full/);
  });

  it("shows a readable alert when the drift check fails instead of claiming no drift", async () => {
    route((url) => (url === "/api/configs/claude/diff" ? errorJson("diff exploded", { status: 500 }) : null));
    renderWithAppProviders(<ConfigsPage />);

    fireEvent.click(await screen.findByText("Claude"));

    await expectReadableAlert(/Could not check Claude for drift\. diff exploded/);
    expect(screen.getByText("Drift could not be checked.")).toBeTruthy();
    expect(screen.queryByText("The config file matches the captured snapshot.")).toBeNull();
  });

  it("shows a readable alert when starring fails", async () => {
    route((url, init) =>
      url === "/api/configs/cursor/tags" && init?.method === "PUT"
        ? errorJson("tags are read-only", { status: 500 })
        : null,
    );
    renderWithAppProviders(<ConfigsPage />);

    const row = (await screen.findByText("Cursor")).closest("tr")!;
    fireEvent.click(within(row).getByRole("button", { name: "Star" }));

    await expectReadableAlert(/Could not update tags for Cursor\. tags are read-only/);
  });

  it("disables a row action while it is pending and sends one request for a double click", async () => {
    let release: (response: Response) => void = () => undefined;
    route((url) =>
      url === "/api/configs/cursor/enable"
        ? new Promise<Response>((resolve) => {
            release = resolve;
          })
        : null,
    );
    renderWithAppProviders(<ConfigsPage />);

    const button = await screen.findByRole("button", { name: "Manage" });
    fireEvent.click(button);
    fireEvent.click(button);

    await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(true));
    expect(posts.filter((url) => url === "/api/configs/cursor/enable")).toHaveLength(1);

    release(okJson({ status: "ok" }));
    await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
    expect(posts.filter((url) => url === "/api/configs/cursor/enable")).toHaveLength(1);
  });

  it("disables the drawer restore button while pending and sends one request for a double click", async () => {
    let release: (response: Response) => void = () => undefined;
    route((url) =>
      url === "/api/configs/claude/restore"
        ? new Promise<Response>((resolve) => {
            release = resolve;
          })
        : null,
    );
    renderWithAppProviders(<ConfigsPage />);

    fireEvent.click(await screen.findByText("Claude"));
    const button = await screen.findByRole("button", { name: /Restore/ });
    fireEvent.click(button);
    fireEvent.click(button);

    await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(true));
    expect(posts.filter((url) => url === "/api/configs/claude/restore")).toHaveLength(1);

    release(okJson({ status: "ok" }));
    await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
  });

  it("disables the capture button while capture is pending", async () => {
    let release: (response: Response) => void = () => undefined;
    route((url) =>
      url.startsWith("/api/configs/capture")
        ? new Promise<Response>((resolve) => {
            release = resolve;
          })
        : null,
    );
    renderWithAppProviders(<ConfigsPage />);

    const button = await screen.findByRole("button", { name: /Capture all/ });
    fireEvent.click(button);
    fireEvent.click(button);

    await waitFor(() => expect(screen.getByRole("button", { name: /Capturing/ }).hasAttribute("disabled")).toBe(true));
    expect(posts.filter((url) => url.startsWith("/api/configs/capture"))).toHaveLength(1);
    release(okJson({ status: "ok" }));
  });
});
