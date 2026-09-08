import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  AgentSkillsFieldEditor,
  deriveSkillTagOptions,
} from "./AgentSkillsFieldEditor";

describe("AgentSkillsFieldEditor", () => {
  const knownSkills = [
    { slug: "code-review", name: "Code Review" },
    { slug: "test-debugging", name: "Test Debugging" },
    { slug: "perf-audit", name: "Performance Audit" },
  ];

  it("renders chips with display names and handles removal", () => {
    const onChange = vi.fn();
    render(
      <AgentSkillsFieldEditor
        skills={["code-review", "test-debugging"]}
        knownSkills={knownSkills}
        onChange={onChange}
      />,
    );

    expect(screen.getByText("Code Review")).toBeInTheDocument();
    expect(screen.getByText("Test Debugging")).toBeInTheDocument();

    const removeBtn = screen.getByRole("button", { name: "Remove skill Code Review" });
    fireEvent.click(removeBtn);
    expect(onChange).toHaveBeenCalledWith(["test-debugging"]);
  });

  it("suggests adopted skills as user types and adds on click", () => {
    const onChange = vi.fn();
    render(
      <AgentSkillsFieldEditor
        skills={["code-review"]}
        knownSkills={knownSkills}
        onChange={onChange}
      />,
    );

    const input = screen.getByRole("combobox", { name: "Attach skill" });
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "test" } });

    const option = screen.getByRole("option", { name: /Test Debugging/i });
    expect(option).toBeInTheDocument();

    fireEvent.mouseDown(option);
    expect(onChange).toHaveBeenCalledWith(["code-review", "test-debugging"]);
  });

  it("adds skill on Enter key", () => {
    const onChange = vi.fn();
    render(
      <AgentSkillsFieldEditor
        skills={[]}
        knownSkills={knownSkills}
        onChange={onChange}
      />,
    );

    const input = screen.getByRole("combobox", { name: "Attach skill" });
    fireEvent.change(input, { target: { value: "perf-audit" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onChange).toHaveBeenCalledWith(["perf-audit"]);
  });

  it("prevents duplicate skill attachments case-insensitively", () => {
    const onChange = vi.fn();
    render(
      <AgentSkillsFieldEditor
        skills={["code-review"]}
        knownSkills={knownSkills}
        onChange={onChange}
      />,
    );

    const input = screen.getByRole("combobox", { name: "Attach skill" });
    fireEvent.change(input, { target: { value: "CODE-REVIEW" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByText("Skill already attached")).toBeInTheDocument();
  });

  it("removes last chip on Backspace when input is empty", () => {
    const onChange = vi.fn();
    render(
      <AgentSkillsFieldEditor
        skills={["code-review", "test-debugging"]}
        knownSkills={knownSkills}
        onChange={onChange}
      />,
    );

    const input = screen.getByRole("combobox", { name: "Attach skill" });
    fireEvent.keyDown(input, { key: "Backspace" });

    expect(onChange).toHaveBeenCalledWith(["code-review"]);
  });

  it("offers every adopted skill on an empty input, not a silent first page", () => {
    const many = Array.from({ length: 12 }, (_, index) => ({
      slug: `skill-${index}`,
      name: `Skill ${index}`,
    }));
    render(<AgentSkillsFieldEditor skills={[]} knownSkills={many} onChange={vi.fn()} />);

    fireEvent.focus(screen.getByRole("combobox", { name: "Attach skill" }));

    expect(screen.getAllByRole("option")).toHaveLength(many.length);
    expect(screen.getByRole("option", { name: /Skill 11/ })).toBeInTheDocument();
  });

  describe("tag collections", () => {
    const tagOptions = [
      { tag: "quality", skills: ["code-review", "test-debugging"] },
      { tag: "perf", skills: ["perf-audit"] },
      { tag: "empty-tag", skills: [] },
    ];

    it("renders quick-pick tag pills and attaches every slug on pick", () => {
      const onChange = vi.fn();
      render(
        <AgentSkillsFieldEditor
          skills={[]}
          knownSkills={knownSkills}
          tagOptions={tagOptions}
          onChange={onChange}
        />,
      );

      const qualityBtn = screen.getByRole("button", { name: "quality" });
      expect(qualityBtn).toBeInTheDocument();
      const perfBtn = screen.getByRole("button", { name: "perf" });
      expect(perfBtn).toBeInTheDocument();

      fireEvent.click(qualityBtn);
      expect(onChange).toHaveBeenCalledWith(["code-review", "test-debugging"]);
    });

    it("does not duplicate already-attached slugs and preserves existing order", () => {
      const onChange = vi.fn();
      render(
        <AgentSkillsFieldEditor
          skills={["test-debugging"]}
          knownSkills={knownSkills}
          tagOptions={tagOptions}
          onChange={onChange}
        />,
      );

      // "quality" has ["code-review", "test-debugging"]. "test-debugging" is already attached.
      const qualityBtn = screen.getByRole("button", { name: "quality" });
      fireEvent.click(qualityBtn);

      // Current skills first, followed by missing slugs ("code-review")
      expect(onChange).toHaveBeenCalledWith(["test-debugging", "code-review"]);
    });

    it("deduplicates pre-existing case-variant slugs while preserving their first occurrence", () => {
      const onChange = vi.fn();
      render(
        <AgentSkillsFieldEditor
          skills={["custom", "CODE-REVIEW", "code-review"]}
          knownSkills={knownSkills}
          tagOptions={tagOptions}
          onChange={onChange}
        />,
      );

      fireEvent.click(screen.getByRole("button", { name: "quality" }));

      expect(onChange).toHaveBeenCalledWith(["custom", "CODE-REVIEW", "test-debugging"]);
    });

    it("does not render empty collections", () => {
      render(
        <AgentSkillsFieldEditor
          skills={[]}
          knownSkills={knownSkills}
          tagOptions={tagOptions}
          onChange={vi.fn()}
        />,
      );

      expect(screen.queryByRole("button", { name: "empty-tag" })).not.toBeInTheDocument();
    });

    it("hides/omits collections whose slugs are all already attached", () => {
      render(
        <AgentSkillsFieldEditor
          skills={["code-review", "test-debugging"]}
          knownSkills={knownSkills}
          tagOptions={tagOptions}
          onChange={vi.fn()}
        />,
      );

      // "quality" has both code-review and test-debugging, which are both attached -> omitted
      expect(screen.queryByRole("button", { name: "quality" })).not.toBeInTheDocument();
      // "perf" has perf-audit, which is not attached -> visible
      expect(screen.getByRole("button", { name: "perf" })).toBeInTheDocument();
    });

    it("ignores tag picks in disabled state", () => {
      const onChange = vi.fn();
      render(
        <AgentSkillsFieldEditor
          skills={[]}
          knownSkills={knownSkills}
          tagOptions={tagOptions}
          onChange={onChange}
          disabled={true}
        />,
      );

      const qualityBtn = screen.getByRole("button", { name: "quality" });
      expect(qualityBtn).toBeDisabled();

      fireEvent.click(qualityBtn);
      expect(onChange).not.toHaveBeenCalled();
    });

    it("derives tag collections from knownSkills when tagOptions is omitted", () => {
      const onChange = vi.fn();
      const skillsWithTags = [
        { slug: "code-review", name: "Code Review", tags: ["dev-tools"] },
        { slug: "test-debugging", name: "Test Debugging", tags: ["dev-tools", "qa"] },
      ];

      render(
        <AgentSkillsFieldEditor
          skills={[]}
          knownSkills={skillsWithTags}
          onChange={onChange}
        />,
      );

      const devToolsBtn = screen.getByRole("button", { name: "dev-tools" });
      expect(devToolsBtn).toBeInTheDocument();

      fireEvent.click(devToolsBtn);
      expect(onChange).toHaveBeenCalledWith(["code-review", "test-debugging"]);
    });

    it("deduplicates case-variant duplicates within the same tag option", () => {
      const onChange = vi.fn();
      const customTagOptions = [
        { tag: "mixed", skills: ["lint-slug", "LINT-SLUG", "lint-slug", "format-slug"] },
      ];

      render(
        <AgentSkillsFieldEditor
          skills={[]}
          knownSkills={knownSkills}
          tagOptions={customTagOptions}
          onChange={onChange}
        />,
      );

      fireEvent.click(screen.getByRole("button", { name: "mixed" }));
      expect(onChange).toHaveBeenCalledWith(["lint-slug", "format-slug"]);
    });

    it("restores tag option pill when an attached skill is removed", () => {
      const { rerender } = render(
        <AgentSkillsFieldEditor
          skills={["code-review", "test-debugging"]}
          knownSkills={knownSkills}
          tagOptions={tagOptions}
          onChange={vi.fn()}
        />,
      );

      // All slugs in quality are attached, so quality pill is omitted
      expect(screen.queryByRole("button", { name: "quality" })).not.toBeInTheDocument();

      // Simulate removal of "test-debugging"
      rerender(
        <AgentSkillsFieldEditor
          skills={["code-review"]}
          knownSkills={knownSkills}
          tagOptions={tagOptions}
          onChange={vi.fn()}
        />,
      );

      // Quality pill should now be visible again
      expect(screen.getByRole("button", { name: "quality" })).toBeInTheDocument();
    });

    it("preserves free-form chip addition and tag picks together", () => {
      const onChange = vi.fn();
      render(
        <AgentSkillsFieldEditor
          skills={["custom-freeform-skill"]}
          knownSkills={knownSkills}
          tagOptions={tagOptions}
          onChange={onChange}
        />,
      );

      expect(screen.getByText("custom-freeform-skill")).toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: "perf" }));
      expect(onChange).toHaveBeenCalledWith(["custom-freeform-skill", "perf-audit"]);
    });
  });

  describe("deriveSkillTagOptions", () => {
    it("derives and groups tags from skill table rows and filters unmanaged/non-shared", () => {
      const rows = [
        { skillRef: "shared:review", displayStatus: "Managed", tags: ["quality", "dev"] },
        { skillRef: "shared:test", displayStatus: "Managed", tags: ["quality", "qa"] },
        { skillRef: "unmanaged:custom", displayStatus: "Unmanaged", tags: ["quality"] },
      ];

      const options = deriveSkillTagOptions(rows);

      // "quality" has review and test (custom is unmanaged and not shared, so skipped)
      // sorted alphabetically: dev, qa, quality
      expect(options).toEqual([
        { tag: "dev", skills: ["review"] },
        { tag: "qa", skills: ["test"] },
        { tag: "quality", skills: ["review", "test"] },
      ]);
    });

    it("derives and groups tags from adopted skills with slug", () => {
      const items = [
        { slug: "lint", name: "Linter", tags: ["code"] },
        { slug: "format", name: "Formatter", tags: ["code"] },
      ];

      const options = deriveSkillTagOptions(items);
      expect(options).toEqual([
        { tag: "code", skills: ["lint", "format"] },
      ]);
    });

    it("returns empty array for empty or null input", () => {
      expect(deriveSkillTagOptions([])).toEqual([]);
      expect(deriveSkillTagOptions(null)).toEqual([]);
      expect(deriveSkillTagOptions(undefined)).toEqual([]);
    });
  });
});
