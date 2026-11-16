import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import AgentsInUsePage from "../features/agents/screens/AgentsInUsePage";
import { createRouteFetchMock, errorJson, okJson } from "./fetch";
import { renderWithAppProviders } from "./render";

const fetchMock = vi.fn();
const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

type CellState = "enabled" | "disabled";
const HARNESSES = [
  { harness: "claude", label: "Claude Code", logoKey: "claude", installed: true },
  { harness: "codex", label: "Codex", logoKey: "codex", installed: true },
];

// The fake server owns the truth. A failing write may or may not have landed first.
const server: Record<string, Record<string, CellState>> = {};

function inventory() {
  return {
    columns: HARNESSES,
    issues: [],
    entries: Object.entries(server).map(([ref, cells]) => ({
      ref,
      name: `Agent ${ref}`,
      description: `desc ${ref}`,
      kind: "managed",
      bindings: HARNESSES.map(({ harness }) => ({ harness, state: cells[harness], detail: null })),
      actions: { canAdopt: false, canDelete: true },
    })),
  };
}

interface Plan { delay: number; fail?: string; applyAnyway?: boolean }

function stubServer(plans: Record<string, Plan>) {
  fetchMock.mockImplementation(createRouteFetchMock([
    {
      match: (url, _input, init) => init?.method === "POST" && /\/api\/agents\/[^/]+\/(enable|disable)$/.test(url),
      response: async (url, _input, init) => {
        const [, ref, verb] = /\/api\/agents\/([^/]+)\/(enable|disable)$/.exec(url)!;
        const { harness } = JSON.parse(String(init?.body)) as { harness: string };
        const plan = plans[`${ref}:${harness}`];
        await sleep(plan.delay);
        if (!plan.fail || plan.applyAnyway) server[ref][harness] = verb === "enable" ? "enabled" : "disabled";
        return plan.fail ? errorJson(plan.fail, { status: 500 }) : okJson({});
      },
    },
    {
      match: (url) => url.includes("/api/agents"),
      response: async () => {
        const snapshot = inventory(); // the server answers with the state at request time
        await sleep(15);
        return snapshot;
      },
    },
  ]));
}

const rowOf = (ref: string) => screen.getByText(`Agent ${ref}`).closest("tr") as HTMLElement;
const cellOf = (ref: string, label: string) =>
  within(rowOf(ref)).getByRole("button", { name: new RegExp(`(Enable|Disable) for ${label}`) });
const expectedLabel = (state: CellState, label: string) => `${state === "enabled" ? "Disable" : "Enable"} for ${label}`;

describe("Agents matrix settle pressure test", () => {
  beforeEach(() => {
    for (const key of Object.keys(server)) delete server[key];
    server.a1 = { claude: "disabled", codex: "disabled" };
    server.a2 = { claude: "disabled", codex: "enabled" };
    server.a3 = { claude: "enabled", codex: "disabled" };
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("ends in the server's state with no stale cell when toggles overlap, lag and fail", async () => {
    stubServer({
      "a1:claude": { delay: 90 },                                  // slow success
      "a1:codex": { delay: 10 },                                   // fast success, resolves first
      "a2:claude": { delay: 40, fail: "disk full" },               // fails, nothing written
      "a2:codex": { delay: 25, fail: "write interrupted", applyAnyway: true }, // fails after writing
      "a3:codex": { delay: 55 },                                   // succeeds between the others
    });

    // Record each cell's state at the moment its pending marker clears. A cell that
    // stops spinning while it still shows the old value is the bug under test.
    const settledWith = new Map<string, string>();
    const observer = new MutationObserver((records) => {
      for (const record of records) {
        const el = record.target as HTMLElement;
        if (record.attributeName !== "data-pending" || el.hasAttribute("data-pending")) continue;
        const row = el.closest("tr")?.textContent ?? "";
        const key = `${/Agent (a\d)/.exec(row)?.[1]}:${el.getAttribute("aria-label")?.replace(/^(Enable|Disable) for /, "")}`;
        settledWith.set(key, el.getAttribute("aria-label") ?? "");
      }
    });

    renderWithAppProviders(<AgentsInUsePage />, { route: "/agents" });
    await waitFor(() => expect(screen.getByText("Agent a1")).toBeInTheDocument());
    observer.observe(document.body, { subtree: true, attributes: true, attributeFilter: ["data-pending"] });

    fireEvent.click(cellOf("a1", "Claude Code"));
    fireEvent.click(cellOf("a2", "Claude Code"));
    fireEvent.click(cellOf("a1", "Codex"));
    fireEvent.click(cellOf("a2", "Codex"));
    fireEvent.click(cellOf("a3", "Codex"));

    // All five writes have been sent; wait for every spinner to clear.
    await waitFor(() => expect(document.querySelectorAll('[data-pending="true"]')).toHaveLength(5));
    await waitFor(() => expect(document.querySelectorAll('[data-pending="true"]')).toHaveLength(0), { timeout: 3000 });
    observer.disconnect();

    // Final state: every cell matches the server, with no extra waiting after the spinners cleared.
    for (const [ref, cells] of Object.entries(server)) {
      expect(cellOf(ref, "Claude Code")).toHaveAttribute("aria-label", expectedLabel(cells.claude, "Claude Code"));
      expect(cellOf(ref, "Codex")).toHaveAttribute("aria-label", expectedLabel(cells.codex, "Codex"));
    }
    expect(server.a1).toEqual({ claude: "enabled", codex: "enabled" });
    expect(server.a2).toEqual({ claude: "disabled", codex: "disabled" }); // codex write landed despite the error

    // No cell stopped spinning while still showing a value the server no longer held.
    for (const [key, label] of settledWith) {
      const [ref, harness] = key.split(":");
      const column = harness;
      const state = server[ref][column === "Claude Code" ? "claude" : "codex"];
      expect(label, `cell ${key} cleared its spinner on stale data`).toBe(expectedLabel(state, column));
    }
    expect(settledWith.size).toBe(5);

    // The failures are surfaced, not swallowed by the refetch.
    expect(screen.getByRole("alert")).toHaveTextContent(/disk full|write interrupted/);
  });
});
