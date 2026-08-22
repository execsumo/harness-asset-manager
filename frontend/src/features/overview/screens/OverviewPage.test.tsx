import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { errorJson, okJson } from "../../../test/fetch";
import { renderWithAppProviders } from "../../../test/render";
import OverviewPage from "./OverviewPage";

const fetchMock = vi.fn();

function renderOverview() {
  return renderWithAppProviders(<OverviewPage />, { route: "/overview" });
}

function skillsPayload() {
  return {
    summary: { managed: 2, unmanaged: 1 },
    harnessColumns: [
      { harness: "codex", label: "Codex", logoKey: "codex", installed: true },
      { harness: "claude", label: "Claude", logoKey: "claude", installed: true },
    ],
    rows: [
      {
        skillRef: "audit",
        name: "audit",
        description: "Audit project state.",
        displayStatus: "Managed",
        actions: {},
        cells: [
          { harness: "codex", label: "Codex", logoKey: "codex", state: "enabled", interactive: true },
          { harness: "claude", label: "Claude", logoKey: "claude", state: "disabled", interactive: true },
        ],
      },
      {
        skillRef: "docs",
        name: "docs",
        description: "Write documents.",
        displayStatus: "Managed",
        actions: {},
        cells: [
          { harness: "codex", label: "Codex", logoKey: "codex", state: "enabled", interactive: true },
          { harness: "claude", label: "Claude", logoKey: "claude", state: "enabled", interactive: true },
        ],
      },
      {
        skillRef: "trace",
        name: "trace",
        description: "Needs review.",
        displayStatus: "Unmanaged",
        actions: {},
        cells: [
          { harness: "codex", label: "Codex", logoKey: "codex", state: "found", interactive: false },
          { harness: "claude", label: "Claude", logoKey: "claude", state: "empty", interactive: false },
        ],
      },
    ],
  };
}

function mcpInventoryPayload() {
  return {
    columns: [
      {
        harness: "codex",
        label: "Codex",
        logoKey: "codex",
        installed: true,
        configPresent: true,
        mcpWritable: true,
        mcpUnavailableReason: null,
      },
      {
        harness: "claude",
        label: "Claude",
        logoKey: "claude",
        installed: true,
        configPresent: true,
        mcpWritable: false,
        mcpUnavailableReason: "Claude MCP writes are unavailable",
      },
    ],
    entries: [
      {
        name: "exa",
        displayName: "Exa",
        kind: "managed",
        canEnable: true,
        spec: { transport: "http", url: "https://example.com/mcp" },
        sightings: [
          { harness: "codex", state: "managed", driftDetail: null },
          { harness: "claude", state: "drifted", driftDetail: "Different headers" },
        ],
      },
      {
        name: "context7",
        displayName: "Context7",
        kind: "managed",
        canEnable: true,
        spec: { transport: "stdio", command: "npx", args: ["context7"] },
        sightings: [{ harness: "codex", state: "managed", driftDetail: null }],
      },
      {
        name: "firecrawl",
        displayName: "Firecrawl",
        kind: "unmanaged",
        canEnable: false,
        spec: null,
        sightings: [{ harness: "claude", state: "unmanaged", driftDetail: null }],
      },
    ],
    issues: [{ name: "bad", reason: "Invalid manifest" }],
  };
}

function hooksInventoryPayload() {
  return {
    columns: [
      {
        harness: "codex",
        label: "Codex",
        logoKey: "codex",
        installed: true,
        configPresent: true,
        hooksWritable: true,
        hooksUnavailableReason: null,
      },
      {
        harness: "claude",
        label: "Claude",
        logoKey: "claude",
        installed: true,
        configPresent: true,
        hooksWritable: false,
        hooksUnavailableReason: "Claude hook writes are unavailable",
      },
    ],
    entries: [
      {
        id: "pre-commit",
        displayName: "Pre-commit",
        kind: "managed",
        canEnable: true,
        enabledStatus: "enabled",
        spec: null,
        sightings: [
          { harness: "codex", state: "managed", driftDetail: null },
          { harness: "claude", state: "drifted", driftDetail: null },
        ],
      },
    ],
    issues: [],
  };
}

