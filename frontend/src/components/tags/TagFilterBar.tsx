import { useEffect, useRef, useState } from "react";
import { Search, Star, X } from "lucide-react";

import type { AssetTagCount } from "./tag-counts";

export interface TagFilterBarProps {
  tags: AssetTagCount[];
  selectedTags: string[];
  onToggleTag: (tag: string) => void;
  onClearTags?: () => void;
}

export function TagFilterBar({
  tags,
  selectedTags,
  onToggleTag,
  onClearTags,
}: TagFilterBarProps) {
  const [filterQuery, setFilterQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const normalizedSelected = new Set(selectedTags.map((t) => t.toLowerCase()));

  useEffect(() => {
    if (searchOpen) {
      searchInputRef.current?.focus();
    }
  }, [searchOpen]);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setSearchOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const starredItem = tags.find((t) => t.isStarred) ?? { tag: "starred", count: 0, isStarred: true };
  const regularTags = tags.filter((t) => !t.isStarred);

  const filteredRegularTags = filterQuery.trim()
    ? regularTags.filter((t) => t.tag.toLowerCase().includes(filterQuery.trim().toLowerCase()))
    : regularTags;

  const isStarredSelected = normalizedSelected.has("starred");

  if (tags.length === 0 && selectedTags.length === 0) {
    return null;
  }

  return (
    <div className="skill-tag-filter-bar" ref={containerRef} role="group" aria-label="Filter by tag">
      <div className="skill-tag-filter-bar__chips">
        {/* Pinned starred chip */}
        <button
          type="button"
          className={`skill-tag-chip skill-tag-chip--starred ${isStarredSelected ? "skill-tag-chip--active" : ""}`}
          onClick={() => onToggleTag("starred")}
          aria-pressed={isStarredSelected}
        >
          <Star
            size={13}
            className={`skill-tag-chip__star ${isStarredSelected ? "skill-tag-chip__star--filled" : ""}`}
          />
          <span>starred</span>
          <span className="skill-tag-chip__count">{starredItem.count}</span>
        </button>

        {/* Regular tag chips */}
        {filteredRegularTags.map((item) => {
          const isSelected = normalizedSelected.has(item.tag.toLowerCase());
          return (
            <button
              key={item.tag}
              type="button"
              className={`skill-tag-chip ${isSelected ? "skill-tag-chip--active" : ""}`}
              onClick={() => onToggleTag(item.tag)}
              aria-pressed={isSelected}
            >
              <span>{item.tag}</span>
              <span className="skill-tag-chip__count">{item.count}</span>
            </button>
          );
        })}

        {/* Selected tags that might not be in the known list */}
        {selectedTags
          .filter((t) => t.toLowerCase() !== "starred")
          .filter((t) => !regularTags.some((rt) => rt.tag.toLowerCase() === t.toLowerCase()))
          .map((orphanTag) => (
            <button
              key={orphanTag}
              type="button"
              className="skill-tag-chip skill-tag-chip--active"
              onClick={() => onToggleTag(orphanTag)}
              aria-pressed={true}
            >
              <span>{orphanTag}</span>
              <span className="skill-tag-chip__count">0</span>
            </button>
          ))}

        {/* Tag filter search input / button if there are many tags */}
        {regularTags.length > 3 ? (
          searchOpen ? (
            <div className="skill-tag-filter-bar__search-inline">
              <input
                ref={searchInputRef}
                type="text"
                className="skill-tag-filter-bar__search-input"
                placeholder="Find tag..."
                value={filterQuery}
                onChange={(e) => setFilterQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Escape") {
                    setSearchOpen(false);
                    setFilterQuery("");
                  } else if (e.key === "Enter" && filteredRegularTags.length === 1) {
                    onToggleTag(filteredRegularTags[0].tag);
                    setSearchOpen(false);
                    setFilterQuery("");
                  }
                }}
              />
              <button
                type="button"
                className="skill-tag-filter-bar__search-clear"
                onClick={() => {
                  setSearchOpen(false);
                  setFilterQuery("");
                }}
                aria-label="Close tag search"
              >
                <X size={12} />
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="skill-tag-filter-bar__search-toggle"
              onClick={() => setSearchOpen(true)}
              aria-label="Search tags"
              title="Search tags"
            >
              <Search size={12} />
            </button>
          )
        ) : null}

        {/* Clear all active tag filters */}
        {selectedTags.length > 0 && onClearTags ? (
          <button
            type="button"
            className="skill-tag-filter-bar__clear-btn"
            onClick={onClearTags}
            aria-label="Clear tag filters"
          >
            <X size={12} />
            <span>Clear tags</span>
          </button>
        ) : null}
      </div>
    </div>
  );
}
