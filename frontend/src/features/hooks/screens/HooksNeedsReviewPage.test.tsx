import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { okJson } from "../../../test/fetch";
import { renderWithAppProviders } from "../../../test/render";
import HooksPage from "./HooksInUsePage";

const fetchMock = vi.fn();

function columnsFixture() {
  return [
    { harness: "cursor", label: "Cursor", logoKey: "cursor" },
    { harness: "claude", label: "Claude", logoKey: "claude" },
  ];
}

function emptyInventoryFixture() {
  return { columns: columnsFixture(), entries: [] };
}

function unmanagedHooksInventoryFixture() {
  return {
    columns: columnsFixture(),
    entries: [
      {
        id: "hook-1",
        displayName: "Pre-Commit Check",
        kind: "unmanaged",
        canEnable: true,
        spec: {
          id: "hook-1",
          event: "PreCommit",
          command: "npm test",
          description: "Run tests before commit",
        },
        sightings: [{ harness: "cursor", state: "unmanaged" }],
      },
    ],
  };
}

function mixedHooksInventoryFixture() {
  return {
    columns: columnsFixture(),
    entries: [
      {
        id: "managed-hook",
        displayName: "Managed Hook",
        kind: "managed",
        canEnable: true,
        sightings: [{ harness: "cursor", state: "managed" }],
      },
      ...unmanagedHooksInventoryFixture().entries,
    ],
  };
}

function renderPage(route = "/hooks?status=untracked") {
  return renderWithAppProviders(<HooksPage />, { route });
}

describe("Hooks unified inventory page", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("renders empty state when no hooks need review", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/hooks")) return okJson(emptyInventoryFixture());
      throw new Error(`Unhandled URL ${url}`);
    });

    renderPage();
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /no hooks need review/i })).toBeInTheDocument(),
    );
  });

  it("renders MatrixTable with discovery columns and Adopt button", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/hooks")) return okJson(unmanagedHooksInventoryFixture());
      throw new Error(`Unhandled URL ${url}`);
    });

    renderPage();
    await waitFor(() => expect(screen.getByRole("table", { name: /hooks matrix/i })).toBeInTheDocument());
    expect(screen.getByText("Pre-Commit Check")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Adopt$/i })).toBeInTheDocument();
  });

  it("triggers promote mutation when Adopt button is clicked", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/promote")) {
        expect(init?.method).toBe("POST");
        return okJson({ ok: true });
      }
      if (url.includes("/api/hooks")) return okJson(unmanagedHooksInventoryFixture());
      throw new Error(`Unhandled URL ${url}`);
    });

    renderPage();
    await waitFor(() => expect(screen.getByText("Pre-Commit Check")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: /^Adopt$/i }));
    await waitFor(() =>
      expect(fetchMock.mock.calls.some((call) => String(call[0]).includes("/promote"))).toBe(true),
    );
  });

  it("deep-link status=untracked renders only untracked rows", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/hooks")) return okJson(mixedHooksInventoryFixture());
      throw new Error(`Unhandled URL ${url}`);
    });

    renderPage("/hooks?status=untracked");
    await waitFor(() => expect(screen.getByText("Pre-Commit Check")).toBeInTheDocument());
    expect(screen.queryByText("Managed Hook")).not.toBeInTheDocument();
  });

  it("does not render checkboxes on managed rows", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/hooks")) return okJson(mixedHooksInventoryFixture());
      throw new Error(`Unhandled URL ${url}`);
    });

    renderPage("/hooks");
    await waitFor(() => expect(screen.getByText("Managed Hook")).toBeInTheDocument());
    expect(screen.getByRole("checkbox", { name: /select pre-commit check/i })).toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: /managed hook/i })).not.toBeInTheDocument();
  });

  it("shows the bulk dock only after an untracked row is selected", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.includes("/api/hooks")) return okJson(mixedHooksInventoryFixture());
      throw new Error(`Unhandled URL ${url}`);
    });

    renderPage("/hooks");
    await waitFor(() => expect(screen.getByRole("checkbox", { name: /select pre-commit check/i })).toBeInTheDocument());
    expect(screen.queryByRole("toolbar")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: /select pre-commit check/i }));
    expect(screen.getByRole("toolbar")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /adopt selected/i })).toBeInTheDocument();
  });
});
