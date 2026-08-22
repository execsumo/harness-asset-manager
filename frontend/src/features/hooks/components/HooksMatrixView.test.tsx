import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { HookInventoryColumnDto, HookInventoryEntryDto } from "../api/management-types";
import { HooksMatrixView } from "./HooksMatrixView";

const columns: HookInventoryColumnDto[] = [
  { harness: "codex", label: "Codex", logoKey: "codex", installed: true, configPresent: true, hooksWritable: true },
  { harness: "cursor", label: "Cursor", logoKey: "cursor", installed: true, configPresent: true, hooksWritable: true },
];

const entries: HookInventoryEntryDto[] = [
  {
    id: "alpha-hook",
    displayName: "Alpha Hook",
    kind: "managed",
    canEnable: true,
    enabledStatus: "enabled",
    sightings: [
      { harness: "codex", state: "managed" },
      { harness: "cursor", state: "missing" },
    ],
  },
  {
    id: "zeta-hook",
    displayName: "Zeta Hook",
    kind: "managed",
    canEnable: true,
    enabledStatus: "disabled",
    sightings: [
      { harness: "codex", state: "missing" },
      { harness: "cursor", state: "missing" },
    ],
  },
];

function renderMatrix() {
  const props = {
    entries,
    columns,
    pendingHookKeys: new Set<string>(),
    pendingPerHarnessKeys: new Set<string>(),
    checkedIds: new Set<string>(),
    onOpenDetail: vi.fn(),
    onToggleChecked: vi.fn(),
    onEnableHarness: vi.fn(),
    onDisableHarness: vi.fn(),
    onAdopt: vi.fn(),
  };
  render(<HooksMatrixView {...props} />);
  return props;
}

describe("HooksMatrixView", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "ResizeObserver",
      class ResizeObserver {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders a harness matrix with sortable rows", () => {
    renderMatrix();

    const table = screen.getByRole("table", { name: "Hooks harness matrix" });
    const headerCells = table.querySelectorAll("thead tr > th");
    expect(headerCells).toHaveLength(columns.length + 4);
    expect(table.querySelectorAll("tbody tr:first-child > td")).toHaveLength(headerCells.length);
    expect(rowNames()).toEqual(["Alpha Hook", "Zeta Hook"]);

    // Sort desc by name
    fireEvent.click(screen.getByRole("button", { name: "Sort by Hook" }));
    expect(rowNames()).toEqual(["Zeta Hook", "Alpha Hook"]);

    // Sort by Active
    fireEvent.click(screen.getByRole("button", { name: "Sort by Active" }));
    expect(rowNames()).toEqual(["Zeta Hook", "Alpha Hook"]);
  });

  it("sorts by harness column", () => {
    renderMatrix();

    fireEvent.click(screen.getByRole("button", { name: "Sort by Codex" }));
    expect(rowNames()).toEqual(["Alpha Hook", "Zeta Hook"]);
  });
});

function rowNames(): string[] {
  const table = screen.getByRole("table", { name: "Hooks harness matrix" });
  return within(table)
    .getAllByRole("row")
    .slice(1)
    .map((row) => within(row).getAllByText(/Alpha Hook|Zeta Hook/)[0].textContent ?? "");
}
