import { useEffect, useRef, useState } from "react";
import { X } from "lucide-react";

export interface AdoptedSkillOption {
  slug: string;
  name: string;
  tags?: string[];
}

export interface SkillTagOption {
  tag: string;
  skills: string[];
}

export interface SkillTagSourceItem {
  skillRef?: string;
  slug?: string;
  displayStatus?: string;
  tags?: string[];
}

export function deriveSkillTagOptions(items?: SkillTagSourceItem[] | null): SkillTagOption[] {
  if (!items || items.length === 0) return [];
  const tagMap = new Map<string, { tag: string; skills: string[] }>();

  for (const item of items) {
    let slug = "";
    if (item.skillRef) {
      if (!item.skillRef.startsWith("shared:") && item.displayStatus !== "Managed") {
        continue;
      }
      slug = item.skillRef.replace(/^shared:/, "");
    } else if (item.slug) {
      slug = item.slug;
    }

    if (!slug) continue;
    const tags = item.tags || [];
    for (const rawTag of tags) {
      const tag = typeof rawTag === "string" ? rawTag.trim() : "";
      if (!tag) continue;
      const key = tag.toLowerCase();
      let entry = tagMap.get(key);
      if (!entry) {
        entry = { tag, skills: [] };
        tagMap.set(key, entry);
      }
      if (!entry.skills.includes(slug)) {
        entry.skills.push(slug);
      }
    }
  }

  return Array.from(tagMap.values()).sort((a, b) =>
    a.tag.localeCompare(b.tag, undefined, { sensitivity: "base" })
  );
}

export interface AgentSkillsFieldEditorProps {
  skills: string[];
  knownSkills?: AdoptedSkillOption[];
  tagOptions?: SkillTagOption[];
  onChange: (skills: string[]) => void;
  disabled?: boolean;
  placeholder?: string;
}

