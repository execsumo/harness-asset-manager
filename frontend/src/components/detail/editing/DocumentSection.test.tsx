import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DocumentSection } from "./DocumentSection";

describe("DocumentSection", () => {
  it("renders preview content in preview mode", () => {
    render(
      <DocumentSection
        title="Document"
        mode="preview"
        onModeChange={vi.fn()}
        previewContent={<p>Preview markdown</p>}
        editFrontmatter={<div>Frontmatter inputs</div>}
        bodyValue="# Header"
        onBodyChange={vi.fn()}
      />,
    );

    expect(screen.getByText("Document")).toBeInTheDocument();
    expect(screen.getByText("Preview markdown")).toBeInTheDocument();
    expect(screen.queryByText("Frontmatter inputs")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Document body")).not.toBeInTheDocument();
  });

  it("renders editor controls and handles mode switching", () => {
    const onModeChange = vi.fn();
    const onBodyChange = vi.fn();

    render(
      <DocumentSection
        title="Document"
        mode="edit"
        onModeChange={onModeChange}
        previewContent={<p>Preview markdown</p>}
        editFrontmatter={<div>Frontmatter inputs</div>}
        bodyValue="# Header"
        onBodyChange={onBodyChange}
        bodyLabel="Body (SKILL.md)"
      />,
    );

    expect(screen.getByText("Frontmatter inputs")).toBeInTheDocument();
    const textarea = screen.getByLabelText("Body (SKILL.md)");
    expect(textarea).toHaveValue("# Header");

    fireEvent.change(textarea, { target: { value: "# Header updated" } });
    expect(onBodyChange).toHaveBeenCalledWith("# Header updated");

    fireEvent.click(screen.getByRole("button", { name: "Preview" }));
    expect(onModeChange).toHaveBeenCalledWith("preview");
  });

  it("renders dirty action bar with Save and Cancel buttons when dirty", () => {
    const onSave = vi.fn();
    const onCancel = vi.fn();

    render(
      <DocumentSection
        title="Document"
        mode="edit"
        onModeChange={vi.fn()}
        previewContent={<p>Preview</p>}
        editFrontmatter={<div>Frontmatter</div>}
        bodyValue="# Header"
        onBodyChange={vi.fn()}
        isDirty={true}
        onSave={onSave}
        onCancel={onCancel}
        saveLabel="Save"
        cancelLabel="Cancel"
        unsavedLabel="Unsaved changes"
      />,
    );

    expect(screen.getByText("Unsaved changes")).toBeInTheDocument();
    const saveBtn = screen.getByRole("button", { name: "Save" });
    const cancelBtn = screen.getByRole("button", { name: "Cancel" });

    fireEvent.click(saveBtn);
    expect(onSave).toHaveBeenCalled();

    fireEvent.click(cancelBtn);
    expect(onCancel).toHaveBeenCalled();
  });
});
