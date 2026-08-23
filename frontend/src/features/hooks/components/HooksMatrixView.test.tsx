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

function buildProps(testEntries: HookInventoryEntryDto[] = entries) {
  return {
    entries: testEntries,
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
}

function renderMatrix() {
  const props = buildProps();
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

  it("renders the event as the row heading when a spec is present, command on the second line", () => {
    const withSpec: HookInventoryEntryDto[] = [
      {
        ...entries[0],
        spec: {
          command: "dossier hook pre-compaction",
          description: "",
          event: "pre_compact",
          id: "alpha-hook",
          installedAt: "2026-01-01T00:00:00Z",
          match: "any",
          revision: "1",
        },
      },
    ];
    render(<HooksMatrixView {...buildProps(withSpec)} />);

    const identity = screen.getByText("pre_compact").closest(".matrix-table__cell--identity");
    expect(identity).not.toBeNull();
    expect(identity?.querySelector(".matrix-table__name-text")?.textContent).toBe("pre_compact");
    expect(identity?.querySelector(".matrix-table__description")?.textContent).toBe(
      "dossier hook pre-compaction",
    );
    expect(screen.queryByText("Alpha Hook")).toBeNull();
  });

  it("renders a harness matrix with sortable rows", () => {
    renderMatrix();

    const table = screen.getByRole("table", { name: "Hooks harness matrix" });
    const headerCells = table.querySelectorAll("thead tr > th");
    expect(headerCells).toHaveLength(columns.length + 5);
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

  it("toggles star on a hook row", () => {
    const onToggleStar = vi.fn();
    const props = { ...buildProps(), onToggleStar };
    render(<HooksMatrixView {...props} />);

    fireEvent.click(screen.getByRole("button", { name: "Star alpha-hook" }));
    expect(onToggleStar).toHaveBeenCalledWith("alpha-hook");
  });
});

function rowNames(): string[] {
  const table = screen.getByRole("table", { name: "Hooks harness matrix" });
  return within(table)
    .getAllByRole("row")
    .slice(1)
    .map((row) => within(row).getAllByText(/Alpha Hook|Zeta Hook/)[0].textContent ?? "");
}
