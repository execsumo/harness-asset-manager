import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { HarnessCell } from "../../model/types";
import { SkillDetailHarnessMatrix } from "./SkillDetailHarnessMatrix";

const cells: HarnessCell[] = [
  { harness: "codex", label: "Codex", state: "disabled", interactive: true },
  { harness: "claude", label: "Claude", state: "enabled", interactive: true },
  { harness: "cursor", label: "Cursor", state: "found", interactive: false },
  { harness: "opencode", label: "OpenCode", state: "empty", interactive: false },
];

describe("SkillDetailHarnessMatrix", () => {
  it("renders toggle controls for interactive cells and guidance for found cells", () => {
    const onToggleCell = vi.fn();
    render(
      <SkillDetailHarnessMatrix
        skillName="Shared Audit"
        cells={cells}
        pendingToggleHarnesses={new Set()}
        pendingStructuralAction={null}
        onToggleCell={onToggleCell}
      />,
    );

    const enableButton = screen.getByRole("button", { name: "Enable Shared Audit for Codex" });
    const disableButton = screen.getByRole("button", { name: "Disable Shared Audit for Claude" });
    expect(enableButton).toBeInTheDocument();
    expect(enableButton).toHaveClass("action-pill--accent");
    expect(disableButton).toBeInTheDocument();
    expect(disableButton).toHaveClass("action-pill--danger");
    expect(screen.getByRole("group", { name: "Codex, Disabled" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Claude, Enabled" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Cursor, Found in harness" })).toBeInTheDocument();
    expect(screen.getByText("Adopt this skill to manage it")).toBeInTheDocument();
    expect(screen.getByText("Found in harness")).toBeInTheDocument();
    expect(screen.queryByText(/^Enabled$/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Disabled$/)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Not present$/)).not.toBeInTheDocument();

    fireEvent.click(enableButton);
    expect(onToggleCell).toHaveBeenCalledWith(cells[0]);
  });

  it("shows each scoped Hermes Bot inside one Hermes binding", () => {
    const { container } = render(
      <SkillDetailHarnessMatrix
        skillName="Shared Audit"
        cells={[{ harness: "hermes", label: "Hermes Agent", logoKey: "hermes", state: "enabled", interactive: true }]}
        linkedTargets={["hermes:coder", "hermes:reviewer"]}
        pendingToggleHarnesses={new Set()}
        pendingStructuralAction={null}
        onToggleCell={vi.fn()}
      />,
    );

    expect(screen.getByText("Coder")).toBeInTheDocument();
    expect(screen.getByText("Reviewer")).toBeInTheDocument();
    expect(screen.getByLabelText("Hermes Bots: Coder, Reviewer")).toBeInTheDocument();
    expect(container.querySelectorAll("img")).toHaveLength(1);
  });

  it("does not add a Bot label for the unscoped Hermes target", () => {
    const { container } = render(
      <SkillDetailHarnessMatrix
        skillName="Default Profile Skill"
        cells={[{ harness: "hermes", label: "Hermes Agent", logoKey: "hermes", state: "enabled", interactive: true }]}
        linkedTargets={["hermes"]}
        pendingToggleHarnesses={new Set()}
        pendingStructuralAction={null}
        onToggleCell={vi.fn()}
      />,
    );

    expect(screen.getByRole("group", { name: "Hermes Agent, Enabled" })).toBeInTheDocument();
    expect(screen.queryByText("Hermes Bots:")).not.toBeInTheDocument();
    expect(container.querySelectorAll("img")).toHaveLength(1);
  });

  it("names the originating Bot of an unmanaged adoption candidate", () => {
    // An unmanaged copy has no binding yet, so the Bot is only knowable from
    // where it was found.
    render(
      <SkillDetailHarnessMatrix
        skillName="Bot Authored Skill"
        cells={[{ harness: "hermes", label: "Hermes Agent", logoKey: "hermes", state: "found", interactive: false }]}
        linkedTargets={[]}
        locations={[{ harness: "hermes:coder" }]}
        pendingToggleHarnesses={new Set()}
        pendingStructuralAction={null}
        onToggleCell={vi.fn()}
      />,
    );

    expect(screen.getByText("Coder")).toBeInTheDocument();
    expect(screen.getByLabelText("Hermes Bots: Coder")).toBeInTheDocument();
  });

  it("distinguishes two same-named candidates from different Bots", () => {
    render(
      <SkillDetailHarnessMatrix
        skillName="Bot Authored Skill"
        cells={[{ harness: "hermes", label: "Hermes Agent", logoKey: "hermes", state: "found", interactive: false }]}
        linkedTargets={[]}
        locations={[{ harness: "hermes:coder" }, { harness: "hermes:reviewer" }]}
        pendingToggleHarnesses={new Set()}
        pendingStructuralAction={null}
        onToggleCell={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("Hermes Bots: Coder, Reviewer")).toBeInTheDocument();
  });
});
