import { describe, expect, it } from "vitest";

import type { SkillsWorkspaceData } from "./types";
import {
  countAdoptableLocalSkillRows,
  countNeedsReviewRows,
  extractSkillTagCounts,
  filterNeedsReviewRows,
  filterSkills,
  filterSkillsInUseRows,
  resetSkillsNeedsReviewFilters,
  resetSkillsInUseFilters,
} from "./selectors";

const data: SkillsWorkspaceData = {
  summary: { managed: 2, unmanaged: 1 },
  harnessColumns: [{ harness: "codex", label: "Codex", installed: true }],
  rows: [
    {
      skillRef: "shared:shared-audit",
      name: "Shared Audit",
      description: "Shared audit workflow",
      displayStatus: "Managed",
      tags: ["starred", "devops"],
      actions: { canManage: false, canStopManaging: true, canDelete: false },
      cells: [{ harness: "codex", label: "Codex", state: "disabled", interactive: true }],
    },
    {
      skillRef: "shared:audit-skill",
      name: "Audit Skill",
      description: "Locally modified audit workflow",
      displayStatus: "Managed",
      tags: ["core", "security"],
      actions: { canManage: false, canStopManaging: true, canDelete: true },
      cells: [{ harness: "codex", label: "Codex", state: "enabled", interactive: true }],
    },
    {
      skillRef: "unmanaged:trace-lens",
      name: "Trace Lens",
      description: "Trace review workflow",
      displayStatus: "Unmanaged",
      tags: ["devops"],
      actions: { canManage: true, canStopManaging: false, canDelete: false },
      cells: [{ harness: "codex", label: "Codex", state: "found", interactive: false }],
    },
  ],
} as unknown as SkillsWorkspaceData;

describe("skills workspace model", () => {
  it("harness filter keeps only rows enabled or found on the harness", () => {
    // "shared-audit" is adopted but merely disabled on codex — it must NOT match.
    const codexOnly = filterSkills(data, { search: "", status: "all", harness: "codex" });
    expect(codexOnly.map((row) => row.skillRef)).toEqual([
      "shared:audit-skill",
      "unmanaged:trace-lens",
    ]);
    const missingHarness = filterSkills(data, { search: "", status: "all", harness: "claude" });
    expect(missingHarness).toHaveLength(0);
  });

  it("filters skills by single tag and multiple tags with OR semantics", () => {
    const starredOnly = filterSkills(data, { search: "", status: "all", tags: ["starred"] });
    expect(starredOnly.map((row) => row.skillRef)).toEqual(["shared:shared-audit"]);

    const devopsOnly = filterSkills(data, { search: "", status: "all", tags: ["devops"] });
    expect(devopsOnly.map((row) => row.skillRef)).toEqual([
      "shared:shared-audit",
      "unmanaged:trace-lens",
    ]);

    // OR within tags: matches either 'starred' or 'core'
    const multiTags = filterSkills(data, { search: "", status: "all", tags: ["starred", "core"] });
    expect(multiTags.map((row) => row.skillRef)).toEqual([
      "shared:shared-audit",
      "shared:audit-skill",
    ]);

    // Composes AND with status filter
    const devopsEnabled = filterSkills(data, { search: "", status: "enabled", tags: ["devops"] });
    // shared-audit is disabled, trace-lens is unmanaged (not in-use enabled)
    expect(devopsEnabled).toHaveLength(0);
  });

  it("extracts unique tag counts with starred pinned first", () => {
    const tagCounts = extractSkillTagCounts(data);
    expect(tagCounts).toEqual([
      { tag: "starred", count: 1, isStarred: true },
      { tag: "core", count: 1, isStarred: false },
      { tag: "devops", count: 2, isStarred: false },
      { tag: "security", count: 1, isStarred: false },
    ]);
  });

  it("partitions in-use and needs-review rows correctly", () => {
    const inUseRows = filterSkillsInUseRows(data, resetSkillsInUseFilters());
    const needsReviewRows = filterNeedsReviewRows(data, resetSkillsNeedsReviewFilters());

    expect(inUseRows.map((row) => row.name)).toEqual(["Shared Audit", "Audit Skill"]);
    expect(needsReviewRows.map((row) => row.name)).toEqual(["Trace Lens"]);
  });

  it("treats locally modified shared-store entries as in-use rows", () => {
    expect(filterSkillsInUseRows(data, resetSkillsInUseFilters()).map((row) => row.name)).toEqual([
      "Shared Audit",
      "Audit Skill",
    ]);
  });

  it("searches only user-visible row content and harness labels", () => {
    expect(filterSkillsInUseRows(data, { search: "codex" }).map((row) => row.name)).toEqual([
      "Shared Audit",
      "Audit Skill",
    ]);
    expect(filterSkillsInUseRows(data, { search: "managed" })).toEqual([]);
    expect(filterSkillsInUseRows(data, { search: "local changes" })).toEqual([]);
  });

  it("counts needs-review rows and adoptable actions", () => {
    expect(countNeedsReviewRows(data)).toBe(1);
    expect(countAdoptableLocalSkillRows(data)).toBe(1);
  });
});

