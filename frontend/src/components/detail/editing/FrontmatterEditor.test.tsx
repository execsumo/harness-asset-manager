import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  FrontmatterEditor,
  parseFrontmatterFromYaml,
  serializeFrontmatterToYaml,
  type FrontmatterFieldGroup,
  type KnownFieldConfig,
  type OtherFrontmatterEntry,
} from "./FrontmatterEditor";

describe("FrontmatterEditor", () => {
  it("renders known fields and other frontmatter key/value rows", () => {
    const knownFields: KnownFieldConfig[] = [
      {
        key: "name",
        label: "Name",
        value: "my-skill",
        onChange: vi.fn(),
      },
      {
        key: "description",
        label: "Description",
        value: "my description",
        onChange: vi.fn(),
      },
    ];

    const otherEntries: OtherFrontmatterEntry[] = [
      { id: "1", key: "author", value: "Jane" },
      { id: "2", key: "version", value: "1.0.0" },
    ];

    render(
      <FrontmatterEditor
        knownFields={knownFields}
        otherEntries={otherEntries}
        onChangeOtherEntries={vi.fn()}
        rawYaml=""
        onChangeRawYaml={vi.fn()}
        mode="structured"
        onModeChange={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("Name")).toHaveValue("my-skill");
    expect(screen.getByLabelText("Description")).toHaveValue("my description");
    expect(screen.getByLabelText("Key for entry 1")).toHaveValue("author");
    expect(screen.getByLabelText("Value for entry 1")).toHaveValue("Jane");
    expect(screen.getByLabelText("Key for entry 2")).toHaveValue("version");
    expect(screen.getByLabelText("Value for entry 2")).toHaveValue("1.0.0");
  });

  it("calls onChangeOtherEntries when adding or removing entries", () => {
    const onChangeOtherEntries = vi.fn();
    const otherEntries: OtherFrontmatterEntry[] = [
      { id: "1", key: "author", value: "Jane" },
    ];

    render(
      <FrontmatterEditor
        knownFields={[]}
        otherEntries={otherEntries}
        onChangeOtherEntries={onChangeOtherEntries}
        rawYaml=""
        onChangeRawYaml={vi.fn()}
        mode="structured"
        onModeChange={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Add field" }));
    expect(onChangeOtherEntries).toHaveBeenCalledWith([
      { id: "1", key: "author", value: "Jane" },
      expect.objectContaining({ key: "", value: "" }),
    ]);

    fireEvent.click(screen.getByRole("button", { name: "Remove field author" }));
    expect(onChangeOtherEntries).toHaveBeenCalledWith([]);
  });

  it("switches to raw YAML mode and displays YAML text", () => {
    const onModeChange = vi.fn();
    const onChangeRawYaml = vi.fn();

    render(
      <FrontmatterEditor
        knownFields={[{ key: "name", label: "Name", value: "my-skill", onChange: vi.fn() }]}
        otherEntries={[{ id: "1", key: "author", value: "Jane" }]}
        onChangeOtherEntries={vi.fn()}
        rawYaml={"name: my-skill\nauthor: Jane\n"}
        onChangeRawYaml={onChangeRawYaml}
        mode="raw"
        onModeChange={onModeChange}
      />,
    );

    expect(screen.getByLabelText("Raw frontmatter YAML")).toHaveValue(
      "name: my-skill\nauthor: Jane\n",
    );
  });

  it("parses YAML string into known fields and other entries correctly", () => {
    const yaml = `
name: test-name
description: test-desc
customKey: customVal
author: Jane Doe
`;
    const result = parseFrontmatterFromYaml(yaml, ["name", "description"]);
    expect(result.error).toBeNull();
    expect(result.known).toEqual({
      name: "test-name",
      description: "test-desc",
    });
    expect(result.other).toEqual([
      { id: expect.any(String), key: "customKey", value: "customVal" },
      { id: expect.any(String), key: "author", value: "Jane Doe" },
    ]);
  });

  it("parses YAML multi-line list items into comma-separated known values", () => {
    const yaml = `
name: test-name
skills:
  - code-review
  - test-debugging
`;
    const result = parseFrontmatterFromYaml(yaml, ["name", "skills"]);
    expect(result.error).toBeNull();
    expect(result.known).toEqual({
      name: "test-name",
      skills: "code-review, test-debugging",
    });
  });

  it("renders custom renderInput for known field if provided", () => {
    const knownFields: KnownFieldConfig[] = [
      {
        key: "skills",
        label: "Skills",
        value: "code-review",
        onChange: vi.fn(),
        renderInput: () => <div data-testid="custom-skills-editor">Custom Skills Editor</div>,
      },
    ];

    render(
      <FrontmatterEditor
        knownFields={knownFields}
        otherEntries={[]}
        onChangeOtherEntries={vi.fn()}
        rawYaml=""
        onChangeRawYaml={vi.fn()}
        mode="structured"
        onModeChange={vi.fn()}
      />,
    );

    expect(screen.getByTestId("custom-skills-editor")).toBeInTheDocument();
  });

  it("serializes a compact nested value instead of its display summary", () => {
    const yaml = serializeFrontmatterToYaml(
      [],
      [
        {
          id: "1",
          key: "hooks",
          value: "(1 entry)",
          rawValue: { PreToolUse: [{ matcher: "Bash" }] },
        },
      ],
    );

    expect(yaml).toContain('hooks: {"PreToolUse":[{"matcher":"Bash"}]}');
    expect(yaml).not.toContain("(1 entry)");
  });

  it("edits a nested block in a textarea, so its indentation survives", () => {
    const onChangeOtherEntries = vi.fn();
    const otherEntries: OtherFrontmatterEntry[] = [
      { id: "1", key: "author", value: "Jane" },
      { id: "2", key: "metadata", value: "\n  hermes: true\n  version: \"1.0\"" },
    ];

    render(
      <FrontmatterEditor
        knownFields={[]}
        otherEntries={otherEntries}
        onChangeOtherEntries={onChangeOtherEntries}
        rawYaml=""
        onChangeRawYaml={vi.fn()}
        mode="structured"
        onModeChange={vi.fn()}
      />,
    );

    // A single-line input would strip the newlines out of a multi-line value on
    // the next controlled render, moving the data loss from the parser into here.
    const nested = screen.getByLabelText("Value for entry 2");
    expect(nested.tagName).toBe("TEXTAREA");
    expect(nested).toHaveValue("\n  hermes: true\n  version: \"1.0\"");

    expect(screen.getByLabelText("Value for entry 1").tagName).toBe("INPUT");
  });

  it("renders grouped fields under their heading in declaration order", () => {
    const knownFields: KnownFieldConfig[] = [
      { key: "name", label: "Name", group: "identity", value: "a", onChange: vi.fn() },
      { key: "model", label: "Model", group: "runtime", value: "b", onChange: vi.fn() },
      { key: "role", label: "Role", group: "identity", value: "c", onChange: vi.fn() },
      // Hidden fields stay serializable without claiming a slot in their group.
      { key: "tools", label: "Tools", group: "runtime", hidden: true, value: "d", onChange: vi.fn() },
    ];
    const fieldGroups: FrontmatterFieldGroup[] = [
      { id: "identity", title: "Identity", hint: "What it is." },
      { id: "runtime", title: "Runtime" },
      { id: "empty", title: "Nothing here" },
    ];

    const { container } = render(
      <FrontmatterEditor
        knownFields={knownFields}
        fieldGroups={fieldGroups}
        otherEntries={[]}
        onChangeOtherEntries={vi.fn()}
        rawYaml=""
        onChangeRawYaml={vi.fn()}
        mode="structured"
        onModeChange={vi.fn()}
      />,
    );

    const sections = Array.from(
      container.querySelectorAll<HTMLElement>(".frontmatter-editor__group"),
    );
    // A group nobody has a field for is a heading over nothing, so it is dropped.
    expect(sections.map((s) => s.dataset.frontmatterGroup)).toEqual(["identity", "runtime"]);
    expect(
      Array.from(sections[0].querySelectorAll(".frontmatter-editor__label")).map(
        (node) => node.textContent,
      ),
    ).toEqual(["Name", "Role"]);
    expect(sections[0].querySelector(".frontmatter-editor__group-hint")?.textContent).toBe(
      "What it is.",
    );
    expect(sections[1].querySelector(".frontmatter-editor__group-hint")).toBeNull();
    expect(screen.queryByLabelText("Tools")).not.toBeInTheDocument();
  });

  it("keeps a field whose group was never declared visible", () => {
    const knownFields: KnownFieldConfig[] = [
      { key: "name", label: "Name", group: "identity", value: "a", onChange: vi.fn() },
      { key: "orphan", label: "Orphan", group: "nope", value: "b", onChange: vi.fn() },
      { key: "plain", label: "Plain", value: "c", onChange: vi.fn() },
    ];

    render(
      <FrontmatterEditor
        knownFields={knownFields}
        fieldGroups={[{ id: "identity", title: "Identity" }]}
        otherEntries={[]}
        onChangeOtherEntries={vi.fn()}
        rawYaml=""
        onChangeRawYaml={vi.fn()}
        mode="structured"
        onModeChange={vi.fn()}
      />,
    );

    // Mistyping a group id must not silently delete the field from the editor --
    // it falls back to the ungrouped block that editors declaring no groups use.
    expect(screen.getByLabelText("Orphan")).toHaveValue("b");
    expect(screen.getByLabelText("Plain")).toHaveValue("c");
    expect(screen.getByLabelText("Name")).toHaveValue("a");
  });

  it("shows help text under a field without changing its accessible name", () => {
    const knownFields: KnownFieldConfig[] = [
      {
        key: "deny-tools",
        label: "Deny Tools",
        value: "shell",
        onChange: vi.fn(),
        helpText: "Comma-separated. Written as deny-tools.",
      },
    ];

    const { container } = render(
      <FrontmatterEditor
        knownFields={knownFields}
        otherEntries={[]}
        onChangeOtherEntries={vi.fn()}
        rawYaml=""
        onChangeRawYaml={vi.fn()}
        mode="structured"
        onModeChange={vi.fn()}
      />,
    );

    expect(container.querySelector(".frontmatter-editor__help")?.textContent).toBe(
      "Comma-separated. Written as deny-tools.",
    );
    // The hint lives inside the wrapping label, so the control has to keep naming
    // itself or the help text would be read as part of the field's name.
    expect(screen.getByLabelText("Deny Tools")).toHaveValue("shell");
  });
});
