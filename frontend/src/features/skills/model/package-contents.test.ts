import { describe, expect, it } from "vitest";

import { groupPackageFiles } from "./package-contents";

describe("groupPackageFiles", () => {
  it("keeps root files as their own entries and folds directories together", () => {
    expect(
      groupPackageFiles([
        "SKILL.md",
        "README.md",
        "references/a.md",
        "references/b.md",
        "scripts/run.sh",
      ]),
    ).toEqual([
      { name: "references", isDirectory: true, executable: false, files: ["a.md", "b.md"] },
      { name: "scripts", isDirectory: true, executable: true, files: ["run.sh"] },
      { name: "README.md", isDirectory: false, executable: false, files: [] },
      { name: "SKILL.md", isDirectory: false, executable: false, files: [] },
    ]);
  });

  it("flags scripts/ as executable material, whatever its depth", () => {
    const groups = groupPackageFiles(["scripts/nested/tool.py"]);

    expect(groups).toEqual([
      { name: "scripts", isDirectory: true, executable: true, files: ["nested/tool.py"] },
    ]);
  });

  it("returns nothing for an empty package", () => {
    expect(groupPackageFiles([])).toEqual([]);
  });
});
