import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { okJson } from "../../../test/fetch";
import { renderWithAppProviders } from "../../../test/render";
import SettingsPage from "./SettingsPage";

const fetchMock = vi.fn();

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("renders backend-provided local storage paths and auto-adopt matrix", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/api/settings") {
        return okJson({
          storage: {
            platform: "linux",
            configDir: "/tmp/config/harnessam",
            dataDir: "/tmp/data/harnessam",
            stateDir: "/tmp/state/harnessam",
            skillsStorePath: "/tmp/data/harnessam/shared",
            marketplaceCachePath: "/tmp/data/harnessam/marketplace",
            settingsPath: "/tmp/config/harnessam/settings.json",
          },
          harnesses: [],
          autoAdopt: {
            agents: true,
            skills: false,
          },
        });
      }
      throw new Error(`Unhandled URL ${url}`);
    });

    renderWithAppProviders(<SettingsPage />);

    expect(await screen.findByText("/tmp/data/harnessam/shared")).toBeInTheDocument();
    expect(screen.getByText("/tmp/data/harnessam/marketplace")).toBeInTheDocument();
    expect(screen.getByText("Repair Drift")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enable all auto-maintenance" })).toBeInTheDocument();
  });

  it("groups harnesses by detection status and locks undetected harnesses off", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/api/settings") {
        return okJson({
          storage: {
            platform: "linux",
            configDir: "/tmp/config",
            dataDir: "/tmp/data",
            stateDir: "/tmp/state",
            skillsStorePath: "/tmp/data/skills",
            marketplaceCachePath: "/tmp/data/marketplace",
            settingsPath: "/tmp/config/settings.json",
          },
          harnesses: [
            { harness: "codex", label: "Codex", logoKey: null, supportEnabled: true, installed: true, managedLocation: "/tmp/.agents" },
            { harness: "opencode", label: "OpenCode", logoKey: null, supportEnabled: true, installed: false, managedLocation: "/tmp/config/opencode" },
          ],
          autoAdopt: { agents: true, skills: false, slash_commands: false, mcp: false, hooks: false, permissions: false },
          autoAdoptHarnesses: { agents: [], skills: [], slash_commands: [], mcp: [], hooks: [], permissions: [] },
          autoAdoptHarnessOptions: { agents: ["codex"], skills: [], slash_commands: [], mcp: [], hooks: [], permissions: [] },
        });
      }
      throw new Error(`Unhandled URL ${url}`);
    });

    const { container } = renderWithAppProviders(<SettingsPage />);

    await screen.findByText("Codex");
    const headings = Array.from(container.querySelectorAll(".settings-maintenance__group-heading"), (heading) => heading.textContent);
    expect(headings).toContain("Detected harnesses");
    expect(headings).toContain("Not detected harnesses");
    expect(container.textContent?.indexOf("Detected harnesses")).toBeLessThan(
      container.textContent?.indexOf("Not detected harnesses") ?? -1,
    );

    const unavailableToggle = screen.getByRole("switch", { name: "Enable OpenCode support" });
    expect(unavailableToggle).not.toBeChecked();
    expect(unavailableToggle).toBeDisabled();
    const harnessRow = unavailableToggle.closest(".settings-maintenance__harness");
    expect(harnessRow).toBeInTheDocument();
    expect(harnessRow?.querySelector(".settings-row__sub")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Repair drifted Agent bindings not supported for OpenCode")).toHaveTextContent("—");
  });

  it("enables all auto-adopt families through the bulk action", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/api/settings") {
        return okJson({
          storage: {
            platform: "linux",
            configDir: "/tmp/config/harnessam",
            dataDir: "/tmp/data/harnessam",
            stateDir: "/tmp/state/harnessam",
            skillsStorePath: "/tmp/data/harnessam/shared",
            marketplaceCachePath: "/tmp/data/harnessam/marketplace",
            settingsPath: "/tmp/config/harnessam/settings.json",
          },
          harnesses: [],
          autoAdopt: { agents: false, skills: false },
          autoAdoptHarnesses: { agents: [], skills: [] },
          autoAdoptHarnessOptions: { agents: [], skills: [] },
        });
      }
      if (url.startsWith("/api/settings/auto-adopt/")) {
        expect(init?.method).toBe("PUT");
        expect(JSON.parse(String(init?.body))).toEqual({ enabled: true });
        return okJson({ ok: true, autoAdopt: { agents: true, skills: true } });
      }
      throw new Error(`Unhandled URL ${url}`);
    });

    renderWithAppProviders(<SettingsPage />);
    fireEvent.click(await screen.findByRole("button", { name: "Enable all auto-maintenance" }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.filter(([input]) => {
          const url = typeof input === "string" ? input : input.toString();
          return url.startsWith("/api/settings/auto-adopt/");
        }),
      ).toHaveLength(6);
    });
  });

  it("gives every settings row all three grid children", async () => {
    // .settings-row is `grid-template-columns: 28px minmax(0, 1fr) auto`. A row that
    // omits its icon does not shift left: __body drops into the fixed 28px track and
    // its text overflows a column it can never fill, with the trailing control laid
    // out underneath. That is exactly how the auto-adopt row shipped, so pin the
    // contract rather than the symptom.
    vi.mocked(global.fetch).mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/api/settings") {
        return okJson({
          storage: {
            platform: "linux",
            configDir: "/tmp/config/harnessam",
            dataDir: "/tmp/data/harnessam",
            stateDir: "/tmp/state/harnessam",
            skillsStorePath: "/tmp/data/harnessam/skills",
            marketplaceCachePath: "/tmp/data/harnessam/marketplace",
            settingsPath: "/tmp/config/harnessam/settings.json",
          },
          harnesses: [],
          autoAdopt: { agents: true, skills: false },
        });
      }
      throw new Error(`Unhandled URL ${url}`);
    });

    const { container } = renderWithAppProviders(<SettingsPage />);
    await screen.findByRole("button", { name: "Enable all auto-maintenance" });

    const rows = container.querySelectorAll(".settings-row");
    expect(rows.length).toBeGreaterThan(0);
    rows.forEach((row) => {
      expect(row.children).toHaveLength(3);
      expect(row.children[0]).toHaveClass("settings-row__icon");
      expect(row.children[1]).toHaveClass("settings-row__body");
    });
  });

  it("updates one harness target for an auto-adopt family", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/api/settings") {
        return okJson({
          storage: {
            platform: "linux",
            configDir: "/tmp/config",
            dataDir: "/tmp/data",
            stateDir: "/tmp/state",
            skillsStorePath: "/tmp/data/skills",
            marketplaceCachePath: "/tmp/data/marketplace",
            settingsPath: "/tmp/config/settings.json",
          },
          harnesses: [
            { harness: "codex", label: "Codex", logoKey: null, supportEnabled: true, installed: true, managedLocation: "/tmp/.agents" },
          ],
          autoAdopt: {
            agents: true,
            skills: false,
            slash_commands: false,
            mcp: false,
            hooks: false,
            permissions: false,
          },
          autoAdoptHarnesses: {
            agents: [],
            skills: [],
            slash_commands: [],
            mcp: [],
            hooks: [],
            permissions: [],
          },
          autoAdoptHarnessOptions: {
            agents: ["codex"],
            skills: [],
            slash_commands: [],
            mcp: [],
            hooks: [],
            permissions: [],
          },
        });
      }
      if (url === "/api/settings/auto-adopt/agents/harnesses") {
        expect(init?.method).toBe("PUT");
        expect(JSON.parse(String(init?.body))).toEqual({ harnesses: ["codex"] });
        return okJson({ ok: true, autoAdoptHarnesses: { agents: ["codex"] } });
      }
      throw new Error(`Unhandled URL ${url}`);
    });

    renderWithAppProviders(<SettingsPage />);

    const checkbox = await screen.findByRole("checkbox", {
      name: "Repair drifted Agent bindings for Codex",
    });
    fireEvent.click(checkbox);

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some((call) => {
          const url = typeof call[0] === "string" ? call[0] : call[0].toString();
          return url === "/api/settings/auto-adopt/agents/harnesses";
        }),
      ).toBe(true);
    });
  });
});
