import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AgentInventoryDto } from "../api/types";
import { CreateAgentDialog } from "./CreateAgentDialog";

const mockMutateAsync = vi.fn();
const mockToast = vi.fn();

interface MockSettings {
  autoAdoptHarnesses?: { agents?: string[] };
}

const settingsWithDefaults = (): MockSettings => ({
  autoAdoptHarnesses: { agents: ["claude", "cursor"] },
});

// Hermes is deliberately uninstalled: it must render but stay unselectable.
const inventory = (): AgentInventoryDto => ({
  columns: [
    { harness: "claude", label: "Claude", logoKey: "claude", installed: true },
    { harness: "cursor", label: "Cursor", logoKey: "cursor", installed: true },
    { harness: "hermes", label: "Hermes", logoKey: "hermes", installed: false },
  ],
  entries: [
    {
      ref: "existing-agent",
      name: "Existing Agent",
      kind: "managed",
      description: "already exists",
      harnessPath: null,
      bindings: [],
      actions: { canAdopt: false, canDelete: true },
    },
  ],
  issues: [],
});

let mockSettingsData: MockSettings = settingsWithDefaults();
let mockInventoryData: AgentInventoryDto = inventory();

vi.mock("../../../components/Toast", () => ({
  useToast: () => ({ toast: mockToast }),
}));

vi.mock("../api/queries", () => ({
  useCreateAgentMutation: () => ({
    mutateAsync: mockMutateAsync,
    isPending: false,
  }),
  useAgentsInventoryQuery: () => ({
    data: mockInventoryData,
  }),
}));

vi.mock("../../settings/public", () => ({
  useSettingsQuery: () => ({
    data: mockSettingsData,
  }),
}));

vi.mock("../../skills/public", () => ({
  useSkillsListQuery: () => ({
    data: {
      rows: [
        { skillRef: "shared:review", name: "Review", displayStatus: "Managed" },
      ],
    },
  }),
}));

