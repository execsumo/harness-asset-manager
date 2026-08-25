import { describe, expect, it } from "vitest";

import { stripFrontmatter } from "./document";

describe("stripFrontmatter", () => {
  it("drops a leading frontmatter block", () => {
    const document = ["---", "name: reviewer", "model: inherit", "---", "", "# Title"].join("\n");

    expect(stripFrontmatter(document)).toBe("# Title");
  });

  it("keeps a horizontal rule that is not a frontmatter delimiter", () => {
    const document = ["# Title", "", "---", "", "Body"].join("\n");

    expect(stripFrontmatter(document)).toBe(document);
  });

  it("only consumes the first block, leaving later rules alone", () => {
    const document = ["---", "name: reviewer", "---", "", "Intro", "", "---", "", "Outro"].join("\n");

    expect(stripFrontmatter(document)).toBe(["Intro", "", "---", "", "Outro"].join("\n"));
  });

  it("handles an empty frontmatter block", () => {
    expect(stripFrontmatter("---\n---\nBody")).toBe("Body");
  });

  it("leaves an unterminated block alone rather than eating the document", () => {
    const document = ["---", "name: reviewer", "", "Body"].join("\n");

    expect(stripFrontmatter(document)).toBe(document);
  });
});
