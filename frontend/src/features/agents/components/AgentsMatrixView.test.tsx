import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AgentInventoryDto, AgentInventoryEntryDto } from "../api/types";
import { AgentsMatrixView } from "./AgentsMatrixView";

const columns: AgentInventoryDto["columns"] = [
  { harness: "codex", label: "Codex", logoKey: "codex", installed: true },
  { harness: "cursor", label: "Cursor", logoKey: "cursor", installed: true },
];

const entries: AgentInventoryEntryDto[] = [
  {
    ref: "shared:alpha",
    name: "Alpha Agent",
    description: "First agent",
    kind: "managed",
    harnessPath: null,
    bindings: [
      { harness: "codex", state: "enabled", detail: null },
      { harness: "cursor", state: "disabled", detail: null },
    ],
    actions: { canAdopt: false, canDelete: true },
  },
  {
    ref: "shared:zeta",
    name: "Zeta Agent",
    description: "Last agent",
    kind: "managed",
    harnessPath: null,
    bindings: [
      { harness: "codex", state: "disabled", detail: null },
      { harness: "cursor", state: "disabled", detail: null },
    ],
    actions: { canAdopt: false, canDelete: true },
  },
];

function renderMatrix() {
  const props = {
    entries,
    columns,
    pendingAgentKeys: new Set<string>(),
    pendingPerHarnessKeys: new Set<string>(),
    checkedRefs: new Set<string>(),
    onOpenDetail: vi.fn(),
    onToggleChecked: vi.fn(),
    onEnableHarness: vi.fn(),
    onDisableHarness: vi.fn(),
    onAdopt: vi.fn(),
  };
  render(<AgentsMatrixView {...props} />);
  return props;
}

describe("AgentsMatrixView", () => {
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

  it("renders a harness matrix with sortable rows by Agent name and coverage", () => {
    renderMatrix();

    const table = screen.getByRole("table", { name: "Agents harness matrix" });
    const headerCells = table.querySelectorAll("thead tr > th");
    expect(headerCells).toHaveLength(columns.length + 5);
    expect(table.querySelectorAll("tbody tr:first-child > td")).toHaveLength(headerCells.length);
    expect(rowNames()).toEqual(["Alpha Agent", "Zeta Agent"]);

    // Sort by Agent desc
    fireEvent.click(screen.getByRole("button", { name: "Sort by Agent" }));
    expect(rowNames()).toEqual(["Zeta Agent", "Alpha Agent"]);

    // Sort by Active
    fireEvent.click(screen.getByRole("button", { name: "Sort by Active" }));
    expect(rowNames()).toEqual(["Zeta Agent", "Alpha Agent"]);
  });

  it("renders star buttons and tag pills", () => {
    const onToggleStar = vi.fn();
    const onToggleStarredFilter = vi.fn();
    render(
      <AgentsMatrixView
        entries={[
          {
            ...entries[0],
            tags: ["starred", "backend"],
          },
          {
            ...entries[1],
            tags: ["ops"],
          },
        ]}
        columns={columns}
        pendingAgentKeys={new Set()}
        pendingPerHarnessKeys={new Set()}
        checkedRefs={new Set()}
        onOpenDetail={vi.fn()}
        onToggleChecked={vi.fn()}
        onEnableHarness={vi.fn()}
        onDisableHarness={vi.fn()}
        onAdopt={vi.fn()}
        onToggleStar={onToggleStar}
        starredFilterActive={true}
        onToggleStarredFilter={onToggleStarredFilter}
      />
    );

    expect(screen.getByText("backend")).toBeInTheDocument();
    expect(screen.getByText("ops")).toBeInTheDocument();

    const unstarBtn = screen.getByRole("button", { name: "Unstar Alpha Agent" });
    expect(unstarBtn).toBeInTheDocument();
    expect(unstarBtn.className).toContain("skill-star-btn--active");
    fireEvent.click(unstarBtn);
    expect(onToggleStar).toHaveBeenCalledWith("shared:alpha");

    const starBtn = screen.getByRole("button", { name: "Star Zeta Agent" });
    expect(starBtn).toBeInTheDocument();
    expect(starBtn.className).not.toContain("skill-star-btn--active");
    fireEvent.click(starBtn);
    expect(onToggleStar).toHaveBeenCalledWith("shared:zeta");

    const headerStarBtn = screen.getByRole("button", { name: "Filter by starred" });
    fireEvent.click(headerStarBtn);
    expect(onToggleStarredFilter).toHaveBeenCalled();
  });

  it("sorts by harness column", () => {
    renderMatrix();

    fireEvent.click(screen.getByRole("button", { name: "Sort by Codex" }));
    expect(rowNames()).toEqual(["Alpha Agent", "Zeta Agent"]);
  });
});

function rowNames(): string[] {
  const table = screen.getByRole("table", { name: "Agents harness matrix" });
  return within(table)
    .getAllByRole("row")
    .slice(1)
    .map((row) => within(row).getAllByText(/Alpha Agent|Zeta Agent/)[0].textContent ?? "");
}
