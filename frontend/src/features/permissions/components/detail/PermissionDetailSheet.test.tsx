import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { okJson } from "../../../../test/fetch";
import { renderWithAppProviders } from "../../../../test/render";
import { PermissionDetailSheet } from "./PermissionDetailSheet";

const fetchMock = vi.fn();

function permissionDetailFixture(overrides?: Partial<Record<string, unknown>>) {
  return {
    id: "fs-read-project",
    displayName: "Read Project Files",
    kind: "managed",
    tags: ["security"],
    spec: {
      scope: "filesystem",
      decision: "allow",
      pattern: "./**",
      description: "Allow reading project workspace files",
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

describe("PermissionDetailSheet", () => {
  beforeEach(() => {
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders permission details and tags for managed permission", async () => {
    fetchMock.mockImplementation((input) => {
      const url = String(input);
      if (url.includes("/api/permissions/fs-read-project")) {
        return Promise.resolve(okJson(permissionDetailFixture()));
      }
      return Promise.resolve(okJson({}));
    });

    renderWithAppProviders(
      <PermissionDetailSheet
        id="fs-read-project"
        knownTags={["security", "fs"]}
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
      expect(screen.getByRole("heading", { name: "Read Project Files" })).toBeInTheDocument();
    });

    expect(screen.getByText("Allow reading project workspace files")).toBeInTheDocument();
    expect(screen.getByText("allow")).toBeInTheDocument();
    expect(screen.getByText("filesystem")).toBeInTheDocument();
    expect(screen.getByText("security")).toBeInTheDocument();
  });

  it("allows starring and unstarring managed permission via title action button", async () => {
    fetchMock.mockImplementation((input, init) => {
      const url = String(input);
      const method = init?.method || "GET";
      if (url.includes("/api/permissions/fs-read-project/tags") && method === "PUT") {
        return Promise.resolve(okJson({ tags: ["starred", "security"] }));
      }
      if (url.includes("/api/permissions/fs-read-project")) {
        return Promise.resolve(okJson(permissionDetailFixture({ tags: ["security"] })));
      }
      return Promise.resolve(okJson({}));
    });

    renderWithAppProviders(
      <PermissionDetailSheet
        id="fs-read-project"
        knownTags={["security", "fs"]}
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
      expect(screen.getByRole("button", { name: "Star Read Project Files" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Star Read Project Files" }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(
          (call) =>
            String(call[0]).includes("/api/permissions/fs-read-project/tags") &&
            JSON.parse(call[1].body).tags.includes("starred"),
        ),
      ).toBe(true);
    });
  });

  it("allows adding and removing tags for managed permission", async () => {
    fetchMock.mockImplementation((input, init) => {
      const url = String(input);
      const method = init?.method || "GET";
      if (url.includes("/api/permissions/fs-read-project/tags") && method === "PUT") {
        return Promise.resolve(okJson({ tags: ["security", "fs"] }));
      }
      if (url.includes("/api/permissions/fs-read-project")) {
        return Promise.resolve(okJson(permissionDetailFixture({ tags: ["security"] })));
      }
      return Promise.resolve(okJson({}));
    });

    renderWithAppProviders(
      <PermissionDetailSheet
        id="fs-read-project"
        knownTags={["security", "fs", "auth"]}
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
      expect(screen.getByText("security")).toBeInTheDocument();
    });

    // Add tag
    fireEvent.click(screen.getByRole("button", { name: /add tag/i }));
    const input = screen.getByPlaceholderText("Tag name...");
    fireEvent.change(input, { target: { value: "fs" } });
    fireEvent.click(screen.getByRole("button", { name: /confirm tag/i }));

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(
          (call) =>
            String(call[0]).includes("/api/permissions/fs-read-project/tags") &&
            JSON.parse(call[1].body).tags.includes("fs"),
        ),
      ).toBe(true);
    });

    // Remove tag
    const removeBtn = screen.getByRole("button", { name: /remove tag security/i });
    fireEvent.click(removeBtn);

    await waitFor(() => {
      expect(
        fetchMock.mock.calls.some(
          (call) =>
            String(call[0]).includes("/api/permissions/fs-read-project/tags") &&
            !JSON.parse(call[1].body).tags.includes("security"),
        ),
      ).toBe(true);
    });
  });
});
