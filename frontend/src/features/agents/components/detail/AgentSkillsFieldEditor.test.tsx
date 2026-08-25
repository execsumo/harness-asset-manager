import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AgentSkillsFieldEditor } from "./AgentSkillsFieldEditor";

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
});