export function AgentSkillsFieldEditor({
  skills,
  knownSkills = [],
  tagOptions,
  onChange,
  disabled = false,
  placeholder = "Add skill...",
}: AgentSkillsFieldEditorProps) {
  const [inputVal, setInputVal] = useState("");
  const [suggestOpen, setSuggestOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const activeOptionRef = useRef<HTMLLIElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setSuggestOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // The list scrolls rather than truncating, so arrowing down can walk the active
  // option below the fold unless we follow it.
  useEffect(() => {
    activeOptionRef.current?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, suggestOpen]);

  const normalizedExisting = new Set(skills.map((s) => s.toLowerCase()));
  const trimmed = inputVal.trim().toLowerCase();

  const effectiveTagOptions = tagOptions !== undefined
    ? tagOptions
    : deriveSkillTagOptions(knownSkills);

  const visibleTagOptions = effectiveTagOptions.filter((opt) => {
    if (!opt.skills || opt.skills.length === 0) return false;
    const allAttached = opt.skills.every((slug) =>
      normalizedExisting.has(slug.toLowerCase())
    );
    return !allAttached;
  });

  const handlePickTag = (opt: SkillTagOption) => {
    if (disabled) return;
    const existing = new Set(skills.map((s) => s.toLowerCase()));
    const missingSlugs: string[] = [];

    for (const slug of opt.skills) {
      const lower = slug.toLowerCase();
      if (!existing.has(lower)) {
        missingSlugs.push(slug);
        existing.add(lower);
      }
    }

    if (missingSlugs.length === 0) return;

    setError(null);
    onChange([...skills, ...missingSlugs]);
  };

  // Every match, never a first page: a capped list looks complete and is not, and
  // any cap tells the same lie further down. The dropdown scrolls instead.
  const suggestions = knownSkills
    .filter((s) => !normalizedExisting.has(s.slug.toLowerCase()))
    .filter((s) =>
      trimmed ? s.slug.toLowerCase().includes(trimmed) || s.name.toLowerCase().includes(trimmed) : true,
    );

  const handleAdd = (slugOrName: string) => {
    const raw = slugOrName.trim();
    if (!raw) return;

    // Resolve against adopted skills (matching slug or display name)
    const matched = knownSkills.find(
      (s) => s.slug.toLowerCase() === raw.toLowerCase() || s.name.toLowerCase() === raw.toLowerCase(),
    );
    const slugToAdd = matched ? matched.slug : raw;

    if (normalizedExisting.has(slugToAdd.toLowerCase())) {
      setError("Skill already attached");
      return;
    }

    setError(null);
    onChange([...skills, slugToAdd]);
    setInputVal("");
    setSuggestOpen(false);
    setActiveIndex(0);
  };

  const handleRemove = (slugToRemove: string) => {
    setError(null);
    onChange(skills.filter((s) => s.toLowerCase() !== slugToRemove.toLowerCase()));
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      if (suggestions.length > 0 && activeIndex >= 0 && activeIndex < suggestions.length) {
        handleAdd(suggestions[activeIndex].slug);
      } else if (suggestions.length > 0 && trimmed) {
        handleAdd(suggestions[0].slug);
      } else if (inputVal.trim()) {
        handleAdd(inputVal.trim());
      }
    } else if (e.key === "Backspace" && inputVal === "" && skills.length > 0) {
      handleRemove(skills[skills.length - 1]);
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (suggestions.length > 0) {
        setActiveIndex((prev) => (prev + 1) % suggestions.length);
        setSuggestOpen(true);
      }
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (suggestions.length > 0) {
        setActiveIndex((prev) => (prev <= 0 ? suggestions.length - 1 : prev - 1));
        setSuggestOpen(true);
      }
    } else if (e.key === "Escape") {
      setSuggestOpen(false);
      setInputVal("");
      setError(null);
    }
  };

  return (
    <div className="agent-skills-editor" ref={containerRef}>
      {visibleTagOptions.length > 0 ? (
        <div
          className="agent-skills-editor__tag-options"
          role="group"
          aria-label="Skill collections"
        >
          {visibleTagOptions.map((opt) => (
            <button
              key={opt.tag}
              type="button"
              className="agent-skills-editor__tag-pill"
              onClick={() => handlePickTag(opt)}
              disabled={disabled}
            >
              {opt.tag}
            </button>
          ))}
        </div>
      ) : null}

      <div
        className="agent-skills-editor__chips"
        onClick={() => inputRef.current?.focus()}
      >
        {skills.map((slug) => {
          const matched = knownSkills.find((s) => s.slug.toLowerCase() === slug.toLowerCase());
          const displayName = matched ? matched.name : slug;
          return (
            <span key={slug} className="agent-skills-editor__chip">
              <span className="agent-skills-editor__chip-label">{displayName}</span>
              {!disabled ? (
                <button
                  type="button"
                  className="agent-skills-editor__chip-remove"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleRemove(slug);
                  }}
                  aria-label={`Remove skill ${displayName}`}
                >
                  <X size={11} />
                </button>
              ) : null}
            </span>
          );
        })}

        <div className="agent-skills-editor__input-wrapper">
          <input
            ref={inputRef}
            type="text"
            className="agent-skills-editor__input"
            value={inputVal}
            onChange={(e) => {
              setInputVal(e.target.value);
              setError(null);
              setSuggestOpen(true);
              setActiveIndex(0);
            }}
            onFocus={() => setSuggestOpen(true)}
            onKeyDown={handleKeyDown}
            placeholder={skills.length === 0 ? placeholder : ""}
            disabled={disabled}
            aria-label="Attach skill"
            aria-expanded={suggestOpen && suggestions.length > 0}
            role="combobox"
          />

          {suggestOpen && suggestions.length > 0 ? (
            <ul className="agent-skills-editor__suggestions" role="listbox">
              {suggestions.map((s, idx) => (
                <li
                  key={s.slug}
                  ref={idx === activeIndex ? activeOptionRef : undefined}
                  className="agent-skills-editor__suggestion"
                  role="option"
                  aria-selected={idx === activeIndex}
                  data-active={idx === activeIndex}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    handleAdd(s.slug);
                  }}
                >
                  <span className="agent-skills-editor__suggestion-name">{s.name}</span>
                  {s.name !== s.slug ? (
                    <span className="agent-skills-editor__suggestion-slug">({s.slug})</span>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>

      {error ? <div className="agent-skills-editor__error">{error}</div> : null}
    </div>
  );
}
