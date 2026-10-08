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
  useHermesOptionsQuery: () => ({
    data: { providers: [{ id: "test-provider", models: ["test/model"] }] },
  }),
}));

vi.mock("../../settings/public", () => ({
  useSettingsQuery: () => ({
    data: mockSettingsData,
  }),
}));

vi.mock("../../mcp/public", () => ({
  useMcpInventoryQuery: () => ({
    data: {
      entries: [{ kind: "managed", name: "dossier", displayName: "Dossier", spec: {} }],
    },
  }),
}));

vi.mock("../../skills/public", () => ({
  useSkillsListQuery: () => ({
    data: {
      rows: [
        { skillRef: "shared:review", name: "Review", displayStatus: "Managed", tags: ["quality"] },
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

  it("orders the frontmatter fields the way Agent Details reads them", () => {
    render(<CreateAgentDialog open={true} onOpenChange={vi.fn()} />);

    const labels = Array.from(
      document.querySelectorAll(".dialog-fieldset .form-field__label"),
      // The label span also carries a "Required" badge; only the field name matters here.
      (node) => node.firstChild?.textContent?.trim(),
    );

    // The dialog follows the detail editor's order, omitting detail-only fields.
    expect(labels).toEqual([
      "Agent Name",
      "Role",
      "Description",
      "Harness",
      "Model",
      "Effort",
      "Skills",
      "MCP Servers",
      "Disallowed Tools",
      "Memory",
      "Max Turns",
      "Hermes Provider",
    ]);
  });

  it("puts the format and the key a field writes in a help line, not in its label", () => {
    render(<CreateAgentDialog open={true} onOpenChange={vi.fn()} />);

    const hintFor = (label: string) =>
      document
        .querySelector(`[aria-label="${label}"]`)
        ?.closest(".form-field")
        ?.querySelector(".form-field__hint")?.textContent;

    expect(hintFor("MCP Servers")).toContain("Claude/Codex");
    expect(hintFor("Disallowed Tools")).toContain("disallowedTools");
    // The help line sits inside the label element, so each input carries its own
    // aria-label to keep that guidance out of the accessible name.
    expect(screen.getByRole("textbox", { name: "Disallowed Tools" })).toBeInTheDocument();
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

  it("carries contract fields and selected harnesses in the create body, and omits unset keys", async () => {
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
    fireEvent.change(screen.getByPlaceholderText("Describe this agent's role"), {
      target: { value: "Systems designer" },
    });
    fireEvent.change(screen.getByLabelText("Harness"), {
      target: { value: "claude" },
    });
    fireEvent.change(
      screen.getByPlaceholderText("Describe the agent's purpose and functionality..."),
      { target: { value: "Designs systems" } },
    );
    fireEvent.change(screen.getByPlaceholderText("System instructions..."), {
      target: { value: "Think deeply about architectures." },
    });
    fireEvent.change(screen.getByLabelText("Effort"), {
      target: { value: "high" },
    });
    fireEvent.change(screen.getByLabelText("Memory"), {
      target: { value: "project" },
    });
    const mcpServersField = screen.getByRole("combobox", { name: "MCP Servers" });
    fireEvent.change(mcpServersField, { target: { value: "Dossier" } });
    fireEvent.mouseDown(await screen.findByRole("option", { name: /Dossier.*dossier/ }));

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
      role: "Systems designer",
      harness: "claude",
      effort: "high",
      memory: "project",
      mcpServers: ["dossier"],
      harnesses: ["claude"],
    });

    // Unset contract keys are omitted entirely, not sent as empty strings
    expect(payload).not.toHaveProperty("model");
    expect(payload).not.toHaveProperty("tools");
    expect(payload).not.toHaveProperty("skills");
    expect(payload).not.toHaveProperty("disallowedTools");
    expect(payload).not.toHaveProperty("maxTurns");
    expect(payload).not.toHaveProperty("isolation");
    expect(payload).not.toHaveProperty("background");
    expect(payload).not.toHaveProperty("mode");
    expect(payload).not.toHaveProperty("spawning");
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

  it("offers Hermes providers as a dropdown and only sends the shared Model", () => {
    mockSettingsData = { autoAdoptHarnesses: { agents: [] } };
    mockMutateAsync.mockResolvedValueOnce({ name: "Hermes Agent", ok: true, harnessFailures: [] });

    render(<CreateAgentDialog open={true} onOpenChange={vi.fn()} />);
    expect(screen.getByText(/HAM-managed Bots are addressed as hermes -p <name>/i)).toBeInTheDocument();
    expect(screen.getByText(/do not install PATH wrapper scripts/i)).toBeInTheDocument();
    expect(screen.getByText(/External CLI backends/i)).toBeInTheDocument();
    expect(screen.getByText(/Codex app-server subprocess/i)).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText("e.g. Code Reviewer"), {
      target: { value: "Hermes Agent" },
    });
    fireEvent.change(
      screen.getByPlaceholderText("Describe the agent's purpose and functionality..."),
      { target: { value: "Runs through Hermes" } },
    );
    fireEvent.change(screen.getByPlaceholderText("System instructions..."), {
      target: { value: "Use the configured profile." },
    });
    const provider = screen.getByRole("combobox", { name: "Hermes Provider" }) as HTMLSelectElement;
    expect(Array.from(provider.options).map((option) => option.value)).toEqual(["", "test-provider"]);
    fireEvent.change(provider, { target: { value: "test-provider" } });

    fireEvent.click(screen.getByRole("button", { name: "Create Agent" }));

    expect(mockMutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ hermesProvider: "test-provider" }),
    );
    expect(mockMutateAsync.mock.calls[0][0]).not.toHaveProperty("hermesModel");
  });

  it("renders the remaining fixed-vocabulary fields as dropdowns", () => {
    // The surviving pickers share the same native select behavior.
    render(<CreateAgentDialog open={true} onOpenChange={vi.fn()} />);

    for (const label of ["Harness", "Effort", "Memory", "Hermes Provider"]) {
      expect(screen.getByRole("combobox", { name: label })).toBeInTheDocument();
    }

    const memory = screen.getByRole("combobox", { name: "Memory" }) as HTMLSelectElement;
    expect(Array.from(memory.options).map((option) => option.value)).toEqual([
      "",
      "user",
      "project",
      "local",
    ]);
  });

  it("offers Harness as the discovered harnesses, marking the uninstalled ones", () => {
    render(<CreateAgentDialog open={true} onOpenChange={vi.fn()} />);

    const harness = screen.getByRole("combobox", { name: "Harness" }) as HTMLSelectElement;
    const options = Array.from(harness.options).map((option) => [option.value, option.text]);

    // Hermes is in the inventory but not installed here. It stays pickable and marked:
    // an agent is often authored on one machine for another.
    expect(options).toEqual([
      ["", "(none)"],
      ["claude", "Claude"],
      ["cursor", "Cursor"],
      ["hermes", "Hermes — not installed here"],
    ]);
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

  it("allows selecting a skill tag collection to attach all matching skills", () => {
    render(<CreateAgentDialog open={true} onOpenChange={vi.fn()} />);

    const tagBtn = screen.getByRole("button", { name: "quality" });
    expect(tagBtn).toBeInTheDocument();
    fireEvent.click(tagBtn);

    expect(screen.getByText("Review")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "quality" })).not.toBeInTheDocument();
  });
});
