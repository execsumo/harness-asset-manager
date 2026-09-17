import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { okJson } from "./fetch";
import { renderWithAppProviders } from "./render";

import { SkillsWorkspaceSessionProvider } from "../features/skills/model/session";
import SkillsWorkspacePage from "../features/skills/screens/SkillsWorkspacePage";

const fetchMock = vi.fn();

const allAgents = [
  { ref: "agent-1", name: "Agent 1" },
  { ref: "agent-2", name: "Agent 2" },
  { ref: "agent-bad", name: "Agent Bad" },
];

function skillsPayload() {
  return {
    agentOptions: allAgents,
    harnessColumns: [
      { harness: "claude", label: "Claude Code", logoKey: "claude", installed: true },
      { harness: "codex", label: "Codex", logoKey: "codex", installed: true },
    ],
    summary: { total: 3, managed: 2, unmanaged: 1, overridden: 0, pending: 0, errored: 0 },
    rows: [
      {
        skillRef: "shared:managed-1",
        name: "Managed 1",
        description: "A managed skill",
        displayStatus: "Managed",
        tags: [],
        agents: allAgents,
        actions: { canManage: false, canStopManaging: true, canDelete: true },
        conformance: [],
        cells: [
          { harness: "claude", label: "Claude Code", logoKey: "claude", state: "disabled", interactive: true },
          { harness: "codex", label: "Codex", logoKey: "codex", state: "enabled", interactive: true },
        ],
      },
      {
        skillRef: "shared:managed-2",
        name: "Managed 2",
        description: "Another managed skill",
        displayStatus: "Managed",
        tags: [],
        agents: allAgents,
        actions: { canManage: false, canStopManaging: true, canDelete: true },
        conformance: [],
        cells: [
          { harness: "claude", label: "Claude Code", logoKey: "claude", state: "disabled", interactive: true },
          { harness: "codex", label: "Codex", logoKey: "codex", state: "disabled", interactive: true },
        ],
      },
      {
        skillRef: "unmanaged:untracked",
        name: "Untracked",
        description: "An unmanaged skill",
        displayStatus: "Unmanaged",
        tags: [],
        agents: allAgents,
        actions: { canManage: true, canStopManaging: false, canDelete: true },
        conformance: [],
        cells: [
          { harness: "claude", label: "Claude Code", logoKey: "claude", state: "found", interactive: false },
          { harness: "codex", label: "Codex", logoKey: "codex", state: "empty", interactive: false },
        ],
      },
    ],
  };
}