function agentsInventoryPayload() {
  return {
    columns: [{ harness: "codex", label: "Codex", logoKey: "codex", installed: true }],
    entries: [
      {
        ref: "planner",
        name: "planner",
        description: "Planning agent.",
        kind: "managed",
        harnessPath: null,
        bindings: [{ harness: "codex", state: "enabled", detail: null }],
        actions: { canAdopt: false, canDelete: true },
      },
      {
        ref: "helper",
        name: "helper",
        description: "Local helper.",
        kind: "unmanaged",
        harnessPath: "/tmp/.codex/agents/helper.md",
        bindings: [{ harness: "codex", state: "enabled", detail: null }],
        actions: { canAdopt: true, canDelete: false },
      },
    ],
    issues: [],
  };
}

function slashCommandsPayload() {
  return {
    storePath: "/tmp/home/Library/Application Support/harnessam/slash-commands/commands",
    syncStatePath: "/tmp/home/Library/Application Support/harnessam/slash-commands/sync-state.json",
    targets: [],
    defaultTargets: [],
    commands: [
      {
        name: "code-review",
        description: "Review code",
        prompt: "$ARGUMENTS",
        syncTargets: [],
      },
    ],
    reviewCommands: [
      {
        reviewRef: "codex:missing-command:missing",
        kind: "missing",
        target: "codex",
        targetLabel: "Codex",
        name: "missing-command",
        path: "/tmp/home/.codex/prompts/missing-command.md",
        description: "Missing command",
        prompt: "",
        commandExists: true,
        canImport: false,
        actions: ["restore_managed", "remove_binding"],
        error: null,
      },
    ],
  };
}

function stubOverviewApi({
  skills = skillsPayload(),
  slashCommands = slashCommandsPayload(),
  mcp = mcpInventoryPayload(),
  hooks = hooksInventoryPayload(),
  permissions = { columns: [], entries: [], issues: [] },
  agents = agentsInventoryPayload(),
}: {
  skills?: unknown;
  slashCommands?: unknown;
  mcp?: unknown;
  hooks?: unknown;
  permissions?: unknown;
  agents?: unknown;
} = {}) {
  fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input.toString();
    const respond = (payload: unknown) =>
      payload instanceof Error ? errorJson(payload.message) : okJson(payload);
    if (url === "/api/skills") return respond(skills);
    if (url === "/api/slash-commands") return respond(slashCommands);
    if (url === "/api/mcp/servers") return respond(mcp);
    if (url === "/api/hooks") return respond(hooks);
    if (url === "/api/permissions") return respond(permissions);
    if (url === "/api/agents") return respond(agents);
    return okJson({});
  });
}

function section(name: string): HTMLElement {
  return screen.getByRole("heading", { name }).closest("section") as HTMLElement;
}

