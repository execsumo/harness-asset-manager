# Agent Skills specification — triage

**Status: awaiting owner approval. Nothing here is implemented.**

Source of truth: <https://agentskills.io/specification>, fetched 2026-08-25. Every
"spec says" cell below is from that fetch, not from a summary. Every "HAM today"
cell was verified against this checkout on the same day — the checks are named so
they can be re-run.

The task is *not* to implement the specification. Much of it is authoring guidance
— how to write a good skill — and HAM manages skills, it does not write them. Only
the **structural** parts are candidates, and only where HAM can actually support
them.

---

## The table

| # | Spec item | Spec says | Kind | HAM today | Can HAM support it | In / Out | Why |
|---|---|---|---|---|---|---|---|
| 1 | Directory layout | A skill is a directory containing at minimum `SKILL.md`; `scripts/`, `references/`, `assets/` and any other files are optional | Structural | Enforced on read (`find_skill_roots` requires a dir with `SKILL.md`) and preserved on write (`copytree`, directory symlinks). The detail view now lists package contents. | Already does | **In — shipped** | This is item 5 of the queue. Landed ahead of this triage. |
| 2 | Nested `metadata:` map | Optional `metadata` field, "a map from string keys to string values" | Structural | **Broken.** `parse_skill_document` is a flat line parser: it reads `metadata:` as an empty value and hoists `author`/`version` to top level. Saving a document through HAM rewrites `metadata:\n  author: x` as `metadata: ""` + `author: x`. | Yes — the parser needs to represent one level of nesting | **In — recommend fixing** | Silent data loss on a spec-conformant file, in HAM's own write path. This is the only row that is a live defect rather than a missing feature. |
| 3 | `name` charset / length rules | 1–64 chars; lowercase `a-z`, `0-9`, hyphens; no leading, trailing or consecutive hyphens | Structural | No validation whatsoever — `PDF-Processing`, `-pdf`, `pdf--processing`, and a 100-char name all parse unchanged. | Yes, as a **warning** | **Owner's call — recommend surface, do not enforce** | HAM uses `name` as the *display* name, and adopted skills in the live store use title-case display names. Enforcing would make existing, working skills invalid. Surfacing "does not meet the Agent Skills naming rules" costs nothing and breaks nothing. |
| 4 | `name` must match the parent directory | "Must match the parent directory name" | Structural | Never checked. HAM keys everything on the directory name (`package_dir`) and treats `name` as display text, so the two are free to disagree. | Yes, as a warning | **Owner's call — recommend surface, do not enforce** | Same reason as #3, and the same fix surfaces both. HAM's identity model does not depend on the rule holding, so enforcing it buys nothing and would invalidate real skills. |
| 5 | `name` is required | Required field | Structural | Not required — an absent `name` silently falls back to the first `# H1` in the body. | Yes, as a warning | **Owner's call — recommend surface, do not enforce** | The fallback is load-bearing for skills already in the store. Reporting "no `name` field" is honest; refusing to read the skill is not. |
| 6 | `description` required, 1–1024 chars, non-empty | Required | Structural | Parsed and displayed; never validated for presence or length. | Yes, as a warning | **Owner's call — recommend surface, do not enforce** | Folds into the same validation surface as #3–#5. Nothing else in HAM depends on it. |
| 7 | `license` | Optional; license name or reference to a bundled file | Structural (a declared field) | Round-trips intact — flat scalar, surfaced as a metadata row, written back verbatim. | Already does | **Out — nothing to do** | Works today by virtue of the generic passthrough. Giving it a dedicated labelled row is presentation polish, not spec conformance. |
| 8 | `compatibility` | Optional; max 500 chars; environment requirements | Structural | Round-trips intact, same as `license`. Length never checked. | Already does | **Out — nothing to do** | As #7. The length cap could join the #3–#6 warning surface if that is built. |
| 9 | `allowed-tools` | Optional; space-separated string of pre-approved tools. **Marked Experimental by the spec.** | Structural | Round-trips intact — verified, the value survives parse and re-render unchanged. | Already does | **Out** | The spec itself says support "may vary between agent implementations". Building anything on an experimental field invites a rewrite. Passthrough is the right level of commitment. |
| 10 | `scripts/` conventions ("self-contained", "helpful error messages", "handle edge cases") | Recommendation | **Authoring** | n/a | n/a | **Out** | Advice to skill authors. HAM does not write skills. |
| 11 | `references/` conventions (`REFERENCE.md`, `FORMS.md`, keep files focused) | Recommendation | **Authoring** | n/a | n/a | **Out** | As #10. HAM now *shows* the folder (item 1); what goes in it is the author's business. |
| 12 | `assets/` conventions (templates, images, data files) | Recommendation | **Authoring** | n/a | n/a | **Out** | As #10. |
| 13 | Progressive disclosure (metadata ≈100 tokens at startup, body <5000 tokens on activation, resources on demand) | Recommendation | **Authoring** — and a *client* concern | n/a — HAM never loads a skill into a model | No, and it should not | **Out** | This describes how an *agent runtime* consumes a skill. HAM installs skills for harnesses; the harness does the loading. Not HAM's layer. |
| 14 | "Keep `SKILL.md` under 500 lines" | Recommendation | **Authoring** | n/a | Could be measured | **Out** | A style guideline for authors. Measuring it would produce a warning nobody asked for on skills that work fine. |
| 15 | File references one level deep, relative from skill root | Recommendation | **Authoring** | n/a | n/a | **Out** | Advice about how to write the body. |
| 16 | `skills-ref validate ./my-skill` | Tooling pointer | Structural-adjacent | Not used. | Possible — a new external dependency | **Out unless asked** | It would settle #3–#6 in one call, but it is a new dependency on a third-party binary, and `CLAUDE.md` says no new dependency without asking. Raising it, not taking it. |

---

## What the table adds up to

- **One live defect: #2.** A spec-conformant nested `metadata:` map is silently
  destroyed by HAM's own document editor. This is the only row that is a bug rather
  than a gap, and it is the only one I would recommend implementing without further
  discussion.

- **One coherent optional feature: #3–#6 (+ #8's length cap).** A single
  "conformance" surface on Skills detail that *reports* where a skill departs from
  the Agent Skills naming and metadata rules, without refusing to manage it. One
  decision to make once, not four. **The judgement is the owner's**: HAM's display
  names and directory-keyed identity mean enforcement would invalidate skills that
  work today, which is why every one of those rows recommends surface-not-enforce.

- **Everything else is either already handled or is not HAM's problem.** Rows 7–9
  work through the existing frontmatter passthrough; rows 10–15 are authoring
  guidance; row 16 is a dependency question.

## Notes on scope

- The spec's own layout example matches what HAM already round-trips; nothing in the
  directory-structure section needs work beyond item 5, which has shipped.
- No row here proposes changing skill *identity*. HAM keys skills on the package
  directory, and the spec's rule that `name` must equal that directory would, if
  enforced, retroactively invalidate adopted skills. Left alone deliberately.
