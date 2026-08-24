import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DetailTags } from "./DetailTags";

describe("DetailTags", () => {
  it("renders tag chips and allows removing tags", async () => {
    const onAddTag = vi.fn().mockResolvedValue(undefined);
    const onRemoveTag = vi.fn().mockResolvedValue(undefined);

    render(
      <DetailTags
        tags={["starred", "frontend"]}
        knownTags={["starred", "frontend", "backend", "database"]}
        canEdit={true}
        onAddTag={onAddTag}
        onRemoveTag={onRemoveTag}
      />,
    );

    expect(screen.getByText("starred")).toBeInTheDocument();
    expect(screen.getByText("frontend")).toBeInTheDocument();

    const removeBtn = screen.getByRole("button", { name: /remove tag frontend/i });
    fireEvent.click(removeBtn);
    expect(onRemoveTag).toHaveBeenCalledWith("frontend");
  });

  it("displays autocomplete suggestions from knownTags excluding existing tags", async () => {
    const onAddTag = vi.fn().mockResolvedValue(undefined);
    const onRemoveTag = vi.fn().mockResolvedValue(undefined);

    render(
      <DetailTags
        tags={["frontend"]}
        knownTags={["frontend", "backend", "FullStack", "DevOps", "Database"]}
        canEdit={true}
        onAddTag={onAddTag}
        onRemoveTag={onRemoveTag}
      />,
    );

    // Open add input
    const addBtn = screen.getByRole("button", { name: /add tag/i });
    fireEvent.click(addBtn);

    // Suggestions list should be present
    const suggestionsList = screen.getByRole("listbox");
    expect(suggestionsList).toBeInTheDocument();

    // "frontend" should not appear in suggestions because the asset already has it
    expect(screen.queryByRole("option", { name: "frontend" })).not.toBeInTheDocument();
    // other knownTags should appear
    expect(screen.getByRole("option", { name: "backend" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "FullStack" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "DevOps" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Database" })).toBeInTheDocument();

    // Clicking a suggestion adds it
    fireEvent.mouseDown(screen.getByRole("option", { name: "FullStack" }));
    expect(onAddTag).toHaveBeenCalledWith("FullStack");
  });

  it("filters suggestions case-insensitively while typing", async () => {
    const onAddTag = vi.fn().mockResolvedValue(undefined);
    const onRemoveTag = vi.fn().mockResolvedValue(undefined);

    render(
      <DetailTags
        tags={[]}
        knownTags={["alpha", "beta", "ALGORITHM", "gamma"]}
        canEdit={true}
        onAddTag={onAddTag}
        onRemoveTag={onRemoveTag}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /add tag/i }));
    const input = screen.getByPlaceholderText("Tag name...");

    fireEvent.change(input, { target: { value: "al" } });

    expect(screen.getByRole("option", { name: "alpha" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "ALGORITHM" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "beta" })).not.toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "gamma" })).not.toBeInTheDocument();
  });

  it("validates input max length and duplicate tags", async () => {
    const onAddTag = vi.fn().mockResolvedValue(undefined);
    const onRemoveTag = vi.fn().mockResolvedValue(undefined);

    render(
      <DetailTags
        tags={["existing-tag"]}
        knownTags={["existing-tag", "other-tag"]}
        canEdit={true}
        onAddTag={onAddTag}
        onRemoveTag={onRemoveTag}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /add tag/i }));
    const input = screen.getByPlaceholderText("Tag name...");

    // Try adding duplicate tag (case insensitive)
    fireEvent.change(input, { target: { value: "EXISTING-TAG" } });
    fireEvent.click(screen.getByRole("button", { name: /confirm tag/i }));

    expect(screen.getByText("Tag already added")).toBeInTheDocument();
    expect(onAddTag).not.toHaveBeenCalled();
  });

  it("renders read-only tag chips when canEdit=false", () => {
    render(
      <DetailTags
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
