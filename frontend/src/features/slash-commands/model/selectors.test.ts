import { describe, expect, it } from "vitest";

import type { SlashCommandDto, SlashCommandReviewDto, SlashTargetId } from "../api/types";
import {
  countSyncedTargets,
  extractSlashCommandTagCounts,
  filterSlashCommandEntries,
  filterSlashCommands,
  filterSlashReviewRows,
  primaryReviewAction,
  reviewMetaText,
  slashCommandInventoryEntries,
  sortSlashCommands,
} from "./selectors";

describe("slash command selectors", () => {
  const commands: SlashCommandDto[] = [
    command("disabled-command", []),
    command("selective-command", ["codex"]),
    command("enabled-command", ["claude", "codex"]),
  ];

  it("harness filter keeps entries bound to the target harness", () => {
    const entries = slashCommandInventoryEntries({
      commands,
      reviewCommands: [reviewRow("missing", ["restore_managed"])],
    });
    expect(
      filterSlashCommandEntries(entries, "", "all", "codex").map((entry) => entry.id),
    ).toEqual([
      "selective-command",
      "enabled-command",
      "codex:code-review:missing",
    ]);
    expect(
      filterSlashCommandEntries(entries, "", "all", "claude").map((entry) => entry.id),
    ).toEqual(["enabled-command"]);
    // "not_selected" sync entries do not count as touching the target.
    const withUnselected = slashCommandInventoryEntries({
      commands: [
        command("disabled-command", []),
        {
          ...command("selective-command", ["codex"]),
          syncTargets: [
            ...command("selective-command", ["codex"]).syncTargets,
            { target: "claude", path: "/tmp/claude/x.md", status: "not_selected" },
          ],
        },
      ],
      reviewCommands: [],
    });
    expect(
      filterSlashCommandEntries(withUnselected, "", "all", "claude").map((entry) => entry.id),
    ).toEqual([]);
  });

  it("filters and counts coverage", () => {
    expect(filterSlashCommands(commands, "selective").map((item) => item.name)).toEqual([
      "selective-command",
    ]);
    expect(countSyncedTargets(commands[2])).toBe(2);
  });

  it("sorts by coverage and target columns", () => {
    expect(sortSlashCommands(commands, { key: "coverage", direction: "desc" }).map((item) => item.name)).toEqual([
      "enabled-command",
      "selective-command",
      "disabled-command",
    ]);
    expect(sortSlashCommands(commands, { key: { target: "codex" }, direction: "desc" }).map((item) => item.name)).toEqual([
      "enabled-command",
      "selective-command",
      "disabled-command",
    ]);
  });

  it("selects review actions and metadata for unmanaged, drifted, and missing rows", () => {
    const rows: SlashCommandReviewDto[] = [
      reviewRow("unmanaged", ["import"]),
      reviewRow("drifted", ["restore_managed", "adopt_target", "remove_binding"]),
      reviewRow("missing", ["restore_managed", "remove_binding"]),
    ];

    expect(filterSlashReviewRows(rows, "drifted").map((row) => row.kind)).toEqual(["drifted"]);
    expect(rows.map((row) => primaryReviewAction(row))).toEqual([
      "import",
      "restore_managed",
      "restore_managed",
    ]);
    expect(rows.map((row) => reviewMetaText(row))).toEqual([
      "Found in Codex",
      "Changed in Codex",
      "Missing from Codex",
    ]);
  });

  it("extracts tag counts and filters by tags", () => {
    const taggedCommands: SlashCommandDto[] = [
      { ...command("cmd1", ["codex"]), tags: ["starred", "devops"] },
      { ...command("cmd2", ["claude"]), tags: ["devops", "core"] },
      { ...command("cmd3", ["agy"]), tags: ["starred"] },
    ];

    const tagCounts = extractSlashCommandTagCounts(taggedCommands);
    expect(tagCounts).toEqual([
      { tag: "starred", count: 2, isStarred: true },
      { tag: "core", count: 1, isStarred: false },
      { tag: "devops", count: 2, isStarred: false },
    ]);

    const entries = slashCommandInventoryEntries({
      commands: taggedCommands,
      reviewCommands: [reviewRow("unmanaged", ["import"])],
    });

    const starredFiltered = filterSlashCommandEntries(entries, "", "all", null, ["starred"]);
    expect(starredFiltered.map((e) => e.id)).toEqual(["cmd1", "cmd3"]);

    const devopsFiltered = filterSlashCommandEntries(entries, "", "all", null, ["devops"]);
    expect(devopsFiltered.map((e) => e.id)).toEqual(["cmd1", "cmd2"]);
  });
});

function command(name: string, targets: SlashTargetId[]): SlashCommandDto {
  return {
    name,
    description: name,
    prompt: "$ARGUMENTS",
    syncTargets: targets.map((target) => ({
      target,
      path: `/tmp/${target}/${name}.md`,
      status: "synced",
    })),
  };
}

function reviewRow(kind: SlashCommandReviewDto["kind"], actions: SlashCommandReviewDto["actions"]): SlashCommandReviewDto {
  return {
    reviewRef: `codex:code-review:${kind}`,
    kind,
    target: "codex",
    targetLabel: "Codex",
    name: "code-review",
    path: "/tmp/home/.codex/prompts/code-review.md",
    description: "Review code",
    prompt: "$ARGUMENTS",
    commandExists: kind !== "unmanaged",
    canImport: actions.includes("import"),
    actions,
    error: null,
  };
}
