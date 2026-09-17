import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DocumentSection } from "./DocumentSection";

describe("DocumentSection", () => {
  it("renders preview content when editing is unavailable", () => {
    render(
      <DocumentSection
        title="Document"
        editable={false}
        previewContent={<p>Preview markdown</p>}
        editFrontmatter={<div>Frontmatter inputs</div>}
        bodyValue="# Header"
        onBodyChange={vi.fn()}
        isDirty={false}
        isSaving={false}
        onSave={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    expect(screen.getByText("Document")).toBeInTheDocument();
    expect(screen.getByText("Preview markdown")).toBeInTheDocument();
    expect(screen.queryByText("Frontmatter inputs")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Document body")).not.toBeInTheDocument();
  });

  it("renders the editor by default without a mode toggle", () => {
    const onBodyChange = vi.fn();

    render(
      <DocumentSection
        title="Document"
        editFrontmatter={<div>Frontmatter inputs</div>}
        bodyValue="# Header"
        onBodyChange={onBodyChange}
        bodyLabel="Body (SKILL.md)"
        isDirty={false}
        isSaving={false}
        onSave={vi.fn()}
        onCancel={vi.fn()}
      />,
    );

    expect(screen.getByText("Frontmatter inputs")).toBeInTheDocument();
    const textarea = screen.getByLabelText("Body (SKILL.md)");
    expect(textarea).toHaveValue("# Header");

    fireEvent.change(textarea, { target: { value: "# Header updated" } });
    expect(onBodyChange).toHaveBeenCalledWith("# Header updated");

    expect(screen.queryByRole("button", { name: "Preview" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
  });

  it("renders dirty action bar with Save and Cancel buttons when dirty", () => {
    const onSave = vi.fn();
    const onCancel = vi.fn();

    render(
      <DocumentSection
        title="Document"
        editFrontmatter={<div>Frontmatter</div>}
        bodyValue="# Header"
        onBodyChange={vi.fn()}
        isDirty={true}
        isSaving={false}
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
