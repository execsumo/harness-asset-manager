import { Plus, Trash2 } from "lucide-react";
import type { ReactNode } from "react";

export interface KnownFieldConfig {
  key: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  placeholder?: string;
  helpText?: string;
  serialize?: (value: string) => string | null;
  renderInput?: (props: { disabled?: boolean }) => ReactNode;
  /**
   * Set false when `renderInput` renders a group rather than one labelable control.
   * A `<label>` wrapping several buttons hands every one of them the label's text as
   * its accessible name, so the group must name itself instead.
   */
  wrapInLabel?: boolean;
}

export interface OtherFrontmatterEntry {
  id: string;
  key: string;
  value: string;
}

export interface FrontmatterEditorProps {
  knownFields: KnownFieldConfig[];
  otherEntries: OtherFrontmatterEntry[];
  onChangeOtherEntries: (entries: OtherFrontmatterEntry[]) => void;
  rawYaml: string;
  onChangeRawYaml: (yaml: string) => void;
  mode: "structured" | "raw";
  onModeChange: (mode: "structured" | "raw") => void;
  note?: ReactNode;
  validationError?: string | null;
  disabled?: boolean;
}

export function serializeFrontmatterToYaml(
  known: KnownFieldConfig[],
  other: OtherFrontmatterEntry[],
): string {
  const lines: string[] = [];
  for (const field of known) {
    if (field.serialize) {
      const custom = field.serialize(field.value);
      if (custom !== null && custom !== undefined && custom !== "") {
        lines.push(custom);
      }
    } else if (field.value !== undefined && field.value !== "") {
      lines.push(`${field.key}: ${field.value}`);
    }
  }
  for (const entry of other) {
    if (entry.key.trim()) {
      if (entry.value === "") {
        lines.push(`${entry.key.trim()}: ""`);
      } else {
        lines.push(`${entry.key.trim()}: ${entry.value}`);
      }
    }
  }
  return lines.join("\n");
}

