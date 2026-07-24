import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { okJson } from "../../../test/fetch";
import { renderWithAppProviders } from "../../../test/render";
import AgentsInUsePage from "./AgentsInUsePage";
import type { AgentInventoryDto } from "../api/types";

const fetchMock = vi.fn();

function agentsInUseFixture(): AgentInventoryDto {
  return {
    columns: [
      { harness: "cursor", label: "Cursor", logoKey: "cursor", installed: true },
    ],
    issues: [],
    entries: [
      {
        ref: "agent-1",
        name: "Test Agent",
        description: "A test agent",
        kind: "managed",
        harnessPath: null,
        bindings: [
          { harness: "cursor", state: "disabled", detail: null }
        ],
        actions: { canAdopt: false, canDelete: true },
      },
    ],
  };
}

function renderPage() {
  return renderWithAppProviders(<AgentsInUsePage />, { route: "/agents/use" });
}

describe("AgentsInUsePage", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("renders MatrixTable with agent rows", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/agents")) return okJson(agentsInUseFixture());
      throw new Error(`Unhandled URL ${url}`);
    });

    renderPage();
    await waitFor(() => expect(screen.getByRole("table", { name: /Agents Matrix/i })).toBeInTheDocument());
    expect(screen.getByText("Test Agent")).toBeInTheDocument();
  });

  it("toggles a harness cell", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/enable")) {
        expect(init?.method).toBe("POST");
        return okJson({});
      }
      if (url.includes("/api/agents")) return okJson(agentsInUseFixture());
      throw new Error(`Unhandled URL ${url}`);
    });

    renderPage();
    await waitFor(() => expect(screen.getByText("Test Agent")).toBeInTheDocument());
    const enableButton = screen.getByRole("button", { name: /Enable for Cursor/i });
    fireEvent.click(enableButton);
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some((call) => String(call[0]).includes("/enable")),
      ).toBe(true),
    );
  });
});
