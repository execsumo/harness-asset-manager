import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { okJson } from "../../../../test/fetch";
import { renderWithAppProviders } from "../../../../test/render";
import { SlashCommandDetailView } from "./SlashCommandDetailView";
import type { SlashCommandDto, SlashTargetDto } from "../../api/types";

const fetchMock = vi.fn();

function commandFixture(overrides?: Partial<SlashCommandDto>): SlashCommandDto {
  return {
    name: "summarize",
    description: "Summarize selected context",
    prompt: "Summarize this clearly.",
    metadata: [
      { key: "name", value: "summarize" },
      { key: "description", value: "Summarize selected context" },
    ],
    syncTargets: [
      {
        target: "claude",
        status: "synced",
        path: "/home/user/.claude/commands/summarize.md",
      },
    ],
    tags: ["review"],
    ...overrides,
  };
}

function targetsFixture(): SlashTargetDto[] {
  return [
    {
      id: "claude",
      label: "Claude Code",
      rootPath: "/tmp/.claude",
      outputDir: "/tmp/.claude/commands",
      invocationPrefix: "/",
      renderFormat: "frontmatter_markdown",
      scope: "global",
      docsUrl: "",
      fileGlob: "*.md",
      supportsFrontmatter: true,
      supportNote: null,
      enabled: true,
      available: true,
      defaultSelected: true,
      installed: true,
    },
    {
      id: "cursor",
      label: "Cursor",
      rootPath: "/tmp/.cursor",
      outputDir: "/tmp/.cursor/commands",
      invocationPrefix: "/",
      renderFormat: "frontmatter_markdown",
      scope: "global",
      docsUrl: "",
      fileGlob: "*.md",
      supportsFrontmatter: true,
      supportNote: null,
      enabled: true,
      available: true,
      defaultSelected: true,
      installed: true,
    },
  ];
}

describe("SlashCommandDetailView", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders command name, description, document preview, and tags", () => {
    renderWithAppProviders(
      <SlashCommandDetailView
        command={commandFixture()}
        knownTags={["review", "ai", "doc"]}
        targets={targetsFixture()}
        pendingName={null}
        pendingTarget={null}
        onClose={vi.fn()}
        onDelete={vi.fn()}
        onToggleTarget={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "summarize" })).toBeInTheDocument();
    expect(screen.getByText("Summarize selected context")).toBeInTheDocument();
    expect(screen.getByText("Summarize this clearly.")).toBeInTheDocument();
    expect(screen.getByText("review")).toBeInTheDocument();
  });

  it("allows starring and unstarring slash command via title action button", async () => {
    fetchMock.mockImplementation((input, init) => {
      const url = String(input);
      const method = init?.method || "GET";
      if (url.includes("/api/slash-commands/summarize/tags") && method === "PUT") {
        return Promise.resolve(okJson({ tags: ["starred", "review"] }));
      }
      return Promise.resolve(okJson({}));
    });

    renderWithAppProviders(
      <SlashCommandDetailView
        command={commandFixture({ tags: ["review"] })}
        knownTags={["review", "ai"]}
        targets={targetsFixture()}
        pendingName={null}
        pendingTarget={null}
        onClose={vi.fn()}
        onDelete={vi.fn()}
        onToggleTarget={vi.fn()}
      />,
    );

    const starBtn = screen.getByRole("button", { name: "Star summarize" });
    expect(starBtn).toBeInTheDocument();
    fireEvent.click(starBtn);

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(
          (call) =>
            String(call[0]).includes("/api/slash-commands/summarize/tags") &&
            JSON.parse(call[1].body).tags.includes("starred"),
        ),
      ).toBe(true);
    });
  });

  it("allows adding and removing tags in slash command detail view", async () => {
    fetchMock.mockImplementation((input, init) => {
      const url = String(input);
      const method = init?.method || "GET";
      if (url.includes("/api/slash-commands/summarize/tags") && method === "PUT") {
        return Promise.resolve(okJson({ tags: ["review", "doc"] }));
      }
      return Promise.resolve(okJson({}));
    });

    renderWithAppProviders(
      <SlashCommandDetailView
        command={commandFixture({ tags: ["review"] })}
        knownTags={["review", "doc", "ai"]}
        targets={targetsFixture()}
        pendingName={null}
        pendingTarget={null}
        onClose={vi.fn()}
        onDelete={vi.fn()}
        onToggleTarget={vi.fn()}
      />,
    );

    expect(screen.getByText("review")).toBeInTheDocument();

    // Add tag
    fireEvent.click(screen.getByRole("button", { name: /add tag/i }));
    const input = screen.getByPlaceholderText("Tag name...");
    fireEvent.change(input, { target: { value: "doc" } });
    fireEvent.click(screen.getByRole("button", { name: /confirm tag/i }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(
          (call) =>
            String(call[0]).includes("/api/slash-commands/summarize/tags") &&
            JSON.parse(call[1].body).tags.includes("doc"),
        ),
      ).toBe(true);
    });

    // Remove tag
    const removeBtn = screen.getByRole("button", { name: /remove tag review/i });
    fireEvent.click(removeBtn);

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(
          (call) =>
            String(call[0]).includes("/api/slash-commands/summarize/tags") &&
            !JSON.parse(call[1].body).tags.includes("review"),
        ),
      ).toBe(true);
    });
  });
});
