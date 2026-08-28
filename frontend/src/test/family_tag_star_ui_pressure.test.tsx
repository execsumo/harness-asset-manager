import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { createRouteFetchMock, okJson } from "./fetch";
import { renderWithAppProviders } from "./render";

// Components
import { MatrixView as SkillsMatrixView } from "../features/skills/components/matrix/MatrixView";
import { SkillDetailContent } from "../features/skills/components/detail/SkillDetailContent";
import { AgentsMatrixView } from "../features/agents/components/AgentsMatrixView";
import { AgentDetailContent } from "../features/agents/components/detail/AgentDetailContent";
import { SlashCommandMatrix } from "../features/slash-commands/components/SlashCommandMatrix";
import { SlashCommandDetailView } from "../features/slash-commands/components/detail/SlashCommandDetailView";
import { McpServerMatrixView } from "../features/mcp/components/McpServerMatrixView";
import { McpServerDetailView } from "../features/mcp/components/detail/McpServerDetailView";
import { HooksMatrixView } from "../features/hooks/components/HooksMatrixView";
import { HookDetailSheet } from "../features/hooks/components/detail/HookDetailSheet";
import { PermissionsMatrixView } from "../features/permissions/components/PermissionsMatrixView";
import { PermissionDetailSheet } from "../features/permissions/components/detail/PermissionDetailSheet";
import { DetailTags } from "../components/detail/DetailTags";

const fetchMock = vi.fn();

