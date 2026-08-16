import { fireEvent, screen, waitFor } from "@testing-library/react";
import { Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { okJson } from "../../../test/fetch";
import { renderWithAppProviders } from "../../../test/render";
import AgentsInUsePage from "./AgentsInUsePage";
import type { AgentInventoryDto } from "../api/types";
import { getAgentsRouteElements } from "../routes";

const fetchMock = vi.fn();

function unmanagedAgentsFixture(): AgentInventoryDto {
  return {
    columns: [
      { harness: "cursor", label: "Cursor", logoKey: "cursor", installed: true },
      { harness: "claude", label: "Claude Code", logoKey: "claude", installed: true },
    ],
    issues: [],
    entries: [
      {
        ref: "claude/conflict-agent",
        name: "Conflict Agent",
        description: "Will 409",
        kind: "unmanaged",
        harnessPath: ".cursor/agents/conflict-agent.yaml",
        bindings: [
          { harness: "cursor", state: "enabled", detail: null }
        ],
        actions: { canAdopt: true, canDelete: false },
      },
      {
        ref: "opencode/ok-agent",
        name: "OK Agent",
        description: "Will 200",
        kind: "unmanaged",
        harnessPath: ".cursor/agents/ok-agent.yaml",
        bindings: [
          { harness: "cursor", state: "enabled", detail: null }
        ],
        actions: { canAdopt: true, canDelete: false },
      },
    ],
  };
}

function mixedAgentsFixture(): AgentInventoryDto {
  return {
    ...unmanagedAgentsFixture(),
    entries: [
      {
        ref: "managed/agent",
        name: "Managed Agent",
        description: "Already tracked",
        kind: "managed",
        harnessPath: null,
        bindings: [{ harness: "cursor", state: "enabled", detail: null }],
        actions: { canAdopt: false, canDelete: true },
      },
      ...unmanagedAgentsFixture().entries,
    ],
  };
}

function renderPage() {
  return renderWithAppProviders(<AgentsInUsePage />, { route: "/agents?status=untracked" });
}

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="agents-location">{location.pathname}{location.search}</output>;
}

function renderRoutes(route: string) {
  return renderWithAppProviders(
    <>
      <Routes>{getAgentsRouteElements()}</Routes>
      <LocationProbe />
    </>,
    { route },
  );
}

