import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { McpInventoryColumnDto, McpInventoryEntryDto } from "../api/management-types";
import { McpServerMatrixView } from "./McpServerMatrixView";

function columns(): McpInventoryColumnDto[] {
  return [
    { harness: "codex", label: "Codex", logoKey: "codex", installed: true, configPresent: true, mcpWritable: true },
    { harness: "claude", label: "Claude", logoKey: "claude", installed: true, configPresent: true, mcpWritable: true },
    {
      harness: "hermes",
      label: "Hermes Agent",
      logoKey: "hermes",
      installed: true,
      configPresent: false,
      mcpWritable: false,
      mcpUnavailableReason: "Hermes Agent MCP writes are unavailable",
    },
  ];
}

function entries(): McpInventoryEntryDto[] {
  return [
    {
      name: "exa",
      displayName: "Exa Search",
      kind: "managed",
      canEnable: true,
      enabledStatus: "enabled",
      availabilityStatus: "available",
      availabilityReason: null,
      mcpStatus: { kind: "available", reason: null },
      installConfigStatus: { hasFields: false, missingRequired: [], configured: true },
      spec: {
        name: "exa",
        displayName: "Exa Search",
        source: { kind: "marketplace", locator: "exa" },
        transport: "http",
        url: "https://exa.run.tools",
        installedAt: "2026-04-21T00:00:00Z",
        revision: "abc",
      },
      sightings: [
        { harness: "codex", state: "managed" },
        { harness: "claude", state: "missing" },
        { harness: "hermes", state: "missing" },
      ],
    },
    {
      name: "drift",
      displayName: "Drift Server",
      kind: "managed",
      canEnable: true,
      enabledStatus: "disabled",
      availabilityStatus: "unavailable",
      availabilityReason: null,
      mcpStatus: {
        kind: "unchecked",
        reason: null,
      },
      installConfigStatus: { hasFields: false, missingRequired: [], configured: true },
      spec: {
        name: "drift",
        displayName: "Drift Server",
        source: { kind: "manual", locator: "drift" },
        transport: "stdio",
        command: "npx",
        args: ["drift"],
        installedAt: "2026-04-21T00:00:00Z",
        revision: "def",
      },
      sightings: [
        { harness: "codex", state: "missing" },
        { harness: "claude", state: "drifted", driftDetail: "changed=url" },
      ],
    },
  ];
}

function renderMatrix(overrides: Partial<Parameters<typeof McpServerMatrixView>[0]> = {}) {
  const props = {
    entries: entries(),
    columns: columns(),
    pendingServerKeys: new Set<string>(),
    pendingPerHarnessKeys: new Set<string>(),
    checkedNames: new Set<string>(),
    onOpenDetail: vi.fn(),
    onToggleChecked: vi.fn(),
    onEnableHarness: vi.fn(),
    onDisableHarness: vi.fn(),
    ...overrides,
  };
  render(<McpServerMatrixView {...props} />);
  return props;
}

