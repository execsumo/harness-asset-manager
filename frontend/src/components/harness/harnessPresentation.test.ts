import { describe, expect, it } from "vitest";

import { getHarnessPresentation } from "./harnessPresentation";

describe("getHarnessPresentation", () => {
  it("uses the harness family for scoped targets", () => {
    expect(getHarnessPresentation("hermes:coder")?.variant).toBe("hermes");
  });

  it("resolves Pi Agent to its logo", () => {
    expect(getHarnessPresentation("pi")?.variant).toBe("pi");
    expect(getHarnessPresentation("pi:default")?.variant).toBe("pi");
  });

  it("keeps unknown families absent", () => {
    expect(getHarnessPresentation("nope:x")).toBeNull();
  });
});
