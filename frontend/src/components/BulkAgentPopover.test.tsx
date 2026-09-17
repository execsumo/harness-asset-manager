import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { BulkAgentPopover } from "./BulkAgentPopover";

vi.mock("@radix-ui/react-popover", async () => {
  const actual = await vi.importActual<typeof import("@radix-ui/react-popover")>("@radix-ui/react-popover");
  return { ...actual, Portal: ({ children }: { children: ReactNode }) => <>{children}</> };
});

describe("BulkAgentPopover", () => {
  it("applies attach for a fixed-vocabulary multi-agent selection", async () => {
    const onApply = vi.fn(async () => undefined);
    render(
      <BulkAgentPopover
        knownAgents={[
          { ref: "agent-1", name: "Agent 1" },
          { ref: "agent-2", name: "Agent 2" },
        ]}
        onApply={onApply}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Agents" }));
    expect(screen.getByRole("heading", { name: "Agents" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Preview" })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("checkbox", { name: "Agent 1" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Agent 2" }));
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));

    await waitFor(() => expect(onApply).toHaveBeenCalledWith(["agent-1", "agent-2"], "attach"));
  });

  it("applies detach without offering free-form agent creation", async () => {
    const onApply = vi.fn(async () => undefined);
    render(
      <BulkAgentPopover
        knownAgents={[{ ref: "agent-1", name: "Agent 1" }]}
        onApply={onApply}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Agents" }));
    expect(screen.queryByPlaceholderText(/agent/i)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Detach" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Agent 1" }));
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));

    await waitFor(() => expect(onApply).toHaveBeenCalledWith(["agent-1"], "detach"));
  });
});
