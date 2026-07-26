import { screen } from "@testing-library/react";
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

  it("renders backend-provided local storage paths", async () => {
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
        });
      }
      throw new Error(`Unhandled URL ${url}`);
    });

    renderWithAppProviders(<SettingsPage />);

    expect(await screen.findByText("/tmp/data/harness-asset-manager/shared")).toBeInTheDocument();
    expect(screen.getByText("/tmp/data/harness-asset-manager/marketplace")).toBeInTheDocument();
  });
});
