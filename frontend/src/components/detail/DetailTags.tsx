import { useEffect, useRef, useState } from "react";
import { Plus, Star, X } from "lucide-react";

export interface DetailTagsProps {
  tags: string[];
  knownTags?: string[];
  canEdit: boolean;
  onAddTag: (tag: string) => Promise<void>;
  onRemoveTag: (tag: string) => Promise<void>;
  disabled?: boolean;
}

export function DetailTags({
  tags,
  knownTags = [],
  canEdit,
  onAddTag,
  onRemoveTag,
  disabled = false,
}: DetailTagsProps) {
  const [isAdding, setIsAdding] = useState(false);
  const [inputVal, setInputVal] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [suggestOpen, setSuggestOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isAdding) {
      inputRef.current?.focus();
    }
  }, [isAdding]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setSuggestOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const normalizedExisting = new Set(tags.map((t) => t.toLowerCase()));
  const suggestions = knownTags
    .filter((t) => !normalizedExisting.has(t.toLowerCase()))
    .filter((t) => (inputVal.trim() ? t.toLowerCase().includes(inputVal.trim().toLowerCase()) : true))
    .slice(0, 6);

  const handleAdd = async (tagToAdd: string) => {
    const trimmed = tagToAdd.trim();
    if (!trimmed) {
      setError("Tag cannot be empty");
      return;
    }
    if (trimmed.length > 64) {
      setError("Tag must be 64 characters or fewer");
      return;
    }
    if (normalizedExisting.has(trimmed.toLowerCase())) {
      setError("Tag already added");
      return;
    }

    setError(null);
    try {
      await onAddTag(trimmed);
      setInputVal("");
      setIsAdding(false);
      setSuggestOpen(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add tag");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      void handleAdd(inputVal);
    } else if (e.key === "Escape") {
      setIsAdding(false);
      setInputVal("");
      setError(null);
      setSuggestOpen(false);
    }
  };

  return (
    <div className="skill-detail-tags" ref={containerRef}>
      <div className="skill-detail-tags__list">
        {tags.map((tag) => {
          const isStarred = tag.toLowerCase() === "starred";
          return (
            <span
              key={tag}
              className={`skill-detail-tag ${isStarred ? "skill-detail-tag--starred" : ""}`}
            >
              {isStarred ? (
                <Star size={12} className="skill-detail-tag__star" />
              ) : null}
              <span className="skill-detail-tag__label">{tag}</span>
              {canEdit ? (
                <button
                  type="button"
                  className="skill-detail-tag__remove"
                  onClick={() => void onRemoveTag(tag)}
                  disabled={disabled}
                  aria-label={`Remove tag ${tag}`}
                >
                  <X size={11} />
                </button>
              ) : null}
            </span>
          );
        })}

        {tags.length === 0 && !isAdding && !canEdit ? (
          <span className="skill-detail-tags__empty">No tags</span>
        ) : null}

        {canEdit && !isAdding ? (
          <button
            type="button"
            className="skill-detail-tags__add-btn"
            onClick={() => {
              setIsAdding(true);
              setSuggestOpen(true);
            }}
            disabled={disabled}
            aria-label="Add tag"
          >
            <Plus size={12} />
            <span>Add tag</span>
          </button>
        ) : null}

        {canEdit && isAdding ? (
          <div className="skill-detail-tags__input-wrapper">
            <input
              ref={inputRef}
              type="text"
              className="skill-detail-tags__input"
              value={inputVal}
              onChange={(e) => {
                setInputVal(e.target.value);
                setError(null);
                setSuggestOpen(true);
              }}
              onFocus={() => setSuggestOpen(true)}
              onKeyDown={handleKeyDown}
              placeholder="Tag name..."
              disabled={disabled}
              maxLength={64}
            />
            <button
              type="button"
              className="skill-detail-tags__confirm-btn"
              onClick={() => void handleAdd(inputVal)}
              disabled={disabled || !inputVal.trim()}
              aria-label="Confirm tag"
            >
              Add
            </button>
            <button
              type="button"
              className="skill-detail-tags__cancel-btn"
              onClick={() => {
                setIsAdding(false);
                setInputVal("");
                setError(null);
                setSuggestOpen(false);
              }}
              aria-label="Cancel tag edit"
            >
              <X size={12} />
            </button>

            {suggestOpen && suggestions.length > 0 ? (
              <ul className="skill-detail-tags__suggestions" role="listbox">
                {suggestions.map((suggestion) => (
                  <li
                    key={suggestion}
                    className="skill-detail-tags__suggestion"
                    role="option"
                    aria-selected={false}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      void handleAdd(suggestion);
                    }}
                  >
                    {suggestion.toLowerCase() === "starred" ? (
                      <Star size={11} className="skill-detail-tag__star" />
                    ) : null}
                    <span>{suggestion}</span>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : null}
      </div>

      {error ? <div className="skill-detail-tags__error">{error}</div> : null}
    </div>
  );
}
