import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { okJson } from "../../../../test/fetch";
import { renderWithAppProviders } from "../../../../test/render";
import { AgentDetailContent } from "./AgentDetailContent";
import type { AgentDetailDto } from "../../api/types";

const fetchMock = vi.fn();

function agentDetailFixture(overrides?: Partial<AgentDetailDto>): AgentDetailDto {
  return {
    ref: "chief",
    name: "Chief of Staff",
    description: "Orchestrates tasks",
    prompt: "You are the Chief of Staff.",
    tools: ["Read", "Bash"],
    skills: [
      { slug: "code-review", name: "Code Review" },
    ],
    document: "---\nname: Chief of Staff\ndescription: Orchestrates tasks\nskills:\n  - code-review\n---\nYou are the Chief of Staff.",
    storePath: "/store/chief.md",
    configuration: [
      { key: "skills", value: "code-review" },
    ],
    harnesses: [
      {
        harness: "claude",
        label: "Claude Code",
        logoKey: "claude",
        state: "enabled",
        detail: null,
        path: "/home/user/.claude/agents/chief.md",
        installMethod: "symlink",
        installed: true,
      },
    ],
    canDelete: true,
    canEdit: true,
    ...overrides,
  };
}

describe("AgentDetailContent", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders skills chips in edit mode and saves attached skills with auto-enable toast feedback", async () => {
    fetchMock.mockImplementation((input, init) => {
      const url = String(input);
      const method = init?.method || "GET";

      if (url.includes("/api/skills")) {
        return Promise.resolve(
          okJson({
            columns: [],
            entries: [],
            rows: [
              { skillRef: "shared:code-review", name: "Code Review", displayStatus: "Managed" },
              { skillRef: "shared:test-debugging", name: "Test Debugging", displayStatus: "Managed" },
            ],
          }),
        );
      }

      if (url.includes("/api/agents/chief") && method === "PUT") {
        return Promise.resolve(
          okJson({
            ref: "chief",
            name: "Chief of Staff",
            description: "Orchestrates tasks",
            prompt: "You are the Chief of Staff.",
            tools: ["Read", "Bash"],
            skills: [
              { slug: "code-review", name: "Code Review" },
              { slug: "test-debugging", name: "Test Debugging" },
            ],
            document: "---\nname: Chief of Staff\ndescription: Orchestrates tasks\nskills:\n  - code-review\n  - test-debugging\n---\nYou are the Chief of Staff.",
            storePath: "/store/chief.md",
            configuration: [],
            harnesses: [],
            canDelete: true,
            canEdit: true,
            ok: true,
            autoEnabled: [{ skillRef: "shared:test-debugging", harness: "claude" }],
            failed: [],
          }),
        );
      }

      return Promise.resolve(okJson({}));
    });

    renderWithAppProviders(
      <AgentDetailContent
        detail={agentDetailFixture()}
        knownSkills={[
          { slug: "code-review", name: "Code Review" },
          { slug: "test-debugging", name: "Test Debugging" },
        ]}
        pendingPerHarnessKeys={new Set()}
        onToggleHarness={vi.fn()}
        actionErrorMessage={null}
        onClose={vi.fn()}
        onDismissActionError={vi.fn()}
      />,
    );

    // Switch to edit mode
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));

    // Verify existing skill chip is shown
    expect(screen.getByText("Code Review")).toBeInTheDocument();

    // Attach test-debugging skill
    const skillInput = screen.getByRole("combobox", { name: "Attach skill" });
    fireEvent.change(skillInput, { target: { value: "test-debugging" } });
    fireEvent.keyDown(skillInput, { key: "Enter" });

    expect(screen.getByText("Test Debugging")).toBeInTheDocument();

    // Click Save
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining("/api/agents/chief"),
        expect.objectContaining({
          method: "PUT",
          body: expect.stringContaining("test-debugging"),
        }),
      );
    });
  });

  it("previews the document body without its YAML frontmatter", async () => {
    fetchMock.mockImplementation(() => Promise.resolve(okJson({ rows: [] })));

    renderWithAppProviders(
      <AgentDetailContent
        detail={agentDetailFixture({
          document: [
            "---",
            "name: scrutiny-feature-reviewer",
            "model: inherit",
            "---",
            "",
            "# Review Checklist",
          ].join("\n"),
        })}
        pendingPerHarnessKeys={new Set()}
        onToggleHarness={vi.fn()}
        actionErrorMessage={null}
        onClose={vi.fn()}
        onDismissActionError={vi.fn()}
      />,
    );

    expect(await screen.findByRole("heading", { name: "Review Checklist" })).toBeInTheDocument();
    expect(screen.queryByText(/model: inherit/)).not.toBeInTheDocument();
  });

  it("offers effort as a fixed choice, with an empty option that clears the key", () => {
    fetchMock.mockImplementation(() => Promise.resolve(okJson({ rows: [] })));

    renderWithAppProviders(
      <AgentDetailContent
        detail={agentDetailFixture({ effort: "medium" })}
        pendingPerHarnessKeys={new Set()}
        onToggleHarness={vi.fn()}
        actionErrorMessage={null}
        onClose={vi.fn()}
        onDismissActionError={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));

    const effort = screen.getByRole("combobox", { name: "Effort" });
    expect(effort).toHaveValue("medium");
    expect(
      Array.from((effort as HTMLSelectElement).options).map((option) => option.value),
    ).toEqual(["", "low", "medium", "high"]);
  });

  it("keeps an out-of-contract effort visible instead of silently rewriting it", () => {
    fetchMock.mockImplementation(() => Promise.resolve(okJson({ rows: [] })));

    renderWithAppProviders(
      <AgentDetailContent
        detail={agentDetailFixture({ effort: "maximum" })}
        pendingPerHarnessKeys={new Set()}
        onToggleHarness={vi.fn()}
        actionErrorMessage={null}
        onClose={vi.fn()}
        onDismissActionError={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Edit" }));

    const effort = screen.getByRole("combobox", { name: "Effort" });
    expect(effort).toHaveValue("maximum");
    expect(screen.getByRole("option", { name: /not a valid effort/ })).toBeInTheDocument();
  });
});
