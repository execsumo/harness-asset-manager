import { describe, expect, it } from "vitest";

import { getHarnessPresentation } from "./harnessPresentation";

describe("getHarnessPresentation", () => {
  it("uses the harness family for scoped targets", () => {
    expect(getHarnessPresentation("hermes:coder")?.variant).toBe("hermes");
  });

  it("keeps unknown families absent", () => {
    expect(getHarnessPresentation("nope:x")).toBeNull();
  });
});