describe("Agent Bulk Attach UI Pressure Test", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
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

  it("drives bulk attach across managed and unmanaged skills, multiple agents, and a failing agent", async () => {
    const written: Record<string, string[]> = {
      "agent-1": [],
      "agent-2": ["existing-skill"],
      "agent-bad": [],
    };

    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/skills/attach-agents") && init?.method === "POST") {
        const body = JSON.parse(String(init.body)) as {
          skillRefs: string[];
          agentRefs: string[];
          mode: "attach" | "detach";
          dryRun: boolean;
        };
        expect(body.skillRefs).toEqual(["shared:managed-1", "shared:managed-2"]);
        expect(body.agentRefs).toEqual(["agent-1", "agent-2", "agent-bad"]);

        const response = {
          changed: ["agent-1", "agent-2"],
          skipped: [{ ref: "agent-bad", reason: "agent not writable" }],
          autoEnabled: [
            { skillRef: "shared:managed-1", harness: "claude" },
            { skillRef: "shared:managed-2", harness: "codex" },
          ],
          failed: [],
        };

        if (!body.dryRun) {
          for (const agentRef of response.changed) {
            written[agentRef] = Array.from(new Set([...written[agentRef], ...body.skillRefs]));
          }
        }
        return Promise.resolve(okJson(response));
      }

      if (url.includes("/api/skills") && (!init || init.method === "GET")) {
        return Promise.resolve(okJson(skillsPayload()));
      }

      return Promise.resolve(okJson({}));
    });

    renderWithAppProviders(
      <SkillsWorkspaceSessionProvider>
        <SkillsWorkspacePage />
      </SkillsWorkspaceSessionProvider>,
    );

    await waitFor(() => expect(screen.getByText("Managed 1")).toBeInTheDocument());

    fireEvent.click(screen.getByLabelText("Select all visible skills"));

    const toolbar = screen.getByRole("toolbar", { name: "Bulk actions" });
    fireEvent.click(within(toolbar).getByRole("button", { name: "Attach to agents" }));

    await waitFor(() => expect(screen.getByRole("heading", { name: "Attach to agents" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("checkbox", { name: "Agent 1" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Agent 2" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Agent Bad" }));
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));

    await waitFor(() => expect(screen.getByRole("heading", { name: "Attach agents?" })).toBeInTheDocument());
    expect(screen.getByText(/2 agents will change/)).toBeInTheDocument();
    expect(screen.getByText(/2 managed skills/)).toBeInTheDocument();
    expect(screen.getByText(/2 new harness bindings on Claude Code and Codex/)).toBeInTheDocument();
    expect(screen.getByText(/1 unmanaged selected row is skipped/)).toBeInTheDocument();
    expect(screen.getByText(/agent-bad \(agent not writable\)/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Attach" }));

    await waitFor(() => expect(screen.queryByRole("heading", { name: "Attach agents?" })).not.toBeInTheDocument());
    expect(written["agent-1"]).toEqual(["shared:managed-1", "shared:managed-2"]);
    expect(written["agent-2"]).toEqual(["existing-skill", "shared:managed-1", "shared:managed-2"]);
    expect(written["agent-bad"]).toEqual([]);
    expect(screen.getByText(/1 agent was skipped: agent-bad \(agent not writable\)/)).toBeInTheDocument();
  });

  it("offers adopted agents for the first attach even when nothing is attached yet", async () => {
    // Regression: the popover's vocabulary used to be derived from the union of
    // row.agents, i.e. only agents that ALREADY carried a skill. On a cold store
    // that list is empty, so the popover offered nothing and the first attach was
    // impossible. The vocabulary must come from the adopted-agent roster instead.
    const coldPayload = {
      ...skillsPayload(),
      rows: skillsPayload().rows.map((row) => ({ ...row, agents: [] })),
    };

    let attachBody: { skillRefs: string[]; agentRefs: string[] } | null = null;

    fetchMock.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/api/skills/attach-agents") && init?.method === "POST") {
        const body = JSON.parse(String(init.body)) as {
          skillRefs: string[];
          agentRefs: string[];
          dryRun: boolean;
        };
        if (!body.dryRun) attachBody = body;
        return Promise.resolve(
          okJson({ changed: ["agent-1"], skipped: [], autoEnabled: [], failed: [] }),
        );
      }
      if (url.includes("/api/skills") && (!init || init.method === "GET")) {
        return Promise.resolve(okJson(coldPayload));
      }
      return Promise.resolve(okJson({}));
    });

    renderWithAppProviders(
      <SkillsWorkspaceSessionProvider>
        <SkillsWorkspacePage />
      </SkillsWorkspaceSessionProvider>,
    );

    await waitFor(() => expect(screen.getByText("Managed 1")).toBeInTheDocument());
    // No row carries an agent chip - the cold-start condition.
    expect(screen.queryByRole("button", { name: /Agent 1/ })).not.toBeInTheDocument();

    fireEvent.click(screen.getByLabelText("Select all visible skills"));
    const toolbar = screen.getByRole("toolbar", { name: "Bulk actions" });
    fireEvent.click(within(toolbar).getByRole("button", { name: "Attach to agents" }));

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Attach to agents" })).toBeInTheDocument(),
    );

    // The whole point: every adopted agent is offered despite zero attachments.
    expect(screen.getByRole("checkbox", { name: "Agent 1" })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Agent 2" })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Agent Bad" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("checkbox", { name: "Agent 1" }));
    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: "Attach agents?" })).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByRole("button", { name: "Attach" }));

    await waitFor(() => expect(attachBody).not.toBeNull());
    expect(attachBody!.agentRefs).toEqual(["agent-1"]);
    expect(attachBody!.skillRefs).toEqual(["shared:managed-1", "shared:managed-2"]);
  });
});
