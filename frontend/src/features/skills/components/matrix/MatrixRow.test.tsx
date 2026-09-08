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
