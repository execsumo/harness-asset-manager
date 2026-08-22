import { describe, expect, it } from "vitest";

import type { AgentInventoryDto, AgentInventoryEntryDto } from "../api/types";
import { filterAgents } from "./selectors";

function makeEntry(
  ref: string,
  kind: "managed" | "unmanaged",
  bindings: AgentInventoryEntryDto["bindings"],
): AgentInventoryEntryDto {
  return {
    ref,
    name: ref,
    description: "",
    kind,
    harnessPath: null,
    bindings,
    actions: { canAdopt: false, canDelete: false },
  };
}

describe("agents selectors", () => {
  it("filterAgents harness filter keeps only entries bound on the harness", () => {
    const inventory: AgentInventoryDto = {
      columns: [
        { harness: "codex", label: "Codex", logoKey: null, installed: true },
        { harness: "claude", label: "Claude", logoKey: null, installed: true },
      ],
      entries: [
        makeEntry("planner", "managed", [{ harness: "codex", state: "enabled", detail: null }]),
        makeEntry("reviewer", "managed", [{ harness: "claude", state: "disabled", detail: null }]),
        makeEntry("helper", "unmanaged", [{ harness: "codex", state: "enabled", detail: null }]),
      ],
      issues: [],
    };

    expect(filterAgents(inventory, { search: "", status: "all", harness: "codex" }).map((e) => e.ref)).toEqual([
      "planner",
      "helper",
    ]);
    // A merely-disabled binding does not count as touching the harness.
    expect(filterAgents(inventory, { search: "", status: "all", harness: "claude" })).toEqual([]);
    expect(filterAgents(inventory, { search: "", status: "untracked", harness: "claude" })).toEqual([]);
    // Unsupported bindings do not count as touching the harness.
    const unsupported = {
      ...inventory,
      entries: [makeEntry("ghost", "managed", [{ harness: "codex", state: "unsupported", detail: null }])],
    };
    expect(filterAgents(unsupported, { search: "", status: "all", harness: "codex" })).toEqual([]);
  });
});