describe("OverviewPage", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  it("renders the active-harnesses coverage table across all capabilities", async () => {
    stubOverviewApi();
    renderOverview();

    await waitFor(() => expect(screen.getByText("Codex")).toBeInTheDocument());
    const coverage = section("Active harnesses");
    const codexRow = within(coverage).getByText("Codex").closest(".overview-coverage-row") as HTMLElement;
    const claudeRow = within(coverage).getByText("Claude").closest(".overview-coverage-row") as HTMLElement;

    for (const header of ["Harness", "Skills", "Cmds", "MCP", "Hooks", "Perms", "Agents", "Review"]) {
      expect(within(coverage).getByText(header)).toBeInTheDocument();
    }

    // Codex: 2 enabled skills (+1 found), 0 synced commands (+1 review), 2 managed
    // servers, 1 hook, 1 agent (+1 unmanaged) → 3 items to review.
    expect(within(codexRow).getAllByText("2")).toHaveLength(2);
    expect(within(codexRow).getAllByText("+1")).toHaveLength(3);
    expect(within(codexRow).getAllByText("1")).toHaveLength(2);
    expect(within(codexRow).getByText("3")).toBeInTheDocument();

    // Claude: 1 enabled skill, drifted + unmanaged MCP (+2), drifted hook (+1),
    // unwritable MCP and hooks → 3 items to review.
    expect(within(claudeRow).getByText("1")).toBeInTheDocument();
    expect(within(claudeRow).getByText("+2")).toBeInTheDocument();
    expect(within(claudeRow).getByText("3")).toBeInTheDocument();
    expect(
      within(claudeRow).getByLabelText("MCP: Claude MCP writes are unavailable"),
    ).toBeInTheDocument();
    expect(
      within(claudeRow).getByLabelText("Hooks: Claude hook writes are unavailable"),
    ).toBeInTheDocument();

    // The coverage table is the first section on the page.
    const firstSection = document.querySelector(".overview-page > section");
    expect(firstSection).toContainElement(coverage);
  });

  it("renders compact manage and discover shortcuts", async () => {
    stubOverviewApi();
    renderOverview();

    const shortcuts = await screen.findByRole("heading", { name: "Shortcuts" });
    expect(shortcuts).toBeInTheDocument();

    const shortcutsSection = shortcuts.closest("section") as HTMLElement;
    for (const [label, href] of [
      ["Skills", "/skills/use"],
      ["Slash Commands", "/slash-commands/use"],
      ["MCP Servers", "/mcp"],
      ["Hooks", "/hooks"],
      ["Permissions", "/permissions"],
      ["Agents", "/agents"],
      ["Skills Marketplace", "/marketplace/skills"],
      ["MCP Marketplace", "/marketplace/mcp"],
      ["CLI Marketplace", "/marketplace/clis"],
    ] as const) {
      expect(within(shortcutsSection).getByRole("link", { name: label })).toHaveAttribute("href", href);
    }
  });

  it("shows only non-zero review queue items", async () => {
    stubOverviewApi({
      skills: { ...skillsPayload(), summary: { managed: 2, unmanaged: 0 } },
    });
    renderOverview();

    await waitFor(() =>
      expect(screen.getByRole("link", { name: /MCP configs to review/i })).toBeInTheDocument(),
    );
    const queue = section("Review");
    expect(within(queue).queryByRole("link", { name: /Skills to review/i })).not.toBeInTheDocument();
    expect(within(queue).getByRole("link", { name: /MCP configs to review/i })).toBeInTheDocument();
    expect(within(queue).getByRole("link", { name: /Different MCP configs/i })).toBeInTheDocument();
    expect(within(queue).getByRole("link", { name: /MCP inventory issues/i })).toBeInTheDocument();
    expect(within(queue).getByRole("link", { name: /MCP harness unavailable/i })).toBeInTheDocument();
  });

  it("keeps usable data visible when skills fail", async () => {
    stubOverviewApi({
      skills: new Error("Skills unavailable"),
      mcp: {
        columns: [],
        entries: [
          {
            name: "exa",
            displayName: "Exa",
            kind: "managed",
            canEnable: true,
            spec: null,
            sightings: [],
          },
        ],
        issues: [],
      },
    });
    renderOverview();

    await waitFor(() =>
      expect(screen.getByText("Unable to load skills: Skills unavailable")).toBeInTheDocument(),
    );
    expect(screen.getByRole("heading", { name: "Active harnesses" })).toBeInTheDocument();
    expect(screen.queryByText("Unable to load overview data.")).not.toBeInTheDocument();
  });

  it("shows the full-page error state when every inventory fails", async () => {
    stubOverviewApi({
      skills: new Error("boom"),
      slashCommands: new Error("boom"),
      mcp: new Error("boom"),
      hooks: new Error("boom"),
      permissions: new Error("boom"),
      agents: new Error("boom"),
    });
    renderOverview();

    await waitFor(() => expect(screen.getByText("Unable to load overview data.")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Refresh" })).toBeInTheDocument();
  });
});
