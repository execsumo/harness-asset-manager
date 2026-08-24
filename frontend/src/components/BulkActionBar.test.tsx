import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { BulkActionBar } from "./BulkActionBar";

describe("BulkActionBar", () => {
  const defaultDestructive = {
    actionLabel: "Delete",
    confirmTitle: "Delete selected?",
    confirmDescription: "This action cannot be undone.",
  };

  it("renders bulk action bar with selected count and standard actions", () => {
    const onClear = vi.fn();
    const onEnableAll = vi.fn().mockResolvedValue(undefined);
    const onDisableAll = vi.fn().mockResolvedValue(undefined);
    const onDelete = vi.fn().mockResolvedValue(undefined);

    render(
      <BulkActionBar
        selectedCount={3}
        pending={null}
        onClear={onClear}
        onEnableAll={onEnableAll}
        onDisableAll={onDisableAll}
        onDelete={onDelete}
        destructive={defaultDestructive}
      />,
    );

    expect(screen.getByText("3 selected")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enable all" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Disable all" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Tag selected/i })).not.toBeInTheDocument();
  });

  it("renders Star button when onStarSelected is provided", () => {
    const onStarSelected = vi.fn().mockResolvedValue(undefined);

    render(
      <BulkActionBar
        selectedCount={2}
        pending={null}
        onClear={vi.fn()}
        onEnableAll={vi.fn().mockResolvedValue(undefined)}
        onDisableAll={vi.fn().mockResolvedValue(undefined)}
        onDelete={vi.fn().mockResolvedValue(undefined)}
        onStarSelected={onStarSelected}
        starLabel="Star selected"
        destructive={defaultDestructive}
      />,
    );

    const starBtn = screen.getByRole("button", { name: "Star selected" });
    expect(starBtn).toBeInTheDocument();
    fireEvent.click(starBtn);
    expect(onStarSelected).toHaveBeenCalled();
  });

  it("opens Tag popover, stages tags via Enter/comma/suggestions, and applies merged tags", async () => {
    const onTagSelected = vi.fn().mockResolvedValue(undefined);

    render(
      <BulkActionBar
        selectedCount={2}
        pending={null}
        onClear={vi.fn()}
        onEnableAll={vi.fn().mockResolvedValue(undefined)}
        onDisableAll={vi.fn().mockResolvedValue(undefined)}
        onDelete={vi.fn().mockResolvedValue(undefined)}
        onTagSelected={onTagSelected}
        knownTags={["production", "backend", "analytics", "starred"]}
        destructive={defaultDestructive}
      />,
    );

    const tagBtn = screen.getByRole("button", { name: "Tag selected" });
    expect(tagBtn).toBeInTheDocument();

    // Open popover
    fireEvent.click(tagBtn);

    expect(screen.getByText("Add tags to selected")).toBeInTheDocument();

    const input = screen.getByPlaceholderText("Type tag name...");

    // Stage first tag via Enter
    fireEvent.change(input, { target: { value: "frontend" } });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });

    expect(screen.getByText("frontend")).toBeInTheDocument();

    // Stage second tag via Comma
    fireEvent.change(input, { target: { value: "v2" } });
    fireEvent.keyDown(input, { key: ",", code: "Comma" });

    expect(screen.getByText("v2")).toBeInTheDocument();

    // Stage third tag via suggestion click
    fireEvent.change(input, { target: { value: "prod" } });
    const suggestion = screen.getByRole("option", { name: "production" });
    expect(suggestion).toBeInTheDocument();
    fireEvent.mouseDown(suggestion);

    expect(screen.getByText("production")).toBeInTheDocument();

    // Click Apply
    const applyBtn = screen.getByRole("button", { name: "Apply" });
    fireEvent.click(applyBtn);

    await waitFor(() => {
      expect(onTagSelected).toHaveBeenCalledWith(["frontend", "v2", "production"]);
    });
  });

  it("supports committing pending uncommitted input text on Apply click", async () => {
    const onTagSelected = vi.fn().mockResolvedValue(undefined);

    render(
      <BulkActionBar
        selectedCount={1}
        pending={null}
        onClear={vi.fn()}
        onEnableAll={vi.fn().mockResolvedValue(undefined)}
        onDisableAll={vi.fn().mockResolvedValue(undefined)}
        onDelete={vi.fn().mockResolvedValue(undefined)}
        onTagSelected={onTagSelected}
        knownTags={["core"]}
        destructive={defaultDestructive}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Tag selected" }));

    const input = screen.getByPlaceholderText("Type tag name...");
    fireEvent.change(input, { target: { value: "quick-tag" } });

    // Click Apply directly without pressing Enter
    const applyBtn = screen.getByRole("button", { name: "Apply" });
    fireEvent.click(applyBtn);

    await waitFor(() => {
      expect(onTagSelected).toHaveBeenCalledWith(["quick-tag"]);
    });
  });

  it("removes staged tags via chip remove button and backspace", () => {
    render(
      <BulkActionBar
        selectedCount={2}
        pending={null}
        onClear={vi.fn()}
        onEnableAll={vi.fn().mockResolvedValue(undefined)}
        onDisableAll={vi.fn().mockResolvedValue(undefined)}
        onDelete={vi.fn().mockResolvedValue(undefined)}
        onTagSelected={vi.fn().mockResolvedValue(undefined)}
        destructive={defaultDestructive}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Tag selected" }));
    const input = screen.getByPlaceholderText("Type tag name...");

    fireEvent.change(input, { target: { value: "tag1" } });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });

    fireEvent.change(input, { target: { value: "tag2" } });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });

    expect(screen.getByText("tag1")).toBeInTheDocument();
    expect(screen.getByText("tag2")).toBeInTheDocument();

    // Remove tag2 via backspace when input is empty
    fireEvent.keyDown(input, { key: "Backspace", code: "Backspace" });
    expect(screen.queryByText("tag2")).not.toBeInTheDocument();
    expect(screen.getByText("tag1")).toBeInTheDocument();

    // Remove tag1 via remove button
    const removeBtn = screen.getByRole("button", { name: "Remove tag tag1" });
    fireEvent.click(removeBtn);
    expect(screen.queryByText("tag1")).not.toBeInTheDocument();
  });

  it("validates tag length and duplicates in bulk tag popover", () => {
    render(
      <BulkActionBar
        selectedCount={2}
        pending={null}
        onClear={vi.fn()}
        onEnableAll={vi.fn().mockResolvedValue(undefined)}
        onDisableAll={vi.fn().mockResolvedValue(undefined)}
        onDelete={vi.fn().mockResolvedValue(undefined)}
        onTagSelected={vi.fn().mockResolvedValue(undefined)}
        destructive={defaultDestructive}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Tag selected" }));
    const input = screen.getByPlaceholderText("Type tag name...");

    // Duplicate test
    fireEvent.change(input, { target: { value: "alpha" } });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });
    expect(screen.getByText("alpha")).toBeInTheDocument();

    fireEvent.change(input, { target: { value: "ALPHA" } });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });
    expect(screen.getByText("Tag already added")).toBeInTheDocument();

    // Length test
    fireEvent.change(input, { target: { value: "a".repeat(65) } });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });
    expect(screen.getByText("Tag must be 64 characters or fewer")).toBeInTheDocument();
  });
});