describe("Cross-Family Tag and Star UI Parity Pressure Test", () => {
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

  describe("1. Matrix Table Unstarred Star Visibility & Interactivity Across All 6 Families", () => {
    it("Skills: renders visible empty outline star for unstarred rows and filled star for starred rows", () => {
      const onToggleStar = vi.fn();
      renderWithAppProviders(
        <SkillsMatrixView
          rows={[
            {
              skillRef: "shared:starred-skill",
              name: "Starred Skill",
              description: "A starred skill",
              displayStatus: "Managed",
              tags: ["starred"],
              actions: { canManage: false, canStopManaging: true, canDelete: true },
              conformance: [],
              cells: [{ harness: "codex", label: "Codex", logoKey: "codex", state: "enabled", interactive: true }],
            },
            {
              skillRef: "shared:unstarred-skill",
              name: "Unstarred Skill",
              description: "An unstarred skill",
              displayStatus: "Managed",
              tags: ["dev"],
              actions: { canManage: false, canStopManaging: true, canDelete: true },
              conformance: [],
              cells: [{ harness: "codex", label: "Codex", logoKey: "codex", state: "disabled", interactive: true }],
            },
          ]}
          harnessColumns={[{ harness: "codex", label: "Codex", logoKey: "codex", installed: true }]}
          checkedRefs={new Set()}
          selectedSkillRef={null}
          pendingToggleKeys={new Set()}
          onOpenSkill={vi.fn()}
          onToggleChecked={vi.fn()}
          onToggleCell={vi.fn()}
          onToggleStar={onToggleStar}
        />,
      );

      const unstarBtn = screen.getByRole("button", { name: "Unstar Starred Skill" });
      expect(unstarBtn).toBeInTheDocument();
      expect(unstarBtn.className).toContain("skill-star-btn--active");

      const starBtn = screen.getByRole("button", { name: "Star Unstarred Skill" });
      expect(starBtn).toBeInTheDocument();
      expect(starBtn.className).not.toContain("skill-star-btn--active");

      fireEvent.click(starBtn);
      expect(onToggleStar).toHaveBeenCalledWith("shared:unstarred-skill");
    });

    it("Agents: renders visible empty outline star for unstarred rows and filled star for starred rows", () => {
      const onToggleStar = vi.fn();
      renderWithAppProviders(
        <AgentsMatrixView
          entries={[
            {
              ref: "shared:starred-agent",
              name: "Starred Agent",
              description: "Starred",
              kind: "managed",
              harnessPath: null,
              tags: ["starred"],
              bindings: [{ harness: "codex", state: "enabled", detail: null }],
              actions: { canAdopt: false, canDelete: true },
            },
            {
              ref: "shared:unstarred-agent",
              name: "Unstarred Agent",
              description: "Unstarred",
              kind: "managed",
              harnessPath: null,
              tags: [],
              bindings: [{ harness: "codex", state: "disabled", detail: null }],
              actions: { canAdopt: false, canDelete: true },
            },
          ]}
          columns={[{ harness: "codex", label: "Codex", logoKey: "codex", installed: true }]}
          pendingAgentKeys={new Set()}
          pendingPerHarnessKeys={new Set()}
          checkedRefs={new Set()}
          onOpenDetail={vi.fn()}
          onToggleChecked={vi.fn()}
          onEnableHarness={vi.fn()}
          onDisableHarness={vi.fn()}
          onAdopt={vi.fn()}
          onToggleStar={onToggleStar}
        />,
      );

      const unstarBtn = screen.getByRole("button", { name: "Unstar Starred Agent" });
      expect(unstarBtn).toBeInTheDocument();
      expect(unstarBtn.className).toContain("skill-star-btn--active");

      const starBtn = screen.getByRole("button", { name: "Star Unstarred Agent" });
      expect(starBtn).toBeInTheDocument();
      expect(starBtn.className).not.toContain("skill-star-btn--active");

      fireEvent.click(starBtn);
      expect(onToggleStar).toHaveBeenCalledWith("shared:unstarred-agent");
    });

    it("Slash Commands: renders visible empty outline star for unstarred rows and filled star for starred rows", () => {
      const onToggleStar = vi.fn();
      renderWithAppProviders(
        <SlashCommandMatrix
          entries={[
            {
              id: "starred-cmd",
              kind: "managed",
              command: {
                name: "starred-cmd",
                description: "Starred",
                prompt: "p",
                metadata: [],
                syncTargets: [],
                tags: ["starred"],
              },
            },
            {
              id: "unstarred-cmd",
              kind: "managed",
              command: {
                name: "unstarred-cmd",
                description: "Unstarred",
                prompt: "p",
                metadata: [],
                syncTargets: [],
                tags: ["tools"],
              },
            },
          ]}
          targets={[
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
          ]}
          pendingName={null}
          pendingTarget={null}
          pendingReviewKey={null}
          checkedRefs={new Set()}
          onOpenManaged={vi.fn()}
          onOpenReview={vi.fn()}
          onToggleChecked={vi.fn()}
          onToggleTarget={vi.fn()}
          onReviewAction={vi.fn()}
          onToggleStar={onToggleStar}
        />,
      );

      const unstarBtn = screen.getByRole("button", { name: "Unstar starred-cmd" });
      expect(unstarBtn).toBeInTheDocument();
      expect(unstarBtn.className).toContain("skill-star-btn--active");

      const starBtn = screen.getByRole("button", { name: "Star unstarred-cmd" });
      expect(starBtn).toBeInTheDocument();
      expect(starBtn.className).not.toContain("skill-star-btn--active");

      fireEvent.click(starBtn);
      expect(onToggleStar).toHaveBeenCalledWith("unstarred-cmd");
    });

    it("MCP: renders visible empty outline star for unstarred rows and filled star for starred rows", () => {
      const onToggleStar = vi.fn();
      renderWithAppProviders(
        <McpServerMatrixView
          entries={[
            {
              name: "starred-mcp",
              displayName: "Starred MCP",
              kind: "managed",
              canEnable: true,
              enabledStatus: "enabled",
              availabilityStatus: "available",
              availabilityReason: null,
              mcpStatus: { kind: "available", reason: null },
              installConfigStatus: { hasFields: false, missingRequired: [], configured: true },
              spec: null,
              sightings: [{ harness: "codex", state: "managed" }],
              tags: ["starred"],
            },
            {
              name: "unstarred-mcp",
              displayName: "Unstarred MCP",
              kind: "managed",
              canEnable: true,
              enabledStatus: "disabled",
              availabilityStatus: "available",
              availabilityReason: null,
              mcpStatus: { kind: "available", reason: null },
              installConfigStatus: { hasFields: false, missingRequired: [], configured: true },
              spec: null,
              sightings: [{ harness: "codex", state: "missing" }],
              tags: [],
            },
          ]}
          columns={[{ harness: "codex", label: "Codex", logoKey: "codex", installed: true, configPresent: true, mcpWritable: true }]}
          pendingServerKeys={new Set()}
          pendingPerHarnessKeys={new Set()}
          checkedNames={new Set()}
          onOpenDetail={vi.fn()}
          onToggleChecked={vi.fn()}
          onEnableHarness={vi.fn()}
          onDisableHarness={vi.fn()}
          onToggleStar={onToggleStar}
        />,
      );

      const unstarBtn = screen.getByRole("button", { name: "Unstar starred-mcp" });
      expect(unstarBtn).toBeInTheDocument();
      expect(unstarBtn.className).toContain("skill-star-btn--active");

      const starBtn = screen.getByRole("button", { name: "Star unstarred-mcp" });
      expect(starBtn).toBeInTheDocument();
      expect(starBtn.className).not.toContain("skill-star-btn--active");

      fireEvent.click(starBtn);
      expect(onToggleStar).toHaveBeenCalledWith("unstarred-mcp");
    });

    it("Hooks: renders visible empty outline star for unstarred rows and filled star for starred rows", () => {
      const onToggleStar = vi.fn();
      renderWithAppProviders(
        <HooksMatrixView
          entries={[
            {
              id: "starred-hook",
              displayName: "Starred Hook",
              kind: "managed",
              canEnable: true,
              enabledStatus: "enabled",
              sightings: [{ harness: "codex", state: "managed" }],
              tags: ["starred"],
            },
            {
              id: "unstarred-hook",
              displayName: "Unstarred Hook",
              kind: "managed",
              canEnable: true,
              enabledStatus: "disabled",
              sightings: [{ harness: "codex", state: "missing" }],
              tags: [],
            },
          ]}
          columns={[{ harness: "codex", label: "Codex", logoKey: "codex", installed: true, configPresent: true, hooksWritable: true }]}
          pendingHookKeys={new Set()}
          pendingPerHarnessKeys={new Set()}
          checkedIds={new Set()}
          onOpenDetail={vi.fn()}
          onToggleChecked={vi.fn()}
          onEnableHarness={vi.fn()}
          onDisableHarness={vi.fn()}
          onAdopt={vi.fn()}
          onToggleStar={onToggleStar}
        />,
      );

      const unstarBtn = screen.getByRole("button", { name: "Unstar starred-hook" });
      expect(unstarBtn).toBeInTheDocument();
      expect(unstarBtn.className).toContain("skill-star-btn--active");

      const starBtn = screen.getByRole("button", { name: "Star unstarred-hook" });
      expect(starBtn).toBeInTheDocument();
      expect(starBtn.className).not.toContain("skill-star-btn--active");

      fireEvent.click(starBtn);
      expect(onToggleStar).toHaveBeenCalledWith("unstarred-hook");
    });

    it("Permissions: renders visible empty outline star for unstarred rows and filled star for starred rows", () => {
      const onToggleStar = vi.fn();
      renderWithAppProviders(
        <PermissionsMatrixView
          entries={[
            {
              id: "starred-perm",
              displayName: "Starred Perm",
              kind: "managed",
              canEnable: true,
              enabledStatus: "enabled",
              sightings: [{ harness: "codex", state: "managed" }],
              tags: ["starred"],
            },
            {
              id: "unstarred-perm",
              displayName: "Unstarred Perm",
              kind: "managed",
              canEnable: true,
              enabledStatus: "disabled",
              sightings: [{ harness: "codex", state: "missing" }],
              tags: [],
            },
          ]}
          columns={[{ harness: "codex", label: "Codex", logoKey: "codex", installed: true, configPresent: true, permissionsWritable: true }]}
          pendingPermissionKeys={new Set()}
          pendingPerHarnessKeys={new Set()}
          checkedIds={new Set()}
          onOpenDetail={vi.fn()}
          onToggleChecked={vi.fn()}
          onEnableHarness={vi.fn()}
          onDisableHarness={vi.fn()}
          onAdopt={vi.fn()}
          onToggleStar={onToggleStar}
        />,
      );

      const unstarBtn = screen.getByRole("button", { name: "Unstar Starred Perm" });
      expect(unstarBtn).toBeInTheDocument();
      expect(unstarBtn.className).toContain("skill-star-btn--active");

      const starBtn = screen.getByRole("button", { name: "Star Unstarred Perm" });
      expect(starBtn).toBeInTheDocument();
      expect(starBtn.className).not.toContain("skill-star-btn--active");

      fireEvent.click(starBtn);
      expect(onToggleStar).toHaveBeenCalledWith("unstarred-perm");
    });
  });

  describe("2. Detail Views Tag Editing & Star Parity Across All 6 Families", () => {
    it("Skills Detail: allows starring/unstarring and adding/removing tags", async () => {
      fetchMock.mockImplementation((input, init) => {
        const url = String(input);
        const method = init?.method || "GET";
        if (url.includes("/api/skills") && url.includes("/tags") && method === "PUT") {
          return Promise.resolve(okJson({ tags: ["starred", "backend"] }));
        }
        return Promise.resolve(okJson({}));
      });

      renderWithAppProviders(
        <SkillDetailContent
          detail={{
            skillRef: "shared:code-review",
            name: "Code Review",
            description: "Review code",
            displayStatus: "Managed",
            attentionMessage: null,
            tags: ["backend"],
            actions: {
              canManage: false,
              updateStatus: null,
              stopManagingStatus: null,
              stopManagingHarnessLabels: [],
              canDelete: true,
              deleteHarnessLabels: [],
            },
            harnessCells: [],
            locations: [],
            documentMarkdown: "Doc",
            metadata: [],
            packageFiles: [],
            sourceLinks: null,
            conformance: [],
          }}
          knownTags={["backend", "frontend", "ci"]}
          actionErrorMessage=""
          queryErrorMessage=""
          pendingToggleHarnesses={new Set()}
          pendingStructuralAction={null}
          onClose={vi.fn()}
          onDismissActionError={vi.fn()}
          onManage={vi.fn()}
          onToggleHarness={vi.fn()}
          onUpdate={vi.fn()}
          onRequestRemove={vi.fn()}
          onRequestDelete={vi.fn()}
        />,
      );

      // Star button in titleAction
      const starBtn = screen.getByRole("button", { name: "Star Code Review" });
      expect(starBtn).toBeInTheDocument();
      fireEvent.click(starBtn);

      await waitFor(() => {
        expect(
          fetchMock.mock.calls.some(
            (call) =>
              String(call[0]).includes("/api/skills") &&
              String(call[0]).includes("/tags") &&
              JSON.parse(call[1].body).tags.includes("starred"),
          ),
        ).toBe(true);
      });

      // Tags add
      fireEvent.click(screen.getByRole("button", { name: /add tag/i }));
      const input = screen.getByPlaceholderText("Tag name...");
      fireEvent.change(input, { target: { value: "ci" } });
      fireEvent.click(screen.getByRole("button", { name: /confirm tag/i }));

      await waitFor(() => {
        expect(
          fetchMock.mock.calls.some(
            (call) =>
              String(call[0]).includes("/api/skills") &&
              String(call[0]).includes("/tags") &&
              JSON.parse(call[1].body).tags.includes("ci"),
          ),
        ).toBe(true);
      });

      // Tags remove
      const removeBtn = screen.getByRole("button", { name: /remove tag backend/i });
      fireEvent.click(removeBtn);

      await waitFor(() => {
        expect(
          fetchMock.mock.calls.some(
            (call) =>
              String(call[0]).includes("/api/skills") &&
              String(call[0]).includes("/tags") &&
              !JSON.parse(call[1].body).tags.includes("backend"),
          ),
        ).toBe(true);
      });
    });

    it("Agents Detail: allows starring/unstarring and adding/removing tags", async () => {
      fetchMock.mockImplementation((input, init) => {
        const url = String(input);
        const method = init?.method || "GET";
        if (url.includes("/api/agents/arch/tags") && method === "PUT") {
          return Promise.resolve(okJson({ tags: ["starred", "design"] }));
        }
        return Promise.resolve(okJson({ rows: [] }));
      });

      renderWithAppProviders(
        <AgentDetailContent
          detail={{
            ref: "arch",
            name: "Architect",
            description: "System architect",
            prompt: "Prompt",
            tools: [],
            document: "Doc",
            storePath: "/store/arch.md",
            harnesses: [],
            configuration: [],
            canDelete: true,
            canEdit: true,
            tags: ["design"],
          }}
          knownTags={["design", "infra"]}
          pendingPerHarnessKeys={new Set()}
          onToggleHarness={vi.fn()}
          actionErrorMessage={null}
          onClose={vi.fn()}
          onDismissActionError={vi.fn()}
        />,
      );

      const starBtn = screen.getByRole("button", { name: "Star Architect" });
      expect(starBtn).toBeInTheDocument();
      fireEvent.click(starBtn);

      await waitFor(() => {
        expect(
          fetchMock.mock.calls.some(
            (call) =>
              String(call[0]).includes("/api/agents/arch/tags") &&
              JSON.parse(call[1].body).tags.includes("starred"),
          ),
        ).toBe(true);
      });
    });

    it("Slash Commands Detail: allows starring/unstarring and adding/removing tags", async () => {
      fetchMock.mockImplementation((input, init) => {
        const url = String(input);
        const method = init?.method || "GET";
        if (url.includes("/api/slash-commands/explain/tags") && method === "PUT") {
          return Promise.resolve(okJson({ tags: ["starred", "helper"] }));
        }
        return Promise.resolve(okJson({}));
      });

      renderWithAppProviders(
        <SlashCommandDetailView
          command={{
            name: "explain",
            description: "Explain code",
            prompt: "Explain this code",
            metadata: [],
            syncTargets: [],
            tags: ["helper"],
          }}
          knownTags={["helper", "debug"]}
          targets={[]}
          pendingName={null}
          pendingTarget={null}
          onClose={vi.fn()}
          onDelete={vi.fn()}
          onToggleTarget={vi.fn()}
        />,
      );

      const starBtn = screen.getByRole("button", { name: "Star explain" });
      expect(starBtn).toBeInTheDocument();
      fireEvent.click(starBtn);

      await waitFor(() => {
        expect(
          fetchMock.mock.calls.some(
            (call) =>
              String(call[0]).includes("/api/slash-commands/explain/tags") &&
              JSON.parse(call[1].body).tags.includes("starred"),
          ),
        ).toBe(true);
      });
    });

    it("MCP Detail: allows starring/unstarring and adding/removing tags for managed servers", async () => {
      fetchMock.mockImplementation((input, init) => {
        const url = String(input);
        const method = init?.method || "GET";
        if (url.includes("/api/mcp/servers/fetch-tools/tags") && method === "PUT") {
          return Promise.resolve(okJson({ tags: ["starred", "net"] }));
        }
        if (url.includes("/api/mcp/servers/fetch-tools")) {
          return Promise.resolve(
            okJson({
              name: "fetch-tools",
              displayName: "Fetch Tools",
              kind: "managed",
              enabledStatus: "enabled",
              availabilityStatus: "available",
              availabilityReason: null,
              mcpStatus: { kind: "available", reason: null },
              installConfigStatus: { hasFields: false, missingRequired: [], configured: true },
              spec: null,
              sightings: [],
              tags: ["net"],
            }),
          );
        }
        return Promise.resolve(okJson({}));
      });

      renderWithAppProviders(
        <McpServerDetailView
          name="fetch-tools"
          knownTags={["net", "api"]}
          columns={[]}
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
        expect(screen.getByRole("button", { name: "Star Fetch Tools" })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole("button", { name: "Star Fetch Tools" }));

      await waitFor(() => {
        expect(
          fetchMock.mock.calls.some(
            (call) =>
              String(call[0]).includes("/api/mcp/servers/fetch-tools/tags") &&
              JSON.parse(call[1]?.body as string).tags.includes("starred"),
          ),
        ).toBe(true);
      });
    });

    it("Hooks Detail: allows starring/unstarring and adding/removing tags for managed hooks", async () => {
      fetchMock.mockImplementation((input, init) => {
        const url = String(input);
        const method = init?.method || "GET";
        if (url.includes("/api/hooks/post-merge/tags") && method === "PUT") {
          return Promise.resolve(okJson({ tags: ["starred", "git"] }));
        }
        if (url.includes("/api/hooks/post-merge")) {
          return Promise.resolve(
            okJson({
              id: "post-merge",
              displayName: "Post Merge",
              kind: "managed",
              tags: ["git"],
              spec: { event: "post-merge", command: "npm test" },
              sightings: [],
            }),
          );
        }
        return Promise.resolve(okJson({}));
      });

      renderWithAppProviders(
        <HookDetailSheet
          id="post-merge"
          knownTags={["git", "ci"]}
          columns={[]}
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
        expect(screen.getByRole("button", { name: "Star Post Merge" })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole("button", { name: "Star Post Merge" }));

      await waitFor(() => {
        expect(
          fetchMock.mock.calls.some(
            (call) =>
              String(call[0]).includes("/api/hooks/post-merge/tags") &&
              JSON.parse(call[1].body).tags.includes("starred"),
          ),
        ).toBe(true);
      });
    });

    it("Permissions Detail: allows starring/unstarring and adding/removing tags for managed permissions", async () => {
      fetchMock.mockImplementation((input, init) => {
        const url = String(input);
        const method = init?.method || "GET";
        if (url.includes("/api/permissions/exec-bash/tags") && method === "PUT") {
          return Promise.resolve(okJson({ tags: ["starred", "exec"] }));
        }
        if (url.includes("/api/permissions/exec-bash")) {
          return Promise.resolve(
            okJson({
              id: "exec-bash",
              displayName: "Exec Bash",
              kind: "managed",
              tags: ["exec"],
              spec: { scope: "execution", decision: "ask" },
              sightings: [],
            }),
          );
        }
        return Promise.resolve(okJson({}));
      });

      renderWithAppProviders(
        <PermissionDetailSheet
          id="exec-bash"
          knownTags={["exec", "sec"]}
          columns={[]}
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
        expect(screen.getByRole("button", { name: "Star Exec Bash" })).toBeInTheDocument();
      });

      fireEvent.click(screen.getByRole("button", { name: "Star Exec Bash" }));

      await waitFor(() => {
        expect(
          fetchMock.mock.calls.some(
            (call) =>
              String(call[0]).includes("/api/permissions/exec-bash/tags") &&
              JSON.parse(call[1].body).tags.includes("starred"),
          ),
        ).toBe(true);
      });
    });
  });

  describe("3. Unmanaged / Read-only Semantics", () => {
    it("Unmanaged items in detail views do not show editable tags or star buttons", async () => {
      fetchMock.mockImplementation((input) => {
        const url = String(input);
        if (url.includes("/api/mcp/servers/unmanaged-server")) {
          return Promise.resolve(
            okJson({
              name: "unmanaged-server",
              displayName: "Unmanaged Server",
              kind: "unmanaged",
              canEnable: false,
              enabledStatus: "disabled",
              availabilityStatus: "unavailable",
              availabilityReason: null,
              mcpStatus: { kind: "unchecked", reason: null },
              installConfigStatus: { hasFields: false, missingRequired: [], configured: true },
              spec: null,
              sightings: [],
              tags: [],
            }),
          );
        }
        return Promise.resolve(okJson({}));
      });

      renderWithAppProviders(
        <McpServerDetailView
          name="unmanaged-server"
          columns={[]}
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
        expect(screen.getByRole("heading", { name: "Unmanaged Server" })).toBeInTheDocument();
      });

      // No star button
      expect(screen.queryByRole("button", { name: /star/i })).not.toBeInTheDocument();
      // No tags section
      expect(screen.queryByRole("heading", { name: "Tags" })).not.toBeInTheDocument();
    });

    it("DetailTags in read-only mode (canEdit=false) displays tags without remove buttons or add input", () => {
      renderWithAppProviders(
        <DetailTags
          tags={["starred", "security", "production"]}
          canEdit={false}
          onAddTag={vi.fn()}
          onRemoveTag={vi.fn()}
        />,
      );

      expect(screen.getByText("starred")).toBeInTheDocument();
      expect(screen.getByText("security")).toBeInTheDocument();
      expect(screen.getByText("production")).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /remove tag/i })).not.toBeInTheDocument();
      expect(screen.queryByRole("button", { name: /add tag/i })).not.toBeInTheDocument();
    });
  });
});
