import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { okJson } from "../../../../test/fetch";
import { renderWithAppProviders } from "../../../../test/render";
import { AgentDetailContent } from "./AgentDetailContent";
import { AGENT_CONTRACT_KEYS, MAX_TURNS_DEFAULT } from "../../api/types";
import type { AgentDetailDto } from "../../api/types";

function renderDetail(detail: AgentDetailDto) {
  return renderWithAppProviders(
    <AgentDetailContent
      detail={detail}
      pendingPerHarnessKeys={new Set()}
      onToggleHarness={vi.fn()}
      actionErrorMessage={null}
      onClose={vi.fn()}
      onDismissActionError={vi.fn()}
    />,
  );
}

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

  it("renders tag collection quick-picks in edit mode and attaches matching skill slugs on pick", async () => {
    fetchMock.mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/api/skills")) {
        return Promise.resolve(
          okJson({
            columns: [],
            entries: [],
            rows: [
              { skillRef: "shared:code-review", name: "Code Review", displayStatus: "Managed", tags: ["dev-suite"] },
              { skillRef: "shared:test-debugging", name: "Test Debugging", displayStatus: "Managed", tags: ["dev-suite"] },
            ],
          }),
        );
      }
      return Promise.resolve(okJson({}));
    });

    renderWithAppProviders(
      <AgentDetailContent
        detail={agentDetailFixture({ skills: [] })}
        knownSkills={[
          { slug: "code-review", name: "Code Review", tags: ["dev-suite"] },
          { slug: "test-debugging", name: "Test Debugging", tags: ["dev-suite"] },
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

    // The tag collection quick-pick button for "dev-suite" should be visible
    const tagBtn = await screen.findByRole("button", { name: "dev-suite" });
    expect(tagBtn).toBeInTheDocument();

    // Click tag collection
    fireEvent.click(tagBtn);

    // Both skills should now be attached
    expect(screen.getByText("Code Review")).toBeInTheDocument();
    expect(screen.getByText("Test Debugging")).toBeInTheDocument();

    // The tag collection is now fully attached, so it should disappear
    expect(screen.queryByRole("button", { name: "dev-suite" })).not.toBeInTheDocument();
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

  it("lists the structured frontmatter fields in the agent contract order", () => {
    fetchMock.mockImplementation(() => Promise.resolve(okJson({ rows: [] })));

    const { container } = renderDetail(agentDetailFixture());
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));

    const labels = Array.from(
      container.querySelectorAll(".frontmatter-editor__known-fields .frontmatter-editor__label"),
    ).map((node) => node.textContent);

    // The editor and the renderer read top to bottom in the same order, so a field
    // never appears in one place before the key it follows in the file.
    expect(labels).toEqual([
      "Agent Name",
      "Description",
      "Color",
      "Model",
      "Effort",
      "Tools (comma-separated)",
      "Skills",
      "Allowed Subagents",
      "Max Turns",
      "Isolation",
    ]);
    expect(labels).toHaveLength(AGENT_CONTRACT_KEYS.length);
  });

  it("offers color as a dropdown with an empty option that clears the key", () => {
    fetchMock.mockImplementation(() => Promise.resolve(okJson({ rows: [] })));

    renderDetail(agentDetailFixture({ color: "cyan" }));
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));

    const color = screen.getByRole("combobox", { name: "Color" });
    expect(color).toHaveValue("cyan");
    expect(
      Array.from((color as HTMLSelectElement).options).map((option) => option.value),
    ).toEqual(["", "red", "blue", "green", "yellow", "purple", "orange", "pink", "cyan"]);
  });

  it("renders the boolean-ish contract fields as toggles that can also unset the key", () => {
    fetchMock.mockImplementation(() => Promise.resolve(okJson({ rows: [] })));

    renderDetail(agentDetailFixture({ allowedSubagents: "true", isolation: "worktree" }));
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));

    const subagents = screen.getByRole("group", { name: "Allowed Subagents" });
    expect(
      within(subagents).getAllByRole("button").map((button) => button.textContent),
    ).toEqual(["Unset", "true", "false"]);
    expect(within(subagents).getByRole("button", { name: "true" })).toHaveAttribute(
      "data-active",
      "true",
    );

    const isolation = screen.getByRole("group", { name: "Isolation" });
    expect(
      within(isolation).getAllByRole("button").map((button) => button.textContent),
    ).toEqual(["Unset", "worktree", "none"]);
    expect(within(isolation).getByRole("button", { name: "worktree" })).toHaveAttribute(
      "data-active",
      "true",
    );
  });

  it("shows the max_turns default as a placeholder instead of prefilling the field", () => {
    fetchMock.mockImplementation(() => Promise.resolve(okJson({ rows: [] })));

    renderDetail(agentDetailFixture());
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));

    const maxTurns = screen.getByRole("textbox", { name: "Max Turns" });
    expect(maxTurns).toHaveValue("");
    expect(maxTurns).toHaveAttribute(
      "placeholder",
      expect.stringContaining(String(MAX_TURNS_DEFAULT)),
    );
  });

  it("saves the added contract fields, and clears the ones the user unsets", async () => {
    fetchMock.mockImplementation((input, init) => {
      const url = String(input);
      if (url.includes("/api/agents/chief") && (init?.method || "GET") === "PUT") {
        return Promise.resolve(okJson({ ...agentDetailFixture(), ok: true }));
      }
      return Promise.resolve(okJson({ rows: [] }));
    });

    renderDetail(
      agentDetailFixture({ color: "cyan", allowedSubagents: "true", maxTurns: "30" }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Edit" }));

    const isolation = screen.getByRole("group", { name: "Isolation" });
    fireEvent.click(within(isolation).getByRole("button", { name: "worktree" }));

    const subagents = screen.getByRole("group", { name: "Allowed Subagents" });
    fireEvent.click(within(subagents).getByRole("button", { name: "Unset" }));

    fireEvent.change(screen.getByRole("textbox", { name: "Max Turns" }), {
      target: { value: "12" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      const put = fetchMock.mock.calls.find(
        (call) => String(call[0]).includes("/api/agents/chief") && call[1]?.method === "PUT",
      );
      expect(put).toBeDefined();
      expect(JSON.parse(put![1].body)).toMatchObject({
        color: "cyan",
        isolation: "worktree",
        maxTurns: "12",
        // An explicit empty string is what clears the key; omitting it would carry
        // the file's current value forward instead.
        allowedSubagents: "",
      });
    });
  });

  it("allows starring and unstarring a managed agent via title action", async () => {
    fetchMock.mockImplementation((input, init) => {
      const url = String(input);
      const method = init?.method || "GET";
      if (url.includes("/api/agents/chief/tags") && method === "PUT") {
        return Promise.resolve(okJson({ tags: ["starred", "backend"] }));
      }
      return Promise.resolve(okJson({ rows: [] }));
    });

    renderWithAppProviders(
      <AgentDetailContent
        detail={agentDetailFixture({ tags: ["backend"] })}
        pendingPerHarnessKeys={new Set()}
        onToggleHarness={vi.fn()}
        actionErrorMessage={null}
        onClose={vi.fn()}
        onDismissActionError={vi.fn()}
      />,
    );

    const starBtn = screen.getByRole("button", { name: "Star Chief of Staff" });
    expect(starBtn).toBeInTheDocument();
    fireEvent.click(starBtn);

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(
          (call) =>
            String(call[0]).includes("/api/agents/chief/tags") &&
            JSON.parse(call[1].body).tags.includes("starred"),
        ),
      ).toBe(true);
    });
  });

  it("allows adding and removing tags in detail view", async () => {
    fetchMock.mockImplementation((input, init) => {
      const url = String(input);
      const method = init?.method || "GET";
      if (url.includes("/api/agents/chief/tags") && method === "PUT") {
        return Promise.resolve(okJson({ tags: ["backend", "ops"] }));
      }
      return Promise.resolve(okJson({ rows: [] }));
    });

    renderWithAppProviders(
      <AgentDetailContent
        detail={agentDetailFixture({ tags: ["backend"] })}
        knownTags={["backend", "ops", "frontend"]}
        pendingPerHarnessKeys={new Set()}
        onToggleHarness={vi.fn()}
        actionErrorMessage={null}
        onClose={vi.fn()}
        onDismissActionError={vi.fn()}
      />,
    );

    expect(screen.getByText("backend")).toBeInTheDocument();

    // Add tag
    fireEvent.click(screen.getByRole("button", { name: /add tag/i }));
    const input = screen.getByPlaceholderText("Tag name...");
    fireEvent.change(input, { target: { value: "ops" } });
    fireEvent.click(screen.getByRole("button", { name: /confirm tag/i }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(
          (call) =>
            String(call[0]).includes("/api/agents/chief/tags") &&
            JSON.parse(call[1].body).tags.includes("ops"),
        ),
      ).toBe(true);
    });

    // Remove tag
    const removeBtn = screen.getByRole("button", { name: /remove tag backend/i });
    fireEvent.click(removeBtn);

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(
          (call) =>
            String(call[0]).includes("/api/agents/chief/tags") &&
            !JSON.parse(call[1].body).tags.includes("backend"),
        ),
      ).toBe(true);
    });
  });
});
