import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createRouteFetchMock, errorJson, okJson } from "../../../test/fetch";
import { renderWithAppProviders } from "../../../test/render";
import SlashCommandsPage from "./SlashCommandsPage";

const fetchMock = vi.fn();

describe("SlashCommandsPage", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    window.localStorage.clear();
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  it("creates a command with selected targets", async () => {
    const requests: Array<{ url: string; body: unknown }> = [];
    fetchMock.mockImplementation(
      createRouteFetchMock([
        {
          match: (url, _input, init) => url === "/api/slash-commands" && init?.method === "POST",
          response: (url: string, _input: RequestInfo | URL, init?: RequestInit) => {
            requests.push({ url, body: JSON.parse(String(init?.body)) });
            return okJson({
              ok: true,
              command: slashCommandsPayload({
                commands: [
                  {
                    name: "code-review",
                    description: "Review code",
                    prompt: "$ARGUMENTS",
                    syncTargets: [],
                  },
                ],
              }).commands[0],
              sync: [],
            });
          },
        },
        { match: "/api/slash-commands", response: slashCommandsPayload() },
      ]),
    );

    renderWithAppProviders(<SlashCommandsPage />);

    await waitFor(() => expect(screen.getByRole("heading", { name: "Slash Commands" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "New command" }));
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "code-review" } });
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "Review code" } });
    fireEvent.change(screen.getByLabelText("Prompt"), { target: { value: "$ARGUMENTS" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(requests).toHaveLength(1));
    expect(requests[0].body).toEqual({
      name: "code-review",
      description: "Review code",
      prompt: "$ARGUMENTS",
      targets: ["claude", "codex"],
    });

    const dialog = await screen.findByRole("dialog", { name: "Slash command details code-review" });
    expect(within(dialog).getByRole("heading", { name: "code-review", level: 2 })).toBeInTheDocument();
    expect(within(getDetailHeader(dialog, "slash-command-detail-shell__chrome")).queryByText("Managed command")).not.toBeInTheDocument();
    expect(within(dialog).getByRole("heading", { name: "About" })).toBeInTheDocument();
    expect(within(dialog).getByRole("heading", { name: "Document" })).toBeInTheDocument();
    expect(within(dialog).getByText("$ARGUMENTS")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "New slash command" })).not.toBeInTheDocument();
  });

  it("opens a read-only detail sheet with normalized sections", async () => {
    fetchMock.mockImplementation(
      createRouteFetchMock([
        {
          match: "/api/slash-commands",
          response: slashCommandsPayload({
            commands: [
              {
                name: "code-review",
                description: "Review code",
                prompt: "$ARGUMENTS",
                syncTargets: [
                  {
                    target: "claude",
                    path: "/tmp/home/.claude/commands/code-review.md",
                    status: "synced",
                  },
                  {
                    target: "codex",
                    path: "/tmp/home/.codex/prompts/not-written.md",
                    status: "not_selected",
                  },
                ],
              },
            ],
          }),
        },
      ]),
    );

    renderWithAppProviders(<SlashCommandsPage />);

    fireEvent.click(await screen.findByText("code-review"));

    const dialog = screen.getByRole("dialog", { name: "Slash command details code-review" });
    expect(within(dialog).getByRole("heading", { name: "code-review", level: 2 })).toBeInTheDocument();
    expect(within(dialog).queryByText("/code-review")).not.toBeInTheDocument();
    expect(within(dialog).queryByText("/prompts:code-review")).not.toBeInTheDocument();
    expect(within(dialog).queryByLabelText("Name")).not.toBeInTheDocument();
    expect(within(getDetailHeader(dialog, "slash-command-detail-shell__chrome")).queryByText("Managed command")).not.toBeInTheDocument();
    expect(within(dialog).getByRole("heading", { name: "About" })).toBeInTheDocument();
    expect(within(dialog).getByRole("heading", { name: "Document" })).toBeInTheDocument();
    expect(within(dialog).getByText("Review code")).toBeInTheDocument();

    const aboutHeading = within(dialog).getByRole("heading", { name: "About" });
    const documentHeading = within(dialog).getByRole("heading", { name: "Document" });
    const harnessesHeading = within(dialog).getByRole("heading", { name: "Harnesses" });
    expect(Boolean(aboutHeading.compareDocumentPosition(documentHeading) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(Boolean(documentHeading.compareDocumentPosition(harnessesHeading) & Node.DOCUMENT_POSITION_FOLLOWING)).toBe(true);
    expect(within(dialog).queryByRole("heading", { name: "Locations" })).not.toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole("button", { name: "Edit" }));
    expect(screen.getByDisplayValue("Review code")).toBeInTheDocument();
  });

  it("returns to read-only detail after editing a command", async () => {
    const requests: Array<{ url: string; body: unknown }> = [];
    let commands = [
      {
        name: "code-review",
        description: "Review code",
        prompt: "$ARGUMENTS",
        syncTargets: [
          {
            target: "claude",
            path: "/tmp/home/.claude/commands/code-review.md",
            status: "synced",
          },
        ],
      },
    ];

    fetchMock.mockImplementation(
      createRouteFetchMock([
        {
          match: (url, _input, init) => url === "/api/slash-commands/code-review" && init?.method === "PUT",
          response: (url: string, _input: RequestInfo | URL, init?: RequestInit) => {
            const parsedBody = JSON.parse(String(init?.body));
            requests.push({ url, body: parsedBody });
            const updated = {
              name: "code-review",
              description: parsedBody.description,
              prompt: parsedBody.prompt,
              syncTargets: [
                {
                  target: "claude",
                  path: "/tmp/home/.claude/commands/code-review.md",
                  status: "synced",
                },
              ],
            };
            commands = [updated];
            return okJson({
              ok: true,
              command: updated,
              sync: [],
            });
          },
        },
        {
          match: "/api/slash-commands",
          response: () => slashCommandsPayload({ commands }),
        },
      ]),
    );

    renderWithAppProviders(<SlashCommandsPage />);

    fireEvent.click(await screen.findByText("code-review"));
    let dialog = screen.getByRole("dialog", { name: "Slash command details code-review" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Edit" }));
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "Review code carefully" } });
    fireEvent.change(screen.getByLabelText("Prompt Body"), { target: { value: "Review this diff carefully." } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(requests).toHaveLength(1));
    expect(requests[0].body).toEqual({
      description: "Review code carefully",
      prompt: "Review this diff carefully.",
      targets: ["claude"],
      metadata: [],
    });

    dialog = await screen.findByRole("dialog", { name: "Slash command details code-review" });
    expect(within(dialog).getByText("Review code carefully")).toBeInTheDocument();
    expect(within(dialog).getByText("Review this diff carefully.")).toBeInTheDocument();
  });

  it("keeps the edit form open when saving fails", async () => {
    fetchMock.mockImplementation(
      createRouteFetchMock([
        {
          match: (url, _input, init) => url === "/api/slash-commands/code-review" && init?.method === "PUT",
          response: errorJson("Unable to save slash command."),
        },
        {
          match: "/api/slash-commands",
          response: slashCommandsPayload({
            commands: [
              {
                name: "code-review",
                description: "Review code",
                prompt: "$ARGUMENTS",
                syncTargets: [],
              },
            ],
          }),
        },
      ]),
    );

    renderWithAppProviders(<SlashCommandsPage />);

    fireEvent.click(await screen.findByText("code-review"));
    const dialog = screen.getByRole("dialog", { name: "Slash command details code-review" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Edit" }));
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "Review code carefully" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(screen.getByText("Unable to save slash command.")).toBeInTheDocument());
    expect(screen.getByLabelText("Description")).toHaveValue("Review code carefully");
  });

  it("keeps all sync targets unchecked when an existing command is disabled everywhere", async () => {
    fetchMock.mockImplementation(
      createRouteFetchMock([
        {
          match: "/api/slash-commands",
          response: slashCommandsPayload({
            commands: [
              {
                name: "print-1-9",
                description: "打印1-9",
                prompt: "用最简单的python打印最快的1-9",
                syncTargets: [
                  {
                    target: "claude",
                    path: "/tmp/home/.claude/commands/print-1-9.md",
                    status: "not_selected",
                  },
                  {
                    target: "codex",
                    path: "/tmp/home/.codex/prompts/print-1-9.md",
                    status: "not_selected",
                  },
                ],
              },
            ],
          }),
        },
      ]),
    );

    renderWithAppProviders(<SlashCommandsPage />);

    fireEvent.click(await screen.findByText("print-1-9"));

    const dialog = screen.getByRole("dialog", { name: "Slash command details print-1-9" });
    expect(within(dialog).getByRole("button", { name: "Enable Claude Code for print-1-9" })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Enable Codex for print-1-9" })).toBeInTheDocument();
  });

  it("toggles harnesses from the adopted command detail sheet", async () => {
    const requests: Array<{ url: string; body: unknown }> = [];
    fetchMock.mockImplementation(
      createRouteFetchMock([
        {
          match: (url, _input, init) => url === "/api/slash-commands/code-review/sync" && init?.method === "POST",
          response: (url: string, _input: RequestInfo | URL, init?: RequestInit) => {
            requests.push({ url, body: JSON.parse(String(init?.body)) });
            return okJson({
              ok: true,
              command: null,
              sync: [],
            });
          },
        },
        {
          match: "/api/slash-commands",
          response: slashCommandsPayload({
            commands: [
              {
                name: "code-review",
                description: "Review code",
                prompt: "$ARGUMENTS",
                syncTargets: [
                  {
                    target: "claude",
                    path: "/tmp/home/.claude/commands/code-review.md",
                    status: "synced",
                  },
                  {
                    target: "codex",
                    path: "/tmp/home/.codex/prompts/code-review.md",
                    status: "synced",
                  },
                ],
              },
            ],
          }),
        },
      ]),
    );

    renderWithAppProviders(<SlashCommandsPage />);

    fireEvent.click(await screen.findByText("code-review"));
    const dialog = screen.getByRole("dialog", { name: "Slash command details code-review" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Disable Codex for code-review" }));

    await waitFor(() => expect(requests).toHaveLength(1));
    expect(requests[0].body).toEqual({ targets: ["claude"] });
  });

  it("opens delete confirmation from detail with raw command name", async () => {
    fetchMock.mockImplementation(
      createRouteFetchMock([
        {
          match: "/api/slash-commands",
          response: slashCommandsPayload({
            commands: [
              {
                name: "code-review",
                description: "Review code",
                prompt: "$ARGUMENTS",
                syncTargets: [],
              },
            ],
          }),
        },
      ]),
    );

    renderWithAppProviders(<SlashCommandsPage />);

    fireEvent.click(await screen.findByText("code-review"));
    const dialog = screen.getByRole("dialog", { name: "Slash command details code-review" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete" }));

    expect(screen.getByRole("heading", { name: "Delete code-review?" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Delete /code-review?" })).not.toBeInTheDocument();
  });

  it("renders slash commands in the matrix", async () => {
    fetchMock.mockImplementation(
      createRouteFetchMock([
        {
          match: "/api/slash-commands",
          response: slashCommandsPayload({
            commands: [
              {
                name: "code-review",
                description: "Review code",
                prompt: "$ARGUMENTS",
                syncTargets: [
                  {
                    target: "claude",
                    path: "/tmp/home/.claude/commands/code-review.md",
                    status: "synced",
                  },
                ],
              },
            ],
          }),
        },
      ]),
    );

    renderWithAppProviders(<SlashCommandsPage />);

    expect(await screen.findByRole("table", { name: "Slash commands target matrix" })).toBeInTheDocument();
    expect(screen.getByText("code-review")).toBeInTheDocument();
    expect(screen.queryByText("/prompts:code-review")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Disable Claude Code for code-review")).toBeInTheDocument();
    expect(screen.getByLabelText("Enable Codex for code-review")).toBeInTheDocument();
    expect(screen.getByLabelText("Active on 1 of 2 targets")).toBeInTheDocument();
  });

  it("renders star buttons for starred and unstarred slash commands in the matrix and toggles star", async () => {
    const requests: Array<{ url: string; body: unknown }> = [];
    fetchMock.mockImplementation(
      createRouteFetchMock([
        {
          match: (url, _input, init) => url === "/api/slash-commands/summarize/tags" && init?.method === "PUT",
          response: (url: string, _input: RequestInfo | URL, init?: RequestInit) => {
            requests.push({ url, body: JSON.parse(String(init?.body)) });
            return okJson({ tags: ["starred", "review"] });
          },
        },
        {
          match: "/api/slash-commands",
          response: slashCommandsPayload({
            commands: [
              {
                name: "summarize",
                description: "Summarize text",
                prompt: "$ARGUMENTS",
                syncTargets: [],
                tags: ["review"],
              },
              {
                name: "explain",
                description: "Explain code",
                prompt: "$ARGUMENTS",
                syncTargets: [],
                tags: ["starred"],
              },
            ],
          }),
        },
      ]),
    );

    renderWithAppProviders(<SlashCommandsPage />);

    expect(await screen.findByRole("table", { name: "Slash commands target matrix" })).toBeInTheDocument();

    const unstarBtn = screen.getByRole("button", { name: "Unstar explain" });
    expect(unstarBtn).toBeInTheDocument();
    expect(unstarBtn.className).toContain("skill-star-btn--active");

    const starBtn = screen.getByRole("button", { name: "Star summarize" });
    expect(starBtn).toBeInTheDocument();
    expect(starBtn.className).not.toContain("skill-star-btn--active");

    fireEvent.click(starBtn);

    await waitFor(() => expect(requests).toHaveLength(1));
    expect(requests[0].body).toEqual({ tags: ["starred", "review"] });
  });
});

function slashCommandsPayload({
  commands = [],
}: {
  commands?: Array<{
    name: string;
    description: string;
    prompt: string;
    syncTargets: unknown[];
    tags?: string[];
  }>;
} = {}) {
  return {
    storePath: "/tmp/home/Library/Application Support/harnessam/slash-commands/commands",
    syncStatePath: "/tmp/home/Library/Application Support/harnessam/slash-commands/sync-state.json",
    targets: [
      {
        id: "claude",
        label: "Claude Code",
        rootPath: "/tmp/home/.claude",
        outputDir: "/tmp/home/.claude/commands",
        invocationPrefix: "/",
        renderFormat: "frontmatter_markdown",
        scope: "global",
        docsUrl: "https://code.claude.com/docs/en/slash-commands",
        fileGlob: "*.md",
        supportsFrontmatter: true,
        supportNote: null,
        enabled: true,
        available: true,
        defaultSelected: true,
      },
      {
        id: "codex",
        label: "Codex",
        rootPath: "/tmp/home/.codex",
        outputDir: "/tmp/home/.codex/prompts",
        invocationPrefix: "/prompts:",
        renderFormat: "frontmatter_markdown",
        scope: "global",
        docsUrl: "https://developers.openai.com/codex/custom-prompts",
        fileGlob: "*.md",
        supportsFrontmatter: true,
        supportNote: null,
        enabled: true,
        available: true,
        defaultSelected: true,
      },
    ],
    defaultTargets: ["claude", "codex"],
    commands,
    reviewCommands: [],
  };
}

function getDetailHeader(container: HTMLElement, className: string): HTMLElement {
  const header = container.querySelector(`.${className}`);
  expect(header).not.toBeNull();
  return header as HTMLElement;
}
