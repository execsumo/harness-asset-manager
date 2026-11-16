import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { HarnessColumn, SkillListRow } from "../../model/types";
import { MatrixRow } from "./MatrixRow";

const harnessColumns: HarnessColumn[] = [
  { harness: "hermes", label: "Hermes Agent", logoKey: "hermes", installed: true },
];

function candidate(linkedTargets: string[]): SkillListRow {
  return {
    skillRef: `unmanaged:${linkedTargets[0]}`,
    name: "Duplicate Candidate",
    description: "Created by a Bot",
    displayStatus: "Unmanaged",
    tags: [],
      agents: [],
    actions: { canManage: true, canStopManaging: false, canDelete: false },
    cells: [{ harness: "hermes", label: "Hermes Agent", logoKey: "hermes", state: "found", interactive: false }],
    linkedTargets,
    conformance: [],
  };
}

describe("MatrixRow Hermes Bot attribution", () => {
  it("distinguishes same-named candidates from different Bots", () => {
    render(
      <table>
        <tbody>
          {[candidate(["hermes:coder"]), candidate(["hermes:reviewer"])].map((row) => (
            <MatrixRow
              key={row.skillRef}
              row={row}
              harnessColumns={harnessColumns}
              checked={false}
              selected={false}
              pendingToggleKeys={new Set()}
              pendingStructuralActions={new Map()}
              onOpenSkill={vi.fn()}
              onToggleChecked={vi.fn()}
              onToggleCell={vi.fn()}
            />
          ))}
        </tbody>
      </table>,
    );

    expect(screen.getByLabelText("Hermes Bots: Coder")).toBeInTheDocument();
    expect(screen.getByLabelText("Hermes Bots: Reviewer")).toBeInTheDocument();
  });
});

describe("MatrixRow agent tags", () => {
  const withAgent: SkillListRow = {
    ...candidate(["hermes:coder"]),
    agents: [{ ref: "agent:reviewer", name: "reviewer", role: "qa" }],
  } as SkillListRow;

  function renderRow(showAgents?: boolean) {
    return render(
      <table>
        <tbody>
          <MatrixRow
            row={withAgent}
            harnessColumns={harnessColumns}
            checked={false}
            selected={false}
            pendingToggleKeys={new Set()}
            pendingStructuralActions={new Map()}
            onOpenSkill={vi.fn()}
            onToggleChecked={vi.fn()}
            onToggleCell={vi.fn()}
            showAgents={showAgents}
          />
        </tbody>
      </table>,
    );
  }

  it("shows agent chips by default", () => {
    renderRow();
    expect(screen.getByText("qa:reviewer")).toBeInTheDocument();
  });

  it("hides agent chips when the setting is off", () => {
    renderRow(false);
    expect(screen.queryByText("qa:reviewer")).not.toBeInTheDocument();
  });
});