describe("Agents unified inventory", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("renders MatrixTable with unmanaged agents", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/agents")) return okJson(unmanagedAgentsFixture());
      throw new Error(`Unhandled URL ${url}`);
    });

    renderPage();
    await waitFor(() => expect(screen.getByRole("table", { name: /Agents Matrix/i })).toBeInTheDocument());
    expect(screen.getByText("OK Agent")).toBeInTheDocument();

    const okRow = screen.getByText("OK Agent").closest("tr");
    expect(okRow).not.toBeNull();
    expect(okRow?.querySelector('[aria-label="Open details for OK Agent"]')).not.toBeNull();
    expect(okRow?.querySelector('[aria-label="Not found in Claude Code"]')).not.toBeNull();
    expect(okRow?.querySelectorAll('[aria-label^="Open details for"]').length).toBe(1);
  });

  it("renders each issue's name and reason verbatim when issues are present", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/agents")) {
        return okJson({
          ...unmanagedAgentsFixture(),
          issues: [
            {
              name: "auditor",
              reason: "Claude replaced the link at /Users/x/.claude/agents/auditor.md with an edited copy.",
            },
          ],
        });
      }
      throw new Error(`Unhandled URL ${url}`);
    });

    renderPage();
    await waitFor(() => expect(screen.getByText("OK Agent")).toBeInTheDocument());
    expect(screen.getByText("auditor")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Claude replaced the link at /Users/x/.claude/agents/auditor.md with an edited copy.",
      ),
    ).toBeInTheDocument();
  });

  it("renders no issues section when issues is empty", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/agents")) return okJson(unmanagedAgentsFixture());
      throw new Error(`Unhandled URL ${url}`);
    });

    renderPage();
    await waitFor(() => expect(screen.getByText("OK Agent")).toBeInTheDocument());
    expect(screen.queryByText("Bindings that need attention")).not.toBeInTheDocument();
  });

  it("renders recent automatic repairs when present", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/agents")) {
        return okJson({
          ...unmanagedAgentsFixture(),
          recentRepairs: [
            {
              at: 1783997184.96,
              ref: "red-team",
              harness: "claude",
              action: "adopted",
              detail: "adopted edited harness copy into store and restored link",
            },
          ],
        });
      }
      throw new Error(`Unhandled URL ${url}`);
    });

    renderPage();
    await waitFor(() => expect(screen.getByText("Recent automatic repairs")).toBeInTheDocument());
    expect(
      screen.getByText("adopted edited harness copy into store and restored link"),
    ).toBeInTheDocument();
    expect(screen.getByText(/red-team/)).toBeInTheDocument();
    expect(screen.queryByText(/1970/)).not.toBeInTheDocument();
  });

  it("renders no repairs section when recentRepairs is empty or absent", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/agents")) {
        return okJson({
          ...unmanagedAgentsFixture(),
          recentRepairs: [],
        });
      }
      throw new Error(`Unhandled URL ${url}`);
    });

    renderPage();
    await waitFor(() => expect(screen.getByText("OK Agent")).toBeInTheDocument());
    expect(screen.queryByText("Recent automatic repairs")).not.toBeInTheDocument();
  });

  it("handles 409 conflict and resolves with keep_store", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/adopt")) {
        if (init?.body && String(init.body).includes("keep_store")) {
          expect(init?.method).toBe("POST");
          return okJson({});
        }
        return new Response(
          JSON.stringify({
            conflict: "store-name-exists",
            slug: "conflict-agent",
            storePath: "agents/conflict-agent.yaml",
            harnessPath: ".cursor/agents/conflict-agent.yaml",
          }),
          { status: 409, headers: { "Content-Type": "application/json" } }
        );
      }
      if (url.includes("/api/agents")) return okJson(unmanagedAgentsFixture());
      throw new Error(`Unhandled URL ${url}`);
    });

    renderPage();
    await waitFor(() => expect(screen.getByText("Conflict Agent")).toBeInTheDocument());
    
    // click adopt for Conflict Agent
    const rows = screen.getAllByRole("row");
    const conflictRow = rows.find(r => r.textContent?.includes("Conflict Agent"));
    const adoptButton = conflictRow!.querySelector("button.action-pill")!;
    fireEvent.click(adoptButton);

    await waitFor(() => expect(screen.getByText(/Name Collision: conflict-agent/i)).toBeInTheDocument());
    
    // Click Keep project version
    const keepButton = screen.getByRole("button", { name: /Keep the project version/i });
    fireEvent.click(keepButton);

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some((call) => String(call[1]?.body).includes('"onConflict":"keep_store"')),
      ).toBe(true),
    );
  });

  it("bulk adopt surfaces skipped[]", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/adopt-all")) {
        expect(init?.method).toBe("POST");
        return okJson({
          ok: true,
          adopted: ["opencode/ok-agent"],
          skipped: [{ ref: "claude/conflict-agent", reason: "conflict" }]
        });
      }
      if (url.includes("/api/agents")) return okJson(unmanagedAgentsFixture());
      throw new Error(`Unhandled URL ${url}`);
    });

    renderPage();
    await waitFor(() => expect(screen.getByText("OK Agent")).toBeInTheDocument());
    
    const adoptAllButton = screen.getByRole("button", { name: /Adopt all eligible/i });
    fireEvent.click(adoptAllButton);

    await waitFor(() => expect(screen.getByText(/Skipped 1 agents due to conflicts/i)).toBeInTheDocument());
  });

  it("deep-link status=untracked renders only untracked rows", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/agents")) return okJson(mixedAgentsFixture());
      throw new Error(`Unhandled URL ${url}`);
    });

    renderPage();
    await waitFor(() => expect(screen.getByText("OK Agent")).toBeInTheDocument());
    expect(screen.queryByText("Managed Agent")).not.toBeInTheDocument();
  });

  it("does not render checkboxes on managed rows", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/agents")) return okJson(mixedAgentsFixture());
      throw new Error(`Unhandled URL ${url}`);
    });

    renderWithAppProviders(<AgentsInUsePage />, { route: "/agents" });
    await waitFor(() => expect(screen.getByText("Managed Agent")).toBeInTheDocument());
    expect(screen.getByRole("checkbox", { name: /select ok agent/i })).toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: /managed agent/i })).not.toBeInTheDocument();
  });

  it("shows the bulk dock only after an untracked row is selected", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/agents")) return okJson(mixedAgentsFixture());
      throw new Error(`Unhandled URL ${url}`);
    });

    renderWithAppProviders(<AgentsInUsePage />, { route: "/agents" });
    await waitFor(() => expect(screen.getByRole("checkbox", { name: /select ok agent/i })).toBeInTheDocument());
    expect(screen.queryByRole("toolbar")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: /select ok agent/i }));
    expect(screen.getByRole("toolbar")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /adopt selected/i })).toBeInTheDocument();
  });
});

describe("Agents legacy route redirects", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/agents")) return okJson(unmanagedAgentsFixture());
      throw new Error(`Unhandled URL ${url}`);
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("redirects /agents/use to /agents without a status filter", async () => {
    renderRoutes("/agents/use");
    await waitFor(() => expect(screen.getByTestId("agents-location")).toHaveTextContent("/agents"));
    expect(screen.getByTestId("agents-location")).toHaveTextContent(/^\/agents$/);
  });

  it("redirects /agents/review to the untracked filter and renders untracked rows", async () => {
    renderRoutes("/agents/review");
    await waitFor(() => {
      expect(screen.getByTestId("agents-location")).toHaveTextContent("/agents?status=untracked");
      expect(screen.getByText("OK Agent")).toBeInTheDocument();
    });
  });
});
