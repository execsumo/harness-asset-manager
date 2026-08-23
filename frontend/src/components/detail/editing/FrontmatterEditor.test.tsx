import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  FrontmatterEditor,
  parseFrontmatterFromYaml,
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
});