describe("CreateAgentDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSettingsData = settingsWithDefaults();
    mockInventoryData = inventory();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("preselects harnesses from configured auto-adopt defaults", () => {
    mockSettingsData = {
      autoAdoptHarnesses: { agents: ["claude", "cursor"] },
    };

    render(<CreateAgentDialog open={true} onOpenChange={vi.fn()} />);

    // Claude and Cursor are enabled / selected
    const claudeBtn = screen.getByRole("button", { name: /disable claude/i });
    expect(claudeBtn).toHaveAttribute("aria-pressed", "true");

    const cursorBtn = screen.getByRole("button", { name: /disable cursor/i });
    expect(cursorBtn).toHaveAttribute("aria-pressed", "true");

    // Hermes is not installed -> disabled
    const hermesBtn = screen.getByRole("button", { name: /hermes is not installed/i });
    expect(hermesBtn).toBeDisabled();

    // The inline empty note is NOT shown when harnesses are selected
    expect(
      screen.queryByText(/This agent won't be available in any harness yet/i),
    ).not.toBeInTheDocument();
  });

  it("preselects nothing when the configured list is empty, and shows the inline note", () => {
    mockSettingsData = {
      autoAdoptHarnesses: { agents: [] },
    };

    render(<CreateAgentDialog open={true} onOpenChange={vi.fn()} />);

    // Claude and Cursor are not selected
    const claudeBtn = screen.getByRole("button", { name: /enable claude/i });
    expect(claudeBtn).toHaveAttribute("aria-pressed", "false");

    const cursorBtn = screen.getByRole("button", { name: /enable cursor/i });
    expect(cursorBtn).toHaveAttribute("aria-pressed", "false");

    // Inline note is visible
    expect(
      screen.getByText(
        "This agent won't be available in any harness yet. Pick one above, or set defaults in Settings → Auto-adopt.",
      ),
    ).toBeInTheDocument();

    // Selecting a harness removes the hint
    fireEvent.click(claudeBtn);
    expect(
      screen.queryByText(/This agent won't be available in any harness yet/i),
    ).not.toBeInTheDocument();

    // Deselecting brings it back
    fireEvent.click(screen.getByRole("button", { name: /disable claude/i }));
    expect(
      screen.getByText(
        "This agent won't be available in any harness yet. Pick one above, or set defaults in Settings → Auto-adopt.",
      ),
    ).toBeInTheDocument();
  });

  it("carries contract fields and selected harnesses in the create body, and omits unset keys", () => {
    mockSettingsData = {
      autoAdoptHarnesses: { agents: ["claude"] },
    };
    mockMutateAsync.mockResolvedValueOnce({
      name: "Architect",
      ok: true,
      harnessFailures: [],
    });

    render(<CreateAgentDialog open={true} onOpenChange={vi.fn()} />);

    fireEvent.change(screen.getByPlaceholderText("e.g. Code Reviewer"), {
      target: { value: "Architect" },
    });
    fireEvent.change(
      screen.getByPlaceholderText("Describe the agent's purpose and functionality..."),
      { target: { value: "Designs systems" } },
    );
    fireEvent.change(screen.getByPlaceholderText("System instructions..."), {
      target: { value: "Think deeply about architectures." },
    });
    fireEvent.change(screen.getByLabelText("Color"), {
      target: { value: "purple" },
    });
    fireEvent.change(screen.getByLabelText("Effort"), {
      target: { value: "high" },
    });

    // Submit the form
    const submitBtn = screen.getByRole("button", { name: "Create Agent" });
    expect(submitBtn).not.toBeDisabled();
    fireEvent.click(submitBtn);

    expect(mockMutateAsync).toHaveBeenCalledTimes(1);
    const payload = mockMutateAsync.mock.calls[0][0];
    expect(payload).toEqual({
      name: "Architect",
      description: "Designs systems",
      prompt: "Think deeply about architectures.",
      color: "purple",
      effort: "high",
      harnesses: ["claude"],
    });

    // Unset contract keys are omitted entirely, not sent as empty strings
    expect(payload).not.toHaveProperty("model");
    expect(payload).not.toHaveProperty("tools");
    expect(payload).not.toHaveProperty("skills");
    expect(payload).not.toHaveProperty("allowedSubagents");
    expect(payload).not.toHaveProperty("maxTurns");
    expect(payload).not.toHaveProperty("isolation");
  });

  it("blocks a duplicate name before any fetch", () => {
    render(<CreateAgentDialog open={true} onOpenChange={vi.fn()} />);

    fireEvent.change(screen.getByPlaceholderText("e.g. Code Reviewer"), {
      target: { value: "Existing Agent" },
    });
    fireEvent.change(
      screen.getByPlaceholderText("Describe the agent's purpose and functionality..."),
      { target: { value: "Some description" } },
    );
    fireEvent.change(screen.getByPlaceholderText("System instructions..."), {
      target: { value: "Some prompt instructions." },
    });

    // Error banner / inline message is displayed
    expect(
      screen.getByText('An agent named "existing-agent" already exists.'),
    ).toBeInTheDocument();

    // Submit button is disabled
    const submitBtn = screen.getByRole("button", { name: "Create Agent" });
    expect(submitBtn).toBeDisabled();

    // Even if form submit event is triggered, no mutation occurs
    const form = submitBtn.closest("form");
    expect(form).not.toBeNull();
    fireEvent.submit(form!);

    expect(mockMutateAsync).not.toHaveBeenCalled();
  });

  it("surfaces a partial harness failure in the response rather than swallowing it", async () => {
    const onOpenChange = vi.fn();
    mockSettingsData = {
      autoAdoptHarnesses: { agents: ["claude"] },
    };
    mockMutateAsync.mockResolvedValueOnce({
      name: "Specialist",
      ok: false,
      harnessFailures: [
        { harness: "cursor", error: "harness does not support agents: cursor" },
      ],
    });

    render(<CreateAgentDialog open={true} onOpenChange={onOpenChange} />);

    fireEvent.change(screen.getByPlaceholderText("e.g. Code Reviewer"), {
      target: { value: "Specialist" },
    });
    fireEvent.change(
      screen.getByPlaceholderText("Describe the agent's purpose and functionality..."),
      { target: { value: "Specialized tasks" } },
    );
    fireEvent.change(screen.getByPlaceholderText("System instructions..."), {
      target: { value: "Do specialized work." },
    });

    const submitBtn = screen.getByRole("button", { name: "Create Agent" });
    fireEvent.click(submitBtn);

    await vi.waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalledTimes(1);
    });

    // Toast surfaces creation and named harness failure
    expect(mockToast).toHaveBeenCalledWith(
      expect.stringMatching(/Created agent Specialist, but failed to bind to: cursor/),
    );

    // Dialog closes because agent was successfully created
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});
