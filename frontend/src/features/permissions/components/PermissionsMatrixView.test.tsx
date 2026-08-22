import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  PermissionInventoryColumnDto,
  PermissionInventoryEntryDto,
} from "../api/management-types";
import { PermissionsMatrixView } from "./PermissionsMatrixView";

const columns: PermissionInventoryColumnDto[] = [
  { harness: "codex", label: "Codex", logoKey: "codex", installed: true, configPresent: true, permissionsWritable: true },
  { harness: "cursor", label: "Cursor", logoKey: "cursor", installed: true, configPresent: true, permissionsWritable: true },
];

const entries: PermissionInventoryEntryDto[] = [
  {
    id: "alpha-rule",
    displayName: "Alpha Rule",
    kind: "managed",
    canEnable: true,
    enabledStatus: "enabled",
    sightings: [
      { harness: "codex", state: "managed" },
      { harness: "cursor", state: "missing" },
    ],
  },
  {
    id: "zeta-rule",
    displayName: "Zeta Rule",
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
    pendingPermissionKeys: new Set<string>(),
    pendingPerHarnessKeys: new Set<string>(),
    checkedIds: new Set<string>(),
    onOpenDetail: vi.fn(),
    onToggleChecked: vi.fn(),
    onEnableHarness: vi.fn(),
    onDisableHarness: vi.fn(),
    onAdopt: vi.fn(),
  };
  render(<PermissionsMatrixView {...props} />);
  return props;
}

describe("PermissionsMatrixView", () => {
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

    const table = screen.getByRole("table", { name: "Permissions harness matrix" });
    const headerCells = table.querySelectorAll("thead tr > th");
    expect(headerCells).toHaveLength(columns.length + 4);
    expect(table.querySelectorAll("tbody tr:first-child > td")).toHaveLength(headerCells.length);
    expect(rowNames()).toEqual(["Alpha Rule", "Zeta Rule"]);

    // Sort desc by name
    fireEvent.click(screen.getByRole("button", { name: "Sort by Rule" }));
    expect(rowNames()).toEqual(["Zeta Rule", "Alpha Rule"]);

    // Sort by Active
    fireEvent.click(screen.getByRole("button", { name: "Sort by Active" }));
    expect(rowNames()).toEqual(["Zeta Rule", "Alpha Rule"]);
  });

  it("sorts by harness column", () => {
    renderMatrix();

    fireEvent.click(screen.getByRole("button", { name: "Sort by Codex" }));
    expect(rowNames()).toEqual(["Alpha Rule", "Zeta Rule"]);
  });

  it("renders a checkbox for every row and toggles selection", () => {
    const props = renderMatrix();

    const checkboxes = screen.getAllByRole("checkbox");
    expect(checkboxes).toHaveLength(entries.length);

    fireEvent.click(screen.getByRole("checkbox", { name: "Select Alpha Rule" }));
    expect(props.onToggleChecked).toHaveBeenCalledWith("alpha-rule");
  });
});

function rowNames(): string[] {
  const table = screen.getByRole("table", { name: "Permissions harness matrix" });
  return within(table)
    .getAllByRole("row")
    .slice(1)
    .map((row) => within(row).getAllByText(/Alpha Rule|Zeta Rule/)[0].textContent ?? "");
}
