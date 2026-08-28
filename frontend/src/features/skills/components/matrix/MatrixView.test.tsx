import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { HarnessColumn, SkillListRow } from "../../model/types";
import { MatrixView } from "./MatrixView";

const harnessColumns: HarnessColumn[] = [
  { harness: "codex", label: "Codex", logoKey: "codex", installed: true },
  { harness: "cursor", label: "Cursor", logoKey: "cursor", installed: true },
];

const rows: SkillListRow[] = [
  {
    skillRef: "shared:alpha",
    name: "Alpha",
    description: "First skill",
    displayStatus: "Managed",
    tags: ["starred"],
    actions: { canManage: false, canStopManaging: true, canDelete: true },
    conformance: [],
    cells: [
      { harness: "codex", label: "Codex", logoKey: "codex", state: "enabled", interactive: true },
      { harness: "cursor", label: "Cursor", logoKey: "cursor", state: "disabled", interactive: true },
    ],
  },
  {
    skillRef: "shared:zeta",
    name: "Zeta",
    description: "Last skill",
    displayStatus: "Managed",
    tags: ["core"],
    actions: { canManage: false, canStopManaging: true, canDelete: true },
    conformance: [],
    cells: [
      { harness: "codex", label: "Codex", logoKey: "codex", state: "disabled", interactive: true },
      { harness: "cursor", label: "Cursor", logoKey: "cursor", state: "disabled", interactive: true },
    ],
  },
];

function renderMatrix() {
  const props = {
    rows,
    harnessColumns,
    checkedRefs: new Set<string>(),
    selectedSkillRef: null,
    pendingToggleKeys: new Set<string>(),
    onOpenSkill: vi.fn(),
    onToggleChecked: vi.fn(),
    onToggleCell: vi.fn(),
    onToggleStar: vi.fn(),
  };
  render(<MatrixView {...props} />);
  return props;
}

