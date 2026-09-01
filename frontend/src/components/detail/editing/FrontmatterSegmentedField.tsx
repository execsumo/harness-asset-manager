export interface FrontmatterSegmentedFieldProps {
  /** Names the group for assistive tech, and the vocabulary in the invalid-value hint. */
  label: string;
  value: string;
  options: readonly string[];
  onChange: (value: string) => void;
  disabled?: boolean;
  /** The segment that clears the key. */
  clearLabel?: string;
}

/**
 * A two-or-three-way toggle for a structured frontmatter field with a fixed vocabulary.
 *
 * The extra "unset" segment is what keeps the toggle honest about the file: a key that
 * is simply absent is a third state, and a plain on/off switch would have to invent a
 * value for it and write that value on the next save.
 */
export function FrontmatterSegmentedField({
  label,
  value,
  options,
  onChange,
  disabled,
  clearLabel = "Unset",
}: FrontmatterSegmentedFieldProps) {
  // An agent authored elsewhere can carry a value the contract does not allow. Offering
  // it as its own segment keeps a save from silently rewriting it, and shows the user
  // exactly what the API will reject.
  const isKnown = (candidate: string) => options.includes(candidate);
  const segments = value && !isKnown(value) ? [...options, value] : options;

  return (
    <div className="frontmatter-toggle" role="group" aria-label={label}>
      <button
        type="button"
        className="frontmatter-toggle__btn"
        data-active={value === ""}
        onClick={() => onChange("")}
        disabled={disabled}
      >
        {clearLabel}
      </button>
      {segments.map((option) => (
        <button
          key={option}
          type="button"
          className="frontmatter-toggle__btn"
          data-active={value === option}
          data-invalid={isKnown(option) ? undefined : true}
          title={isKnown(option) ? undefined : `${option} — not a valid ${label.toLowerCase()}`}
          onClick={() => onChange(option)}
          disabled={disabled}
        >
          {option}
        </button>
      ))}
    </div>
  );
}
