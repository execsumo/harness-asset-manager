import { Loader2 } from "lucide-react";
import type { ReactNode } from "react";

export interface DocumentSectionProps {
  title?: string;
  /** Read-only content shown when editing is unavailable. */
  previewContent?: ReactNode;
  editFrontmatter: ReactNode;
  bodyValue: string;
  onBodyChange: (value: string) => void;
  bodyLabel?: string;
  bodyPlaceholder?: string;
  isDirty: boolean;
  isSaving: boolean;
  saveDisabled?: boolean;
  onSave: () => void | Promise<void>;
  onCancel: () => void;
  saveLabel?: string;
  cancelLabel?: string;
  unsavedLabel?: string;
  /** When false the section is read-only: preview only, no edit toggle or save bar. */
  editable?: boolean;
}

export function DocumentSection({
  title = "Document",
  previewContent,
  editFrontmatter,
  bodyValue,
  onBodyChange,
  bodyLabel = "Body",
  bodyPlaceholder = "Markdown body...",
  isDirty,
  isSaving,
  saveDisabled = false,
  onSave,
  onCancel,
  saveLabel = "Save",
  cancelLabel = "Cancel",
  unsavedLabel = "Unsaved changes",
  editable = true,
}: DocumentSectionProps) {
  return (
    <section className="document-section" aria-label={title}>
      <div className="document-section__header">
        <h3 className="document-section__title">{title}</h3>

      </div>

      {!editable ? (
        <div className="document-section__preview">
          <div className="document-section__surface skill-detail__document-surface">
            {previewContent}
          </div>
        </div>
      ) : (
        <div className="document-section__edit">
          {editFrontmatter}

          <div className="document-section__body-editor">
            <span className="document-section__body-label">{bodyLabel}</span>
            <textarea
              className="document-section__body-textarea ui-scrollbar"
              value={bodyValue}
              onChange={(e) => onBodyChange(e.target.value)}
              placeholder={bodyPlaceholder}
              disabled={isSaving}
              aria-label={bodyLabel}
              spellCheck={false}
            />
          </div>

          {isDirty ? (
            <div className="document-section__action-bar">
              <span className="document-section__dirty-indicator">
                <span className="document-section__dirty-dot" aria-hidden="true" />
                {unsavedLabel}
              </span>
              <div className="document-section__action-buttons">
                <button
                  type="button"
                  className="action-pill action-pill--md"
                  onClick={onCancel}
                  disabled={isSaving}
                >
                  {cancelLabel}
                </button>
                <button
                  type="button"
                  className="action-pill action-pill--md action-pill--accent"
                  onClick={() => void onSave()}
                  disabled={isSaving || saveDisabled}
                >
                  {isSaving ? (
                    <Loader2 size={12} className="animate-spin" aria-hidden="true" />
                  ) : null}
                  {saveLabel}
                </button>
              </div>
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}