export function parseFrontmatterFromYaml(
  yamlText: string,
  knownKeys: string[],
): {
  known: Record<string, string>;
  other: OtherFrontmatterEntry[];
  error: string | null;
} {
  const lines = yamlText.split("\n");
  const known: Record<string, string> = {};
  const other: OtherFrontmatterEntry[] = [];
  let currentKey: string | null = null;
  let isCurrentKnown = false;

  for (let i = 0; i < lines.length; i++) {
    const rawLine = lines[i];
    const trimmed = rawLine.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }
    if (trimmed === "---") {
      continue;
    }

    if (trimmed.startsWith("- ") || trimmed === "-") {
      const itemVal = trimmed.replace(/^-\s*/, "").trim().replace(/^['"]|['"]$/g, "");
      if (currentKey) {
        if (isCurrentKnown) {
          const prev = known[currentKey] || "";
          known[currentKey] = prev ? `${prev}, ${itemVal}` : itemVal;
        } else {
          const lastOther = other[other.length - 1];
          if (lastOther) {
            lastOther.value = lastOther.value ? `${lastOther.value}, ${itemVal}` : itemVal;
          }
        }
      }
      continue;
    }

    if (!rawLine.includes(":")) {
      return {
        known: {},
        other: [],
        error: `Invalid YAML line at line ${i + 1}: "${rawLine}" (missing ':')`,
      };
    }
    const colonIdx = rawLine.indexOf(":");
    const key = rawLine.slice(0, colonIdx).trim();
    let value = rawLine.slice(colonIdx + 1).trim();

    if (
      (value.startsWith('"') && value.endsWith('"') && value.length >= 2) ||
      (value.startsWith("'") && value.endsWith("'") && value.length >= 2)
    ) {
      value = value.slice(1, -1);
    }

    currentKey = key;
    isCurrentKnown = knownKeys.includes(key);

    if (isCurrentKnown) {
      known[key] = value;
    } else {
      other.push({
        id: `entry-${i}-${key}-${Math.random().toString(36).slice(2, 7)}`,
        key,
        value,
      });
    }
  }

  return { known, other, error: null };
}

export function FrontmatterEditor({
  knownFields,
  otherEntries,
  onChangeOtherEntries,
  rawYaml,
  onChangeRawYaml,
  mode,
  onModeChange,
  note,
  validationError,
  disabled,
}: FrontmatterEditorProps) {
  const handleToggleMode = (nextMode: "structured" | "raw") => {
    if (nextMode === mode) return;

    if (nextMode === "raw") {
      const serialized = serializeFrontmatterToYaml(knownFields, otherEntries);
      onChangeRawYaml(serialized);
      onModeChange("raw");
    } else {
      const knownKeys = knownFields.map((f) => f.key);
      const parsed = parseFrontmatterFromYaml(rawYaml, knownKeys);
      if (parsed.error) {
        return;
      }
      for (const field of knownFields) {
        field.onChange(parsed.known[field.key] ?? "");
      }
      onChangeOtherEntries(parsed.other);
      onModeChange("structured");
    }
  };

  const handleAddOtherEntry = () => {
    const newEntry: OtherFrontmatterEntry = {
      id: `custom-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      key: "",
      value: "",
    };
    onChangeOtherEntries([...otherEntries, newEntry]);
  };

  const handleUpdateOtherEntry = (
    index: number,
    field: "key" | "value",
    val: string,
  ) => {
    const updated = otherEntries.map((item, idx) =>
      idx === index ? { ...item, [field]: val } : item,
    );
    onChangeOtherEntries(updated);
  };

  const handleRemoveOtherEntry = (index: number) => {
    onChangeOtherEntries(otherEntries.filter((_, idx) => idx !== index));
  };

  return (
    <div className="frontmatter-editor">
      <div className="frontmatter-editor__header">
        <span className="frontmatter-editor__title">Frontmatter</span>
        <div className="view-mode-toggle" role="group" aria-label="Frontmatter view mode">
          <button
            type="button"
            className="view-mode-toggle__btn"
            data-active={mode === "structured"}
            onClick={() => handleToggleMode("structured")}
            disabled={disabled}
          >
            Structured
          </button>
          <button
            type="button"
            className="view-mode-toggle__btn"
            data-active={mode === "raw"}
            onClick={() => handleToggleMode("raw")}
            disabled={disabled}
          >
            Raw YAML
          </button>
        </div>
      </div>

      {validationError ? (
        <div className="frontmatter-editor__error" role="alert">
          {validationError}
        </div>
      ) : null}

      {mode === "raw" ? (
        <textarea
          className="frontmatter-editor__raw-yaml ui-scrollbar"
          value={rawYaml}
          onChange={(e) => onChangeRawYaml(e.target.value)}
          placeholder="key: value"
          disabled={disabled}
          aria-label="Raw frontmatter YAML"
          spellCheck={false}
        />
      ) : (
        <>
          <div className="frontmatter-editor__known-fields">
            {knownFields.map((field) => {
              const Field = field.wrapInLabel === false ? "div" : "label";
              return (
                <Field key={field.key} className="frontmatter-editor__field">
                  <span className="frontmatter-editor__label">{field.label}</span>
                  {field.renderInput ? (
                    field.renderInput({ disabled: disabled || field.disabled })
                  ) : (
                    <input
                      type="text"
                      className="frontmatter-editor__input"
                      value={field.value}
                      onChange={(e) => field.onChange(e.target.value)}
                      disabled={disabled || field.disabled}
                      placeholder={field.placeholder}
                      aria-label={field.label}
                    />
                  )}
                </Field>
              );
            })}
          </div>

          <div className="frontmatter-editor__other-section">
            <span className="frontmatter-editor__other-title">Other frontmatter</span>
            {otherEntries.length > 0 ? (
              <div className="frontmatter-editor__rows">
                {otherEntries.map((entry, index) => (
                  <div key={entry.id} className="frontmatter-editor__row">
                    <input
                      type="text"
                      className="frontmatter-editor__row-key"
                      placeholder="key"
                      value={entry.key}
                      onChange={(e) =>
                        handleUpdateOtherEntry(index, "key", e.target.value)
                      }
                      disabled={disabled}
                      aria-label={`Key for entry ${index + 1}`}
                    />
                    {entry.value.includes("\n") ? (
                      // A nested map, list, or literal block. Its indentation is
                      // the structure, and a single-line input would strip the
                      // newlines back out on the next controlled render.
                      <textarea
                        className="frontmatter-editor__row-value frontmatter-editor__row-value--block ui-scrollbar"
                        placeholder="value"
                        value={entry.value}
                        onChange={(e) =>
                          handleUpdateOtherEntry(index, "value", e.target.value)
                        }
                        disabled={disabled}
                        aria-label={`Value for entry ${index + 1}`}
                        spellCheck={false}
                        rows={Math.min(entry.value.split("\n").length, 8)}
                      />
                    ) : (
                      <input
                        type="text"
                        className="frontmatter-editor__row-value"
                        placeholder="value"
                        value={entry.value}
                        onChange={(e) =>
                          handleUpdateOtherEntry(index, "value", e.target.value)
                        }
                        disabled={disabled}
                        aria-label={`Value for entry ${index + 1}`}
                      />
                    )}
                    <button
                      type="button"
                      className="frontmatter-editor__remove-btn"
                      onClick={() => handleRemoveOtherEntry(index)}
                      disabled={disabled}
                      aria-label={`Remove field ${entry.key || index + 1}`}
                      title="Remove field"
                    >
                      <Trash2 size={14} aria-hidden="true" />
                    </button>
                  </div>
                ))}
              </div>
            ) : null}

            <button
              type="button"
              className="action-pill action-pill--sm frontmatter-editor__add-btn"
              onClick={handleAddOtherEntry}
              disabled={disabled}
            >
              <Plus size={12} aria-hidden="true" />
              Add field
            </button>
          </div>
        </>
      )}

      {note ? <p className="frontmatter-editor__note">{note}</p> : null}
    </div>
  );
}
