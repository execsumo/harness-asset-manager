import { useEffect, useRef, useState } from "react";
import * as Popover from "@radix-ui/react-popover";
import { Star, Tag as TagIcon, X } from "lucide-react";

import { LoadingSpinner } from "./LoadingSpinner";

export interface BulkTagPopoverProps {
  knownTags?: string[];
  onApply: (tags: string[]) => Promise<void>;
  disabled?: boolean;
  pending?: boolean;
}

export function BulkTagPopover({
  knownTags = [],
  onApply,
  disabled = false,
  pending = false,
}: BulkTagPopoverProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [stagedTags, setStagedTags] = useState<string[]>([]);
  const [inputVal, setInputVal] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [suggestionsOpen, setSuggestionsOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen) {
      // Focus input when opened
      const timer = window.setTimeout(() => {
        inputRef.current?.focus();
      }, 50);
      return () => window.clearTimeout(timer);
    }
    return undefined;
  }, [isOpen]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setSuggestionsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const stagedLowerSet = new Set(stagedTags.map((t) => t.toLowerCase()));
  const suggestions = knownTags
    .filter((t) => !stagedLowerSet.has(t.toLowerCase()))
    .filter((t) => (inputVal.trim() ? t.toLowerCase().includes(inputVal.trim().toLowerCase()) : true))
    .slice(0, 6);

  const commitTag = (rawTag: string): boolean => {
    const trimmed = rawTag.trim();
    if (!trimmed) return false;
    if (trimmed.length > 64) {
      setError("Tag must be 64 characters or fewer");
      return false;
    }
    const lower = trimmed.toLowerCase();
    if (stagedTags.some((t) => t.toLowerCase() === lower)) {
      setError("Tag already added");
      return false;
    }
    setError(null);
    setStagedTags((prev) => [...prev, trimmed]);
    setInputVal("");
    setSuggestionsOpen(true);
    return true;
  };

  const removeStagedTag = (idx: number) => {
    setStagedTags((prev) => prev.filter((_, i) => i !== idx));
    setError(null);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "," || e.key === "Enter") {
      e.preventDefault();
      if (inputVal.trim()) {
        commitTag(inputVal);
      } else if (e.key === "Enter" && stagedTags.length > 0) {
        void handleApply();
      }
    } else if (e.key === "Backspace" && !inputVal && stagedTags.length > 0) {
      removeStagedTag(stagedTags.length - 1);
    } else if (e.key === "Escape") {
      setIsOpen(false);
    }
  };

  const handleApply = async () => {
    let finalTags = [...stagedTags];
    if (inputVal.trim()) {
      const trimmed = inputVal.trim();
      if (trimmed.length > 64) {
        setError("Tag must be 64 characters or fewer");
        return;
      }
      const lower = trimmed.toLowerCase();
      if (!stagedTags.some((t) => t.toLowerCase() === lower)) {
        finalTags = [...finalTags, trimmed];
      }
    }

    if (finalTags.length === 0) {
      setError("Enter at least one tag");
      return;
    }

    setError(null);
    try {
      await onApply(finalTags);
      setIsOpen(false);
      setStagedTags([]);
      setInputVal("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to apply tags");
    }
  };

  return (
    <Popover.Root
      open={isOpen}
      onOpenChange={(open) => {
        if (disabled && open) return;
        setIsOpen(open);
        if (!open) {
          setStagedTags([]);
          setInputVal("");
          setError(null);
          setSuggestionsOpen(false);
        }
      }}
    >
      <Popover.Trigger asChild>
        <button
          type="button"
          className="bulk-bar__action"
          disabled={disabled}
          aria-label="Tag selected"
        >
          {pending ? (
            <LoadingSpinner size="sm" label="Tagging" />
          ) : (
            <TagIcon size={15} />
          )}
          Tag
        </button>
      </Popover.Trigger>

      <Popover.Portal>
        <Popover.Content
          className="ui-popup bulk-tag-popover"
          side="top"
          align="center"
          sideOffset={10}
        >
          <div className="bulk-tag-popover__header">
            <span className="bulk-tag-popover__title">Add tags to selected</span>
          </div>

          <div className="bulk-tag-popover__body" ref={containerRef}>
            <div
              className="bulk-tag-popover__input-box"
              onClick={() => inputRef.current?.focus()}
            >
              {stagedTags.map((tag, idx) => {
                const isStarred = tag.toLowerCase() === "starred";
                return (
                  <span
                    key={tag}
                    className={`bulk-tag-popover__chip ${isStarred ? "bulk-tag-popover__chip--starred" : ""}`}
                  >
                    {isStarred ? <Star size={11} className="skill-detail-tag__star" /> : null}
                    <span>{tag}</span>
                    <button
                      type="button"
                      className="bulk-tag-popover__chip-remove"
                      onClick={(e) => {
                        e.stopPropagation();
                        removeStagedTag(idx);
                      }}
                      aria-label={`Remove tag ${tag}`}
                    >
                      <X size={10} />
                    </button>
                  </span>
                );
              })}
              <input
                ref={inputRef}
                type="text"
                className="bulk-tag-popover__input"
                value={inputVal}
                onChange={(e) => {
                  setInputVal(e.target.value);
                  setError(null);
                  setSuggestionsOpen(true);
                }}
                onFocus={() => setSuggestionsOpen(true)}
                onKeyDown={handleKeyDown}
                placeholder={stagedTags.length === 0 ? "Type tag name..." : "Add another..."}
                disabled={disabled || pending}
                maxLength={64}
                aria-label="New tag name"
              />
            </div>

            {suggestionsOpen && suggestions.length > 0 ? (
              <ul className="bulk-tag-popover__suggestions" role="listbox" aria-label="Tag suggestions">
                {suggestions.map((suggestion) => (
                  <li
                    key={suggestion}
                    className="bulk-tag-popover__suggestion"
                    role="option"
                    aria-selected={false}
                    onMouseDown={(e) => {
                      e.preventDefault();
                      commitTag(suggestion);
                      inputRef.current?.focus();
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

            {error ? (
              <div className="bulk-tag-popover__error" role="alert">
                {error}
              </div>
            ) : null}
          </div>

          <div className="bulk-tag-popover__footer">
            <button
              type="button"
              className="action-pill action-pill--sm"
              onClick={() => setIsOpen(false)}
              disabled={pending}
            >
              Cancel
            </button>
            <button
              type="button"
              className="action-pill action-pill--sm action-pill--accent"
              onClick={() => void handleApply()}
              disabled={disabled || pending || (stagedTags.length === 0 && !inputVal.trim())}
            >
              {pending ? <LoadingSpinner size="sm" label="Applying..." /> : "Apply"}
            </button>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