describe("McpServerMatrixView", () => {
  it("locks header and body columns with matrix-specific structure", () => {
    renderMatrix();

    const table = screen.getByRole("table", { name: "MCP server harness matrix" });
    const headerCells = table.querySelectorAll("thead tr > th");
    const bodyCells = table.querySelectorAll("tbody tr:first-child > td");

    expect(table).toHaveClass("matrix-table");
    expect(table).not.toHaveClass("matrix-table--panel");
    expect(table.closest(".matrix-table-wrapper")).not.toHaveClass("matrix-table-wrapper--panel");
    // Header and body must agree cell-for-cell — every column's width is taken
    // from the header cell that sits above it.
    expect(headerCells).toHaveLength(columns().length + 5);
    expect(bodyCells).toHaveLength(headerCells.length);
    expect(headerCells[0]).toHaveClass("matrix-table__th--checkbox");
    expect(headerCells[headerCells.length - 2]).toHaveClass("matrix-table__th--compact");
    expect(headerCells[headerCells.length - 1]).toHaveClass("matrix-table__th--end");
    expect(screen.getByText("MCP Server").closest("th")).toHaveClass("matrix-table__th--identity");
    expect(screen.getByText("Active").closest("th")).toHaveClass("matrix-table__th--end");
    expect(screen.getByRole("button", { name: "Sort by Codex" })).toBeInTheDocument();
  });

  it("renders star buttons for starred and unstarred MCP server rows and toggles star on click", () => {
    const onToggleStar = vi.fn();
    const testEntries = [
      {
        ...entries()[0],
        tags: ["starred"],
      },
      {
        ...entries()[1],
        tags: [],
      },
    ];
    renderMatrix({ entries: testEntries, onToggleStar });

    const unstarBtn = screen.getByRole("button", { name: "Unstar exa" });
    expect(unstarBtn).toBeInTheDocument();
    expect(unstarBtn.className).toContain("skill-star-btn--active");
    fireEvent.click(unstarBtn);
    expect(onToggleStar).toHaveBeenCalledWith("exa");

    const starBtn = screen.getByRole("button", { name: "Star drift" });
    expect(starBtn).toBeInTheDocument();
    expect(starBtn.className).not.toContain("skill-star-btn--active");
    fireEvent.click(starBtn);
    expect(onToggleStar).toHaveBeenCalledWith("drift");
  });

  it("sorts rows by MCP Server name, active coverage, and harness state", () => {
    renderMatrix();

    const getRowNames = () =>
      screen
        .getAllByRole("row")
        .slice(1)
        .map((r) => r.querySelector(".matrix-table__name-text")?.textContent ?? "");

    // Initially asc: "Drift Server", "Exa Search"
    expect(getRowNames()).toEqual(["Drift Server", "Exa Search"]);

    // Sort by name desc: "Exa Search", "Drift Server"
    fireEvent.click(screen.getByRole("button", { name: "Sort by MCP Server" }));
    expect(getRowNames()).toEqual(["Exa Search", "Drift Server"]);

    // Sort by Active
    fireEvent.click(screen.getByRole("button", { name: "Sort by Active" }));
    expect(getRowNames()).toEqual(["Drift Server", "Exa Search"]);

    // Sort by Codex harness (Exa is enabled=0, Drift is missing=4)
    fireEvent.click(screen.getByRole("button", { name: "Sort by Codex" }));
    expect(getRowNames()).toEqual(["Exa Search", "Drift Server"]);
  });

  it("renders coverage and per-harness actions", () => {
    const { onEnableHarness, onDisableHarness } = renderMatrix();

    expect(screen.getByRole("table", { name: "MCP server harness matrix" })).toBeInTheDocument();
    expect(screen.getByLabelText("Enabled on 1 of 2 writable harnesses")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Disable Exa Search on Codex" }));
    expect(onDisableHarness).toHaveBeenCalledWith("exa", "codex");

    fireEvent.click(screen.getByRole("button", { name: "Enable Exa Search on Claude" }));
    expect(onEnableHarness).toHaveBeenCalledWith("exa", "claude");
  });

  it("exposes unavailable harness reasons without allowing mutation", () => {
    renderMatrix();

    const unavailable = screen.getByLabelText("Exa Search on Hermes Agent is unavailable");
    expect(unavailable).toHaveAttribute("aria-disabled", "true");
    expect(unavailable).toHaveAttribute("title", "Hermes Agent MCP writes are unavailable");
  });

  it("routes different configs to detail instead of mutating harness state", () => {
    const { onOpenDetail, onEnableHarness, onDisableHarness } = renderMatrix();

    fireEvent.click(screen.getByRole("button", { name: "Resolve config for Drift Server on Claude" }));
    expect(onOpenDetail).toHaveBeenCalledWith("drift");
    expect(onEnableHarness).not.toHaveBeenCalled();
    expect(onDisableHarness).not.toHaveBeenCalled();
  });

  it("disables pending cells", () => {
    renderMatrix({ pendingPerHarnessKeys: new Set(["exa:codex"]) });

    const pending = screen.getByRole("button", { name: "Disable Exa Search on Codex" });
    expect(pending).toBeDisabled();
    expect(pending).toHaveAttribute("data-pending", "true");
  });

  it("renders adopt action and calls onAdopt for identical unmanaged entries", () => {
    const unmanagedEntry: McpInventoryEntryDto = {
      name: "context7",
      displayName: "Context7",
      kind: "unmanaged",
      canEnable: false,
      enabledStatus: "disabled",
      availabilityStatus: "unavailable",
      availabilityReason: null,
      mcpStatus: { kind: "unchecked", reason: null },
      installConfigStatus: { hasFields: false, missingRequired: [], configured: true },
      spec: null,
      sightings: [
        { harness: "codex", state: "unmanaged" },
        { harness: "claude", state: "unmanaged" },
      ],
    };

    const groupsByName = new Map([
      [
        "context7",
        {
          name: "context7",
          identical: true,
          sightings: [],
        },
      ],
    ]);

    const onAdopt = vi.fn();
    renderMatrix({
      entries: [unmanagedEntry],
      groupsByName,
      onAdopt,
    });

    expect(screen.getByText("Identical")).toBeInTheDocument();
    const adoptButton = screen.getByRole("button", { name: /^Adopt$/ });
    expect(adoptButton).toBeInTheDocument();
    fireEvent.click(adoptButton);
    expect(onAdopt).toHaveBeenCalledWith("context7");
  });

  it("renders choose-config action and calls onChooseConfigToAdopt for differing unmanaged entries", () => {
    const unmanagedEntry: McpInventoryEntryDto = {
      name: "context7",
      displayName: "Context7",
      kind: "unmanaged",
      canEnable: false,
      enabledStatus: "disabled",
      availabilityStatus: "unavailable",
      availabilityReason: null,
      mcpStatus: { kind: "unchecked", reason: null },
      installConfigStatus: { hasFields: false, missingRequired: [], configured: true },
      spec: null,
      sightings: [
        { harness: "codex", state: "unmanaged" },
        { harness: "claude", state: "unmanaged" },
      ],
    };

    const groupsByName = new Map([
      [
        "context7",
        {
          name: "context7",
          identical: false,
          sightings: [],
        },
      ],
    ]);

    const onChooseConfigToAdopt = vi.fn();
    renderMatrix({
      entries: [unmanagedEntry],
      groupsByName,
      onChooseConfigToAdopt,
    });

    expect(screen.getByText("Differs across harnesses")).toBeInTheDocument();
    const chooseButton = screen.getByRole("button", { name: /^Choose config to adopt$/ });
    expect(chooseButton).toBeInTheDocument();
    fireEvent.click(chooseButton);
    expect(onChooseConfigToAdopt).toHaveBeenCalledWith("context7");

    const checkbox = screen.getByRole("checkbox", { name: /select context7/i });
    expect(checkbox).toHaveAttribute("aria-disabled", "true");
  });
});
