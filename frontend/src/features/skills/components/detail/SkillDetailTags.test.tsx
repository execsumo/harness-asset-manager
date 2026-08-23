import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SkillDetailTags } from "./SkillDetailTags";

describe("SkillDetailTags", () => {
  it("renders tag chips and allows adding a new tag when canEdit=true", async () => {
    const onAddTag = vi.fn().mockResolvedValue(undefined);
    const onRemoveTag = vi.fn().mockResolvedValue(undefined);

    render(
      <SkillDetailTags
        tags={["starred", "devops"]}
        knownTags={["starred", "devops", "core", "security"]}
        canEdit={true}
        onAddTag={onAddTag}
        onRemoveTag={onRemoveTag}
      />,
    );

    expect(screen.getByText("starred")).toBeInTheDocument();
    expect(screen.getByText("devops")).toBeInTheDocument();

    // Click remove on 'devops'
    const removeBtn = screen.getByRole("button", { name: /remove tag devops/i });
    fireEvent.click(removeBtn);
    expect(onRemoveTag).toHaveBeenCalledWith("devops");

    // Click 'Add tag'
    const addBtn = screen.getByRole("button", { name: /add tag/i });
    fireEvent.click(addBtn);

    const input = screen.getByPlaceholderText("Tag name...");
    fireEvent.change(input, { target: { value: "productivity" } });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });

    expect(onAddTag).toHaveBeenCalledWith("productivity");
  });

  it("renders read-only tag chips when canEdit=false", () => {
    render(
      <SkillDetailTags
        tags={["starred", "devops"]}
        canEdit={false}
        onAddTag={vi.fn()}
        onRemoveTag={vi.fn()}
      />,
    );

    expect(screen.getByText("starred")).toBeInTheDocument();
    expect(screen.getByText("devops")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /remove tag/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /add tag/i })).not.toBeInTheDocument();
  });
});
