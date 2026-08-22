import { describe, expect, it } from "vitest";
import type {
  HookInventoryDto,
  HookInventoryEntryDto,
  HookInventoryColumnDto,
} from "../api/management-types";
import { filterHooks, filterHooksNeedsReview, matrixCellFor } from "./selectors";

describe("hooks selectors", () => {
  const column: HookInventoryColumnDto = {
    harness: "antigravity-hooks",
    label: "Antigravity",
    installed: true,
    configPresent: true,
    hooksWritable: true,
  };

  it("filterHooksNeedsReview returns only unmanaged entries and honors search", () => {
    const inventory: HookInventoryDto = {
      columns: [column],
      entries: [
        {
          id: "managed-1",
          displayName: "stop: echo done",
          kind: "managed",
          canEnable: true,
          enabledStatus: "enabled",
          sightings: [{ harness: "antigravity-hooks", state: "managed" }],
        },
        {
          id: "manual:abc",
          displayName: "pre_tool_use · shell: rtk hook",
          kind: "unmanaged",
          spec: { id: "", event: "pre_tool_use", command: "rtk hook", match: "shell", description: "", installedAt: "", revision: "" },
          canEnable: true,
          enabledStatus: "disabled",
          sightings: [{ harness: "antigravity-hooks", state: "unmanaged" }],
        },
      ],
      issues: [],
    };

    const all = filterHooksNeedsReview(inventory, "");
    expect(all.map((e) => e.id)).toEqual(["manual:abc"]);
    expect(filterHooksNeedsReview(inventory, "rtk")).toHaveLength(1);
    expect(filterHooksNeedsReview(inventory, "echo done")).toHaveLength(0);
    expect(filterHooksNeedsReview(null, "")).toEqual([]);
  });

  it("filterHooks harness filter keeps only entries sighted on the harness", () => {
    const inventory: HookInventoryDto = {
      columns: [
        column,
        { ...column, harness: "other-hooks", label: "Other" },
      ],
      entries: [
        {
          id: "managed-1",
          displayName: "stop: echo done",
          kind: "managed",
          canEnable: true,
          enabledStatus: "enabled",
          sightings: [{ harness: "antigravity-hooks", state: "managed" }],
        },
        {
          id: "managed-2",
          displayName: "post: echo other",
          kind: "managed",
          canEnable: true,
          enabledStatus: "enabled",
          sightings: [{ harness: "other-hooks", state: "managed" }],
        },
      ],
      issues: [],
    };

    expect(
      filterHooks(inventory, { search: "", status: "all", harness: "antigravity-hooks" }).map((e) => e.id),
    ).toEqual(["managed-1"]);
    expect(
      filterHooks(inventory, { search: "", status: "all", harness: "missing" }),
    ).toEqual([]);
  });

  it("appends caveat to tooltip for enabled hooks when caveat exists", () => {
    const entry: HookInventoryEntryDto = {
      id: "my-hook",
      displayName: "My Hook",
      kind: "managed",
      canEnable: true,
      enabledStatus: "enabled",
      sightings: [
        {
          harness: "antigravity-hooks",
          state: "managed",
          caveat: "On Antigravity this maps to PreInvocation, which fires before every model invocation, not only on user-prompt submit.",
        },
      ],
    };

    const cell = matrixCellFor(entry, column);
    expect(cell.state).toBe("enabled");
    expect(cell.tooltip).toBe(
      "Enabled on Antigravity (Caveat: On Antigravity this maps to PreInvocation, which fires before every model invocation, not only on user-prompt submit.)"
    );
  });

  it("appends caveat to tooltip for disabled/missing hooks when caveat exists", () => {
    const entry: HookInventoryEntryDto = {
      id: "my-hook",
      displayName: "My Hook",
      kind: "managed",
      canEnable: true,
      enabledStatus: "disabled",
      sightings: [
        {
          harness: "antigravity-hooks",
          state: "missing",
          caveat: "On Antigravity this maps to PreInvocation, which fires before every model invocation, not only on user-prompt submit.",
        },
      ],
    };

    const cell = matrixCellFor(entry, column);
    expect(cell.state).toBe("disabled");
    expect(cell.tooltip).toBe(
      "Disabled on Antigravity (Caveat: On Antigravity this maps to PreInvocation, which fires before every model invocation, not only on user-prompt submit.)"
    );
  });

  it("does not append caveat when caveat is absent", () => {
    const entry: HookInventoryEntryDto = {
      id: "my-hook",
      displayName: "My Hook",
      kind: "managed",
      canEnable: true,
      enabledStatus: "enabled",
      sightings: [
        {
          harness: "antigravity-hooks",
          state: "managed",
        },
      ],
    };

    const cell = matrixCellFor(entry, column);
    expect(cell.state).toBe("enabled");
    expect(cell.tooltip).toBe("Enabled on Antigravity");
  });
});
