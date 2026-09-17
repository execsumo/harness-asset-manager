import { useEffect, useRef, useState } from "react";
import { Bot, Search, X } from "lucide-react";

interface SkillAgentCount {
  ref: string;
  name: string;
  count: number;
}

interface SkillAgentFilterBarProps {
  agents: SkillAgentCount[];
  selectedAgents: string[];
  onToggleAgent: (agentRef: string) => void;
  onClearAgents?: () => void;
}

export function SkillAgentFilterBar({
  agents,
  selectedAgents,
  onToggleAgent,
  onClearAgents,
}: SkillAgentFilterBarProps) {
  const [filterQuery, setFilterQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const normalizedSelected = new Set(selectedAgents);

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

  const filteredAgents = filterQuery.trim()
    ? agents.filter((t) => t.name.toLowerCase().includes(filterQuery.trim().toLowerCase()))
    : agents;

  if (agents.length === 0 && selectedAgents.length === 0) {
    return null;
  }

  return (
    <div className="skill-tag-filter-bar" ref={containerRef} role="group" aria-label="Filter by agent">
      <div className="skill-tag-filter-bar__chips">
        {/* Regular agent chips */}
        {filteredAgents.map((item) => {
          const isSelected = normalizedSelected.has(item.ref);
          return (
            <button
              key={item.ref}
              type="button"
              className={`skill-tag-chip ${isSelected ? "skill-tag-chip--active" : ""}`}
              onClick={() => onToggleAgent(item.ref)}
              aria-pressed={isSelected}
            >
              <Bot size={13} className="skill-tag-chip__icon" style={{ marginRight: '4px' }} />
              <span>{item.name}</span>
              <span className="skill-tag-chip__count">{item.count}</span>
            </button>
          );
        })}

        {/* Selected agents that might not be in the known list */}
        {selectedAgents
          .filter((t) => !agents.some((rt) => rt.ref === t))
          .map((orphanAgent) => (
            <button
              key={orphanAgent}
              type="button"
              className="skill-tag-chip skill-tag-chip--active"
              onClick={() => onToggleAgent(orphanAgent)}
              aria-pressed={true}
            >
              <Bot size={13} className="skill-tag-chip__icon" style={{ marginRight: '4px' }} />
              <span>{orphanAgent}</span>
              <span className="skill-tag-chip__count">0</span>
            </button>
          ))}

        {/* Agent filter search input / button if there are many agents */}
        {agents.length > 3 ? (
          searchOpen ? (
            <div className="skill-tag-filter-bar__search-inline">
              <input
                ref={searchInputRef}
                type="text"
                className="skill-tag-filter-bar__search-input"
                placeholder="Find agent..."
                value={filterQuery}
                onChange={(e) => setFilterQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Escape") {
                    setSearchOpen(false);
                    setFilterQuery("");
                  } else if (e.key === "Enter" && filteredAgents.length === 1) {
                    onToggleAgent(filteredAgents[0].ref);
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
                aria-label="Close agent search"
              >
                <X size={12} />
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="skill-tag-filter-bar__search-toggle"
              onClick={() => setSearchOpen(true)}
              aria-label="Search agents"
              title="Search agents"
            >
              <Search size={12} />
            </button>
          )
        ) : null}

        {/* Clear all active agent filters */}
        {selectedAgents.length > 0 && onClearAgents ? (
          <button
            type="button"
            className="skill-tag-filter-bar__clear-btn"
            onClick={onClearAgents}
            aria-label="Clear agent filters"
          >
            <X size={12} />
            <span>Clear agents</span>
          </button>
        ) : null}
      </div>
    </div>
  );
}
