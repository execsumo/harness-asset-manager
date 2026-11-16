import { fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import { createRouteFetchMock, okJson } from "./fetch";
import { mcpInventoryPayload } from "./fixtures/mcp";
import { skillsPayload } from "./fixtures/skills";
import { renderWithRouter, stubDesktopMatchMedia } from "./render";

// One real page crashes during render. The rest of the app must stay usable.
vi.mock("../features/settings/screens/SettingsPage", () => ({
  default: function BrokenSettingsPage(): never {
    throw new Error("Settings exploded during render");
  },
}));

const fetchMock = vi.fn();

describe("Error boundary UI pressure test", () => {
  beforeEach(() => {
    stubDesktopMatchMedia();
    fetchMock.mockImplementation(
      createRouteFetchMock(
        [
          { match: "/api/skills", response: skillsPayload() },
          { match: "/api/mcp/servers", response: mcpInventoryPayload() },
          {
            match: "/api/slash-commands",
            response: { storePath: "/tmp/commands", syncStatePath: "/tmp/sync.json", targets: [], commands: [], reviewCommands: [] },
          },
        ],
        () => okJson({}),
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  afterEach(() => {
    window.localStorage.clear();
    window.sessionStorage.clear();
    fetchMock.mockReset();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("keeps navigation working after a page throws, and recovers on route change", async () => {
    renderWithRouter(<App />, { route: "/settings" });

    const alert = await screen.findByRole("alert", {}, { timeout: 10000 });
    expect(alert).toHaveTextContent("Something went wrong");
    expect(alert).toHaveTextContent("Settings exploded during render");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reload page" })).toBeInTheDocument();

    // Sidebar is still mounted and usable.
    expect(screen.getByLabelText(/primary navigation/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("link", { name: /^Overview$/i }));

    await screen.findByRole("heading", { name: "Overview" }, { timeout: 10000 });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    // The broken page still fails when revisited, and the fallback comes back.
    fireEvent.click(screen.getByRole("link", { name: /^Settings$/i }));
    expect(await screen.findByRole("alert", {}, { timeout: 10000 })).toHaveTextContent(
      "Settings exploded during render",
    );
    expect(screen.getByLabelText(/primary navigation/i)).toBeInTheDocument();
  });
});
