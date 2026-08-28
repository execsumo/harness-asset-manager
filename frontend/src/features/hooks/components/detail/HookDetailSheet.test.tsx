import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { okJson } from "../../../../test/fetch";
import { renderWithAppProviders } from "../../../../test/render";
import { HookDetailSheet } from "./HookDetailSheet";

const fetchMock = vi.fn();

function hookDetailFixture(overrides?: Partial<Record<string, unknown>>) {
  return {
    id: "pre-commit-lint",
    displayName: "Pre-commit Lint",
    kind: "managed",
    tags: ["quality"],
    spec: {
      event: "pre-commit",
      command: "npm run lint",
      description: "Run linter before committing",
      match: "*.ts",
      timeout: 30,
    },
    sightings: [
      { harness: "claude", state: "managed" },
    ],
    configChoices: [],
    ...overrides,
  };
}

const columns = [
  { harness: "claude", label: "Claude Code", installed: true },
];

describe("HookDetailSheet", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders hook details and tags for managed hook", async () => {
    fetchMock.mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/api/hooks/pre-commit-lint")) {
        return Promise.resolve(okJson(hookDetailFixture()));
      }
      return Promise.resolve(okJson({}));
    });

    renderWithAppProviders(
      <HookDetailSheet
        id="pre-commit-lint"
        knownTags={["quality", "ci"]}
        columns={columns}
        pendingPerHarness={new Set()}
        isServerPending={false}
        isUninstalling={false}
        onClose={vi.fn()}
        onEnableHarness={vi.fn()}
        onDisableHarness={vi.fn()}
        onResolveConfig={vi.fn().mockResolvedValue(undefined)}
        onUninstall={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Pre-commit Lint" })).toBeInTheDocument();
    });

    expect(screen.getByText("Run linter before committing")).toBeInTheDocument();
    expect(screen.getByText("npm run lint")).toBeInTheDocument();
    expect(screen.getByText("quality")).toBeInTheDocument();
  });

  it("allows starring and unstarring managed hook via title action button", async () => {
    fetchMock.mockImplementation((input, init) => {
      const url = String(input);
      const method = init?.method || "GET";
      if (url.includes("/api/hooks/pre-commit-lint/tags") && method === "PUT") {
        return Promise.resolve(okJson({ tags: ["starred", "quality"] }));
      }
      if (url.includes("/api/hooks/pre-commit-lint")) {
        return Promise.resolve(okJson(hookDetailFixture({ tags: ["quality"] })));
      }
      return Promise.resolve(okJson({}));
    });

    renderWithAppProviders(
      <HookDetailSheet
        id="pre-commit-lint"
        knownTags={["quality", "ci"]}
        columns={columns}
        pendingPerHarness={new Set()}
        isServerPending={false}
        isUninstalling={false}
        onClose={vi.fn()}
        onEnableHarness={vi.fn()}
        onDisableHarness={vi.fn()}
        onResolveConfig={vi.fn().mockResolvedValue(undefined)}
        onUninstall={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Star Pre-commit Lint" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Star Pre-commit Lint" }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(
          (call) =>
            String(call[0]).includes("/api/hooks/pre-commit-lint/tags") &&
            JSON.parse(call[1].body).tags.includes("starred"),
        ),
      ).toBe(true);
    });
  });

  it("allows adding and removing tags for managed hook", async () => {
    fetchMock.mockImplementation((input, init) => {
      const url = String(input);
      const method = init?.method || "GET";
      if (url.includes("/api/hooks/pre-commit-lint/tags") && method === "PUT") {
        return Promise.resolve(okJson({ tags: ["quality", "ci"] }));
      }
      if (url.includes("/api/hooks/pre-commit-lint")) {
        return Promise.resolve(okJson(hookDetailFixture({ tags: ["quality"] })));
      }
      return Promise.resolve(okJson({}));
    });

    renderWithAppProviders(
      <HookDetailSheet
        id="pre-commit-lint"
        knownTags={["quality", "ci", "git"]}
        columns={columns}
        pendingPerHarness={new Set()}
        isServerPending={false}
        isUninstalling={false}
        onClose={vi.fn()}
        onEnableHarness={vi.fn()}
        onDisableHarness={vi.fn()}
        onResolveConfig={vi.fn().mockResolvedValue(undefined)}
        onUninstall={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("quality")).toBeInTheDocument();
    });

    // Add tag
    fireEvent.click(screen.getByRole("button", { name: /add tag/i }));
    const input = screen.getByPlaceholderText("Tag name...");
    fireEvent.change(input, { target: { value: "ci" } });
    fireEvent.click(screen.getByRole("button", { name: /confirm tag/i }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(
          (call) =>
            String(call[0]).includes("/api/hooks/pre-commit-lint/tags") &&
            JSON.parse(call[1].body).tags.includes("ci"),
        ),
      ).toBe(true);
    });

    // Remove tag
    const removeBtn = screen.getByRole("button", { name: /remove tag quality/i });
    fireEvent.click(removeBtn);

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(
          (call) =>
            String(call[0]).includes("/api/hooks/pre-commit-lint/tags") &&
            !JSON.parse(call[1].body).tags.includes("quality"),
        ),
      ).toBe(true);
    });
  });
});