describe("Skills MatrixView", () => {
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

    const table = screen.getByRole("table", { name: "Skills harness matrix" });
    // Column widths come from the header cells, so header and body have to
    // agree cell-for-cell (see MatrixTable.tsx).
    const headerCells = table.querySelectorAll("thead tr > th");
    expect(headerCells).toHaveLength(harnessColumns.length + 5);
    expect(table.querySelectorAll("tbody tr:first-child > td")).toHaveLength(headerCells.length);
    expect(rowNames()).toEqual(["Alpha", "Zeta"]);

    fireEvent.click(screen.getByRole("button", { name: "Sort by Skill" }));
    expect(rowNames()).toEqual(["Zeta", "Alpha"]);
  });

  it("toggles harness cells", () => {
    const { onToggleCell } = renderMatrix();

    fireEvent.click(screen.getByRole("button", { name: "Disable Alpha on Codex" }));

    expect(onToggleCell).toHaveBeenCalledWith(rows[0], rows[0].cells[0]);
  });

  it("renders the star toggle in its own column after the skill name and before harness columns", () => {
    renderMatrix();

    const table = screen.getByRole("table", { name: "Skills harness matrix" });
    const headerCells = table.querySelectorAll("thead tr > th");
    expect(headerCells[0].className).toContain("matrix-table__th--checkbox");
    expect(headerCells[1].className).toContain("matrix-table__th--identity");
    expect(headerCells[2].className).toContain("matrix-table__th--star");
    expect(headerCells[3].className).toContain("matrix-table__th--harness");

    const firstRow = table.querySelector("tbody tr:first-child") as HTMLElement;
    const cells = firstRow.querySelectorAll("td");
    expect(cells[0].className).toContain("matrix-table__cell--checkbox");
    expect(cells[1].className).toContain("matrix-table__cell--identity");
    expect(cells[2].className).toContain("matrix-table__cell--star");
    expect(cells[3].className).toContain("matrix-table__cell--harness");

    const starBtn = cells[2].querySelector("button");
    expect(starBtn?.getAttribute("aria-label")).toBe("Unstar Alpha");
    expect(starBtn?.className).toContain("skill-star-btn--active");
    // The identity cell does not embed a star button.
    expect(cells[1].querySelector(".skill-star-btn")).toBeNull();

    // The second row (unstarred) visibly renders the empty outline star button
    const secondRow = table.querySelector("tbody tr:nth-child(2)") as HTMLElement;
    const secondRowStarBtn = secondRow.querySelectorAll("td")[2].querySelector("button");
    expect(secondRowStarBtn).not.toBeNull();
    expect(secondRowStarBtn?.getAttribute("aria-label")).toBe("Star Zeta");
    expect(secondRowStarBtn?.className).not.toContain("skill-star-btn--active");
  });

  it("calls onToggleStar when clicking the row star button", () => {
    const { onToggleStar } = renderMatrix();

    const starZetaBtn = screen.getByRole("button", { name: "Star Zeta" });
    fireEvent.click(starZetaBtn);

    expect(onToggleStar).toHaveBeenCalledWith("shared:zeta");
  });

  it("renders the star header button with tooltip and toggles starred filter on click", () => {
    const onToggleStarredFilter = vi.fn();
    render(
      <MatrixView
        rows={rows}
        harnessColumns={harnessColumns}
        checkedRefs={new Set()}
        selectedSkillRef={null}
        pendingToggleKeys={new Set()}
        onOpenSkill={vi.fn()}
        onToggleChecked={vi.fn()}
        onToggleCell={vi.fn()}
        onToggleStarredFilter={onToggleStarredFilter}
        starredFilterActive={false}
      />,
    );

    const headerStarBtn = screen.getByRole("button", { name: "Filter by starred" });
    expect(headerStarBtn).toBeInTheDocument();
    expect(headerStarBtn).toHaveAttribute("aria-pressed", "false");
    expect(headerStarBtn).not.toHaveAttribute("data-active");

    fireEvent.click(headerStarBtn);
    expect(onToggleStarredFilter).toHaveBeenCalledTimes(1);
  });

  it("renders active state on the star header button when starredFilterActive is true", () => {
    render(
      <MatrixView
        rows={rows}
        harnessColumns={harnessColumns}
        checkedRefs={new Set()}
        selectedSkillRef={null}
        pendingToggleKeys={new Set()}
        onOpenSkill={vi.fn()}
        onToggleChecked={vi.fn()}
        onToggleCell={vi.fn()}
        starredFilterActive={true}
      />,
    );

    const headerStarBtn = screen.getByRole("button", { name: "Filter by starred" });
    expect(headerStarBtn).toHaveAttribute("aria-pressed", "true");
    expect(headerStarBtn).toHaveAttribute("data-active", "true");
  });

  it("keeps an undetected harness visible but not actionable", () => {
    render(
      <MatrixView
        rows={[{
          ...rows[0],
          conformance: [],
    cells: [{
            harness: "opencode",
            label: "OpenCode",
            logoKey: "opencode",
            state: "disabled",
            interactive: false,
          }],
        }]}
        harnessColumns={[{ harness: "opencode", label: "OpenCode", logoKey: "opencode", installed: false }]}
        checkedRefs={new Set()}
        selectedSkillRef={null}
        pendingToggleKeys={new Set()}
        onOpenSkill={vi.fn()}
        onToggleChecked={vi.fn()}
        onToggleCell={vi.fn()}
      />,
    );

    expect(screen.queryByRole("button", { name: "Enable Alpha on OpenCode" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("OpenCode unavailable")).toHaveTextContent("—");
  });
});

function rowNames(): string[] {
  const table = screen.getByRole("table", { name: "Skills harness matrix" });
  return within(table)
    .getAllByRole("row")
    .slice(1)
    .map((row) => within(row).getAllByText(/Alpha|Zeta/)[0].textContent ?? "");
}
