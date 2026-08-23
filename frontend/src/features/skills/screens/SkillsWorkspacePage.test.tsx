import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SkillsWorkspaceSessionProvider } from "../model/session";
import { getSkillsRouteElements } from "../routes";
import SkillsWorkspacePage from "./SkillsWorkspacePage";

const hooks = vi.hoisted(() => ({
  onManageSkill: vi.fn(async () => undefined),
  onManageAll: vi.fn(),
  onOpenSkill: vi.fn(),
  onToggleCell: vi.fn(),
  onToggleMultiSelect: vi.fn(),
  onClearMultiSelect: vi.fn(),
  onMultiSelectEnableAll: vi.fn(async () => undefined),
  onMultiSelectDisableAll: vi.fn(async () => undefined),
  onMultiSelectDelete: vi.fn(async () => undefined),
  handleManageSkill: vi.fn(async () => undefined),
  handleToggleSkill: vi.fn(async () => undefined),
  handleUpdateSkill: vi.fn(async () => undefined),
  handleRemoveSkill: vi.fn(async () => undefined),
  handleDeleteSkill: vi.fn(async () => undefined),
  dismissActionError: vi.fn(),
}));

const mixedData = {
  summary: { managed: 2, unmanaged: 1 },
  harnessColumns: [
    { harness: "codex", label: "Codex", logoKey: "codex", installed: true },
    { harness: "cursor", label: "Cursor", logoKey: "cursor", installed: true },
  ],
  rows: [
    {
      skillRef: "shared:managed-skill",
      name: "Managed Skill",
      description: "Managed description",
      displayStatus: "Managed",
      tags: ["starred"],
      actions: { canManage: false, canStopManaging: true, canDelete: true },
      cells: [
        { harness: "codex", label: "Codex", logoKey: "codex", state: "enabled", interactive: true },
        { harness: "cursor", label: "Cursor", logoKey: "cursor", state: "disabled", interactive: true },
      ],
    },
    {
      skillRef: "shared:other-skill",
      name: "Other Skill",
      description: "Other description",
      displayStatus: "Managed",
      tags: ["devops"],
      actions: { canManage: false, canStopManaging: true, canDelete: true },
      cells: [
        { harness: "codex", label: "Codex", logoKey: "codex", state: "enabled", interactive: true },
        { harness: "cursor", label: "Cursor", logoKey: "cursor", state: "disabled", interactive: true },
      ],
    },
    {
      skillRef: "local:untracked-skill",
      name: "Untracked Skill",
      description: "Untracked description",
      displayStatus: "Unmanaged",
      actions: { canManage: true, canStopManaging: false, canDelete: false },
      cells: [
        { harness: "codex", label: "Codex", logoKey: "codex", state: "found", interactive: false },
        { harness: "cursor", label: "Cursor", logoKey: "cursor", state: "empty", interactive: false },
      ],
    },
  ],
};

vi.mock("../model/use-skills-workspace-controller", () => ({
  useSkillsWorkspaceController: () => ({
    context: {
      data: mixedData,
      hasData: true,
      isInitialLoading: false,
      status: "ready",
      errorMessage: "",
      pendingToggleKeys: new Set(),
      pendingStructuralActions: new Map(),
      pendingBulkAction: null,
      selectedSkillRef: null,
      multiSelectedRefs: new Set(),
      multiSelectPending: null,
      onManageAll: hooks.onManageAll,
      onManageSkill: hooks.onManageSkill,
      onOpenSkill: hooks.onOpenSkill,
      onToggleCell: hooks.onToggleCell,
      onToggleMultiSelect: hooks.onToggleMultiSelect,
      onClearMultiSelect: hooks.onClearMultiSelect,
      onMultiSelectEnableAll: hooks.onMultiSelectEnableAll,
      onMultiSelectDisableAll: hooks.onMultiSelectDisableAll,
      onMultiSelectDelete: hooks.onMultiSelectDelete,
      onSetSkillAllHarnesses: vi.fn(),
      onSetManySkillsAllHarnesses: vi.fn(),
      onUpdateSkill: hooks.handleUpdateSkill,
      onRemoveSkill: hooks.handleRemoveSkill,
      onDeleteSkill: hooks.handleDeleteSkill,
    },
    selectedSkillRef: null,
    isDesktopDetailOpen: false,
    closeSelectedSkill: vi.fn(),
    handleManageSkill: hooks.handleManageSkill,
    handleToggleSkill: hooks.handleToggleSkill,
    handleUpdateSkill: hooks.handleUpdateSkill,
    handleRemoveSkill: hooks.handleRemoveSkill,
    handleDeleteSkill: hooks.handleDeleteSkill,
    actionErrorMessage: "",
    queryErrorMessage: "",
    dismissActionError: hooks.dismissActionError,
  }),
}));

function renderPage(route = "/skills") {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <SkillsWorkspaceSessionProvider>
        <MemoryRouter initialEntries={[route]}>
          <SkillsWorkspacePage />
        </MemoryRouter>
      </SkillsWorkspaceSessionProvider>
    </QueryClientProvider>,
  );
}

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="skills-location">{location.pathname}{location.search}</output>;
}

