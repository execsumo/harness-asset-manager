import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { BulkAgentPopover } from "./BulkAgentPopover";

vi.mock("@radix-ui/react-popover", async () => {
  const actual = await vi.importActual<typeof import("@radix-ui/react-popover")>("@radix-ui/react-popover");
  return { ...actual, Portal: ({ children }: { children: ReactNode }) => <>{children}</> };
});

describe("BulkAgentPopover", () => {
  it("previews attach for a fixed-vocabulary multi-agent selection", async () => {
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

    fireEvent.click(screen.getByRole("button", { name: "Attach to agents" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Agent 1" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Agent 2" }));
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));

    await waitFor(() => expect(onApply).toHaveBeenCalledWith(["agent-1", "agent-2"], "attach"));
  });

  it("previews detach without offering free-form agent creation", async () => {
    const onApply = vi.fn(async () => undefined);
    render(
      <BulkAgentPopover
        knownAgents={[{ ref: "agent-1", name: "Agent 1" }]}
        onApply={onApply}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Attach to agents" }));
    expect(screen.queryByPlaceholderText(/agent/i)).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "detach" } });
    fireEvent.click(screen.getByRole("checkbox", { name: "Agent 1" }));
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));

    await waitFor(() => expect(onApply).toHaveBeenCalledWith(["agent-1"], "detach"));
  });
});
