/**
 * Drop a leading YAML frontmatter block from an agent document.
 *
 * `AgentDetail.document` is the whole file, frontmatter included, so that raw and
 * unmanaged agents preview as the file they really are. Handing that to a Markdown
 * renderer turns the block into a bold heading: a run of text followed by a `---`
 * line *is* a setext H2, and the frontmatter's closing delimiter is that line.
 *
 * Only a block opening on line 1 counts. A `---` further down the body is a
 * horizontal rule the author wrote, not a delimiter, and must survive.
 */
export function stripFrontmatter(document: string): string {
  const lines = document.split("\n");
  if (lines[0]?.trim() !== "---") return document;
  const close = lines.findIndex((line, index) => index > 0 && line.trim() === "---");
  if (close === -1) return document;
  return lines.slice(close + 1).join("\n").replace(/^\n+/, "");
}
