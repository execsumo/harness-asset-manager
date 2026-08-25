import { describe, expect, it } from "vitest";

import { buildOverviewModel } from "./overview";

describe("capability overview model", () => {
  it("builds per-harness coverage across all capabilities", () => {
    const model = buildOverviewModel(
      {
        summary: { managed: 2, unmanaged: 1 },
        harnessColumns: [
          { harness: "codex", label: "Codex", installed: true },
        ],
        rows: [
          {
            skillRef: "audit",
            name: "audit",
            description: "",
            displayStatus: "Managed",
            tags: [],
            actions: { canDelete: true, canManage: true, canStopManaging: true },
            conformance: [],
            cells: [
              { harness: "codex", label: "Codex", state: "enabled", interactive: true },
              { harness: "claude", label: "Claude", state: "found", interactive: false },
            ],
          },
        ],
      },
      {
        storePath: "/tmp/harnessam/slash-commands/commands",
        syncStatePath: "/tmp/harnessam/slash-commands/sync-state.json",
        targets: [
          {
            id: "codex",
            label: "Codex",
            rootPath: "/tmp",
            outputDir: "",
            invocationPrefix: "",
            renderFormat: "frontmatter_markdown",
            scope: "global",
            docsUrl: "",
            fileGlob: "",
            supportsFrontmatter: true,
            defaultSelected: true,
            enabled: true,
            available: true,
            installed: true,
          },
        ],
        defaultTargets: ["codex"],
        commands: [
          {
            name: "code-review",
            description: "Review code",
            prompt: "$ARGUMENTS",
            syncTargets: [
              { target: "codex", status: "synced", path: "/tmp/.codex/prompts/code-review.md", error: null },
              { target: "claude", status: "drifted", path: "/tmp/.claude/commands/code-review.md", error: null },
            ],
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
      },
      {
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
            spec: null,
            canEnable: true,
            enabledStatus: "disabled",
            availabilityStatus: "unavailable",
            mcpStatus: { kind: "unchecked", reason: null },
            installConfigStatus: { hasFields: false, missingRequired: [], configured: true },
            sightings: [
              { harness: "codex", state: "managed", driftDetail: null },
              { harness: "claude", state: "drifted", driftDetail: null },
            ],
          },
        ],
        issues: [],
      },
      {
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
        ],
        entries: [
          {
            id: "pre-commit",
            displayName: "Pre-commit",
            kind: "managed",
            canEnable: true,
            enabledStatus: "enabled",
            spec: null,
            sightings: [{ harness: "codex", state: "managed", driftDetail: null }],
          },
        ],
        issues: [],
      },
      {
        columns: [
          {
            harness: "codex",
            label: "Codex",
            logoKey: "codex",
            installed: true,
            configPresent: true,
            permissionsWritable: true,
            permissionsUnavailableReason: null,
          },
        ],
        entries: [],
        issues: [],
      },
      {
        columns: [{ harness: "claude", label: "Claude", logoKey: "claude", installed: true }],
        entries: [
          {
            ref: "helper",
            name: "helper",
            description: "",
            kind: "unmanaged",
            harnessPath: "/tmp/.claude/agents/helper.md",
            bindings: [{ harness: "claude", state: "enabled", detail: null }],
            actions: { canAdopt: true, canDelete: false },
          },
        ],
        issues: [],
      },
    );

    const rows = Object.fromEntries(model.harnessRows.map((row) => [row.harness, row]));

    expect(Object.keys(rows)).toEqual(["codex", "claude"]);
    expect(rows.codex?.cells).toEqual({
      skills: { active: 1, review: 0 },
      commands: { active: 1, review: 1 },
      mcp: { active: 1, review: 0 },
      hooks: { active: 1, review: 0 },
      permissions: { active: 0, review: 0 },
      agents: { active: 0, review: 0 },
    });
    expect(rows.claude?.cells).toEqual({
      skills: { active: 0, review: 1 },
      commands: { active: 0, review: 0 },
      mcp: { active: 0, review: 1 },
      hooks: { active: 0, review: 0 },
      permissions: { active: 0, review: 0 },
      agents: { active: 0, review: 1 },
    });
    expect(rows.claude?.availabilityIssues).toEqual([
      { capability: "MCP", reason: "Claude MCP writes are unavailable" },
    ]);
    expect(rows.codex?.availabilityIssues).toEqual([]);

    // Catalog-level totals, agnostic of any single harness.
    expect(model.totalsRow.cells).toEqual({
      skills: { active: 2, review: 1 },
      commands: { active: 1, review: 1 },
      mcp: { active: 1, review: 1 },
      hooks: { active: 1, review: 0 },
      permissions: { active: 0, review: 0 },
      agents: { active: 0, review: 1 },
    });

    expect(model.reviewItems.length).toBeGreaterThan(0);
  });

  it("turns each skill conformance issue into its own linked notice", () => {
    const model = buildOverviewModel(
      {
        summary: { managed: 1, unmanaged: 0 },
        harnessColumns: [],
        rows: [
          {
            skillRef: "shared:creative-ideation",
            name: "ideation",
            description: "",
            displayStatus: "Managed",
            tags: [],
            actions: { canDelete: true, canManage: false, canStopManaging: true },
            cells: [],
            conformance: [
              {
                code: "name_directory_mismatch",
                message: "`name` is `ideation` but the package directory is `creative-ideation`.",
              },
              { code: "description_missing", message: "No `description` field." },
            ],
          },
        ],
      },
      null,
      null,
      null,
      null,
      null,
    );

    // One notice per issue, never a count: the panel has to say what to correct
    // and link to the asset that needs correcting.
    // The canonical route, not the legacy redirect: a redirect drops `?skill=`.
    expect(model.conformanceNotices.every((n) => n.to.startsWith("/skills?"))).toBe(true);
    expect(model.conformanceNotices).toEqual([
      {
        key: "shared:creative-ideation:name_directory_mismatch",
        asset: "ideation",
        message: "`name` is `ideation` but the package directory is `creative-ideation`.",
        to: "/skills?skill=shared%3Acreative-ideation",
      },
      {
        key: "shared:creative-ideation:description_missing",
        asset: "ideation",
        message: "No `description` field.",
        to: "/skills?skill=shared%3Acreative-ideation",
      },
    ]);
  });

  it("has no notices when every skill conforms", () => {
    const model = buildOverviewModel(
      {
        summary: { managed: 1, unmanaged: 0 },
        harnessColumns: [],
        rows: [
          {
            skillRef: "shared:tidy",
            name: "tidy",
            description: "d",
            displayStatus: "Managed",
            tags: [],
            actions: { canDelete: true, canManage: false, canStopManaging: true },
            cells: [],
            conformance: [],
          },
        ],
      },
      null,
      null,
      null,
      null,
      null,
    );

    // The canonical route, not the legacy redirect: a redirect drops `?skill=`.
    expect(model.conformanceNotices.every((n) => n.to.startsWith("/skills?"))).toBe(true);
    expect(model.conformanceNotices).toEqual([]);
  });
});
