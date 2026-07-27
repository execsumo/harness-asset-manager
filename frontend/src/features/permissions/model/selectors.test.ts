import { describe, expect, it } from "vitest";
import type {
  PermissionInventoryEntryDto,
  PermissionInventoryColumnDto,
} from "../api/management-types";
import type { PermissionInventoryDto } from "../api/management-types";
import { filterPermissions, matrixCellFor, permissionsSummary } from "./selectors";

describe("permissions selectors", () => {
  const column: PermissionInventoryColumnDto = {
    harness: "antigravity-permissions",
    label: "Antigravity",
    installed: true,
    configPresent: true,
    permissionsWritable: true,
  };

  it("appends caveat to tooltip for enabled permissions when caveat exists", () => {
    const entry: PermissionInventoryEntryDto = {
      id: "my-permission",
      displayName: "My Permission",
      kind: "managed",
      canEnable: true,
      enabledStatus: "enabled",
      sightings: [
        {
          harness: "antigravity-permissions",
          state: "managed",
          caveat: "On Antigravity this maps to PreInvocation, which fires before every model invocation, not only on user-prompt submit.",
        },
      ],
    };

    const cell = matrixCellFor(entry, column);
    expect(cell.state).toBe("enabled");
    expect(cell.tooltip).toBe(
      "Applied on Antigravity (Caveat: On Antigravity this maps to PreInvocation, which fires before every model invocation, not only on user-prompt submit.)"
    );
  });

  it("appends caveat to tooltip for disabled/missing permissions when caveat exists", () => {
    const entry: PermissionInventoryEntryDto = {
      id: "my-permission",
      displayName: "My Permission",
      kind: "managed",
      canEnable: true,
      enabledStatus: "disabled",
      sightings: [
        {
          harness: "antigravity-permissions",
          state: "missing",
          caveat: "On Antigravity this maps to PreInvocation, which fires before every model invocation, not only on user-prompt submit.",
        },
      ],
    };

    const cell = matrixCellFor(entry, column);
    expect(cell.state).toBe("disabled");
    expect(cell.tooltip).toBe(
      "Not applied on Antigravity (Caveat: On Antigravity this maps to PreInvocation, which fires before every model invocation, not only on user-prompt submit.)"
    );
  });

  describe("filterPermissions (unified inventory)", () => {
    const inventory: PermissionInventoryDto = {
      columns: [column],
      entries: [
        {
          id: "managed-allow",
          displayName: "allow · shell: git push",
          kind: "managed",
          spec: { id: "", decision: "allow", scope: "shell", pattern: "git push", description: "", installedAt: "", revision: "" },
          canEnable: true,
          enabledStatus: "enabled",
          sightings: [{ harness: "antigravity-permissions", state: "managed" }],
        },
        {
          id: "managed-deny-unbound",
          displayName: "deny · shell: rm -rf",
          kind: "managed",
          spec: { id: "", decision: "deny", scope: "shell", pattern: "rm -rf", description: "", installedAt: "", revision: "" },
          canEnable: true,
          enabledStatus: "disabled",
          sightings: [{ harness: "antigravity-permissions", state: "missing" }],
        },
        {
          id: "manual:abc",
          displayName: "allow · shell: docker ps",
          kind: "unmanaged",
          spec: { id: "", decision: "allow", scope: "shell", pattern: "docker ps", description: "", installedAt: "", revision: "" },
          canEnable: true,
          enabledStatus: "disabled",
          sightings: [{ harness: "antigravity-permissions", state: "unmanaged" }],
        },
      ],
      issues: [],
    };

    const ids = (status: Parameters<typeof filterPermissions>[1]["status"], decision: Parameters<typeof filterPermissions>[1]["decision"] = "all") =>
      filterPermissions(inventory, { search: "", decision, status }).map((e) => e.id);

    it("returns managed and unmanaged rows together for status=all", () => {
      expect(ids("all")).toEqual(["managed-allow", "managed-deny-unbound", "manual:abc"]);
    });

    it("status=untracked returns only unmanaged rows", () => {
      expect(ids("untracked")).toEqual(["manual:abc"]);
    });

    it("status=applied / not-applied scope to managed rows by binding state", () => {
      expect(ids("applied")).toEqual(["managed-allow"]);
      expect(ids("not-applied")).toEqual(["managed-deny-unbound"]);
    });

    it("decision filter applies across kinds", () => {
      expect(ids("all", "deny")).toEqual(["managed-deny-unbound"]);
      expect(ids("all", "allow")).toEqual(["managed-allow", "manual:abc"]);
    });

    it("honors search and null inventory", () => {
      expect(filterPermissions(inventory, { search: "docker", decision: "all", status: "all" })).toHaveLength(1);
      expect(filterPermissions(null, { search: "", decision: "all", status: "all" })).toEqual([]);
    });

    it("permissionsSummary counts kinds", () => {
      expect(permissionsSummary(inventory)).toEqual({ total: 3, tracked: 2, untracked: 1, differs: 0 });
    });
  });

  it("does not append caveat when caveat is absent", () => {
    const entry: PermissionInventoryEntryDto = {
      id: "my-permission",
      displayName: "My Permission",
      kind: "managed",
      canEnable: true,
      enabledStatus: "enabled",
      sightings: [
        {
          harness: "antigravity-permissions",
          state: "managed",
        },
      ],
    };

    const cell = matrixCellFor(entry, column);
    expect(cell.state).toBe("enabled");
    expect(cell.tooltip).toBe("Applied on Antigravity");
  });
});
