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

  it("renders backend-provided local storage paths and auto-adopt toggle", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/api/settings") {
        return okJson({
          storage: {
            platform: "linux",
            configDir: "/tmp/config/harness-asset-manager",
            dataDir: "/tmp/data/harness-asset-manager",
            stateDir: "/tmp/state/harness-asset-manager",
            skillsStorePath: "/tmp/data/harness-asset-manager/shared",
            marketplaceCachePath: "/tmp/data/harness-asset-manager/marketplace",
            settingsPath: "/tmp/config/harness-asset-manager/settings.json",
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

    expect(await screen.findByText("/tmp/data/harness-asset-manager/shared")).toBeInTheDocument();
    expect(screen.getByText("/tmp/data/harness-asset-manager/marketplace")).toBeInTheDocument();
    expect(screen.getByText("Repair drifted agent bindings automatically")).toBeInTheDocument();
    const toggle = screen.getByRole("switch", { name: "Repair drifted agent bindings automatically" });
    expect(toggle).toBeChecked();
  });

  it("flips auto-adopt toggle and calls exact URL /api/settings/auto-adopt/agents", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/api/settings") {
        return okJson({
          storage: {
            platform: "linux",
            configDir: "/tmp/config/harness-asset-manager",
            dataDir: "/tmp/data/harness-asset-manager",
            stateDir: "/tmp/state/harness-asset-manager",
            skillsStorePath: "/tmp/data/harness-asset-manager/shared",
            marketplaceCachePath: "/tmp/data/harness-asset-manager/marketplace",
            settingsPath: "/tmp/config/harness-asset-manager/settings.json",
          },
          harnesses: [],
          autoAdopt: {
            agents: true,
            skills: false,
          },
        });
      }
      if (url === "/api/settings/auto-adopt/agents") {
        expect(init?.method).toBe("PUT");
        expect(JSON.parse(String(init?.body))).toEqual({ enabled: false });
        return okJson({ ok: true, autoAdopt: { agents: false, skills: false } });
      }
      throw new Error(`Unhandled URL ${url}`);
    });

    renderWithAppProviders(<SettingsPage />);

    const toggle = await screen.findByRole("switch", { name: "Repair drifted agent bindings automatically" });
    expect(toggle).toBeChecked();

    fireEvent.click(toggle);

    await waitFor(() => {
      const call = fetchMock.mock.calls.find((c) => {
        const u = typeof c[0] === "string" ? c[0] : c[0].toString();
        return u === "/api/settings/auto-adopt/agents";
      });
      expect(call).toBeDefined();
      if (!call) return;
      expect(typeof call[0] === "string" ? call[0] : call[0].toString()).toBe("/api/settings/auto-adopt/agents");
      expect(call[1]?.method).toBe("PUT");
      expect(JSON.parse(String(call[1]?.body))).toEqual({ enabled: false });
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
            configDir: "/tmp/config/harness-asset-manager",
            dataDir: "/tmp/data/harness-asset-manager",
            stateDir: "/tmp/state/harness-asset-manager",
            skillsStorePath: "/tmp/data/harness-asset-manager/skills",
            marketplaceCachePath: "/tmp/data/harness-asset-manager/marketplace",
            settingsPath: "/tmp/config/harness-asset-manager/settings.json",
          },
          harnesses: [],
          autoAdopt: { agents: true, skills: false },
        });
      }
      throw new Error(`Unhandled URL ${url}`);
    });

    const { container } = renderWithAppProviders(<SettingsPage />);
    await screen.findByRole("switch", { name: "Repair drifted agent bindings automatically" });

    const rows = container.querySelectorAll(".settings-row");
    expect(rows.length).toBeGreaterThan(0);
    rows.forEach((row) => {
      expect(row.children).toHaveLength(3);
      expect(row.children[0]).toHaveClass("settings-row__icon");
      expect(row.children[1]).toHaveClass("settings-row__body");
    });
  });
});
