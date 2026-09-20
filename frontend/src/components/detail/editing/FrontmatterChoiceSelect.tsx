export interface FrontmatterChoiceOption {
  value: string;
  /** Shown to the user; falls back to `value` when the two are the same. */
  label?: string;
  /** Appended after an em dash to explain why the option is unusual. */
  note?: string;
}

export interface FrontmatterChoiceSelectProps {
  /** Names the control for assistive tech, and the vocabulary in the invalid-value hint. */
  label: string;
  value: string;
  options: readonly (string | FrontmatterChoiceOption)[];
  onChange: (value: string) => void;
  disabled?: boolean;
  /** The option that clears the key. */
  clearLabel?: string;
  /** Detail sheets and the create dialog style their inputs differently. */
  className?: string;
}

function normalize(option: string | FrontmatterChoiceOption): FrontmatterChoiceOption {
  return typeof option === "string" ? { value: option } : option;
}

/**
 * A dropdown for a structured frontmatter field with a fixed vocabulary.
 *
 * The extra "unset" option is what keeps the control honest about the file: a key
 * that is simply absent is a third state, and a plain on/off control would have to
 * invent a value for it and write that value on the next save.
 *
 * Every fixed-vocabulary frontmatter field renders through here so the same key
 * looks the same wherever it is edited -- the detail sheet and the create dialog
 * used to disagree about which fields were dropdowns and which were toggles.
 */
export function FrontmatterChoiceSelect({
  label,
  value,
  options,
  onChange,
  disabled,
  clearLabel = "(none)",
  className = "frontmatter-editor__input",
}: FrontmatterChoiceSelectProps) {
  const normalized = options.map(normalize);
  // An agent authored elsewhere can carry a value the contract does not allow.
  // Offering it as its own option keeps a save from silently rewriting it, and
  // shows the user exactly what the API will reject.
  const isKnown = normalized.some((option) => option.value === value);

  return (
    <select
      className={className}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      disabled={disabled}
      aria-label={label}
    >
      <option value="">{clearLabel}</option>
      {normalized.map((option) => (
        <option key={option.value} value={option.value}>
          {option.note
            ? `${option.label ?? option.value} — ${option.note}`
            : (option.label ?? option.value)}
        </option>
      ))}
      {value && !isKnown ? (
        <option value={value}>
          {value} — not a valid {label.toLowerCase()}
        </option>
      ) : null}
    </select>
  );
}