function renderRoutes(route: string) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <SkillsWorkspaceSessionProvider>
        <MemoryRouter initialEntries={[route]}>
          <Routes>{getSkillsRouteElements()}</Routes>
          <LocationProbe />
        </MemoryRouter>
      </SkillsWorkspaceSessionProvider>
    </QueryClientProvider>,
  );
}

describe("Skills unified inventory page", () => {
  beforeEach(() => {
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
    vi.clearAllMocks();
  });

  it("renders managed and untracked rows in one sortable matrix", () => {
    renderPage();

    expect(screen.getByRole("table", { name: "Skills harness matrix" })).toBeInTheDocument();
    expect(screen.getByText("Managed Skill")).toBeInTheDocument();
    expect(screen.getByText("Untracked Skill")).toBeInTheDocument();
    expect(screen.getByLabelText("Search skills in use")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sort by Skill" })).toBeInTheDocument();

    for (const name of ["Grid", "Board", "Matrix", "Scan", "Table"]) {
      expect(screen.queryByRole("button", { name })).not.toBeInTheDocument();
    }
  });

  it("deep-link status=untracked renders only untracked rows", () => {
    renderPage("/skills?status=untracked");

    expect(screen.getByText("Untracked Skill")).toBeInTheDocument();
    expect(screen.queryByText("Managed Skill")).not.toBeInTheDocument();
  });

  it("keeps managed selection separate and makes discovered untracked cells actionable", () => {
    renderPage();

    expect(screen.getByRole("checkbox", { name: "Select Untracked Skill" })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Select Managed Skill" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open details for Untracked Skill on Codex" })).toHaveAttribute(
      "data-state",
      "observed",
    );
  });

  it("adopts an untracked skill from its row action", async () => {
    renderPage("/skills?status=untracked");

    fireEvent.click(screen.getByRole("button", { name: "Adopt" }));
    await waitFor(() => expect(hooks.onManageSkill).toHaveBeenCalledWith("local:untracked-skill"));
  });

  it("shows the untracked bulk dock only after an untracked row is selected", async () => {
    renderPage();

    expect(screen.queryByRole("toolbar", { name: "Bulk actions" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: "Select Untracked Skill" }));
    const toolbar = screen.getByRole("toolbar", { name: "Bulk actions" });
    expect(toolbar).toBeInTheDocument();
    expect(within(toolbar).getByRole("button", { name: "Adopt" })).toBeInTheDocument();

    fireEvent.click(within(toolbar).getByRole("button", { name: "Adopt" }));
    await waitFor(() => expect(hooks.onManageSkill).toHaveBeenCalledWith("local:untracked-skill"));
  });

  it("toggles tag=starred filter when clicking the header star button", async () => {
    renderPage();

    expect(screen.getByText("Managed Skill")).toBeInTheDocument();
    expect(screen.getByText("Other Skill")).toBeInTheDocument();

    const headerStarBtn = screen.getByRole("button", { name: "Filter by starred" });
    expect(headerStarBtn).toHaveAttribute("aria-pressed", "false");

    fireEvent.click(headerStarBtn);

    // After clicking, only the starred skill is visible and button is active
    expect(screen.getByText("Managed Skill")).toBeInTheDocument();
    expect(screen.queryByText("Other Skill")).not.toBeInTheDocument();
    expect(headerStarBtn).toHaveAttribute("aria-pressed", "true");
    expect(headerStarBtn).toHaveAttribute("data-active", "true");

    // Clicking again toggles off
    fireEvent.click(headerStarBtn);
    expect(screen.getByText("Managed Skill")).toBeInTheDocument();
    expect(screen.getByText("Other Skill")).toBeInTheDocument();
    expect(headerStarBtn).toHaveAttribute("aria-pressed", "false");
  });

  it("renders active star header when loading ?tag=starred and participates in clear filters", async () => {
    renderPage("/skills?tag=starred");

    expect(screen.getByText("Managed Skill")).toBeInTheDocument();
    expect(screen.queryByText("Other Skill")).not.toBeInTheDocument();

    const headerStarBtn = screen.getByRole("button", { name: "Filter by starred" });
    expect(headerStarBtn).toHaveAttribute("aria-pressed", "true");
    expect(headerStarBtn).toHaveAttribute("data-active", "true");

    // Clear filters in TagFilterBar clears the star filter
    const clearBtn = screen.getByRole("button", { name: "Clear tag filters" });
    fireEvent.click(clearBtn);

    expect(screen.getByText("Managed Skill")).toBeInTheDocument();
    expect(screen.getByText("Other Skill")).toBeInTheDocument();
    expect(headerStarBtn).toHaveAttribute("aria-pressed", "false");
  });

});

describe("Skills shared route fragment", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "ResizeObserver",
      class ResizeObserver {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
  });

  afterEach(() => vi.unstubAllGlobals());

  it.each([
    ["/skills/use", "/skills"],
    ["/skills/review", "/skills?status=untracked"],
    ["/skills/managed", "/skills"],
    ["/skills/unmanaged", "/skills?status=untracked"],
  ])("redirects %s to %s", async (source, target) => {
    renderRoutes(source);
    await waitFor(() => expect(screen.getByTestId("skills-location").textContent).toBe(target));
  });
});
