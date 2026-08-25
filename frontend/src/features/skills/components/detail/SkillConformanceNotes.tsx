import { AlertTriangle } from "lucide-react";

import type { SkillConformanceIssue } from "../../model/types";

interface SkillConformanceNotesProps {
  issues: SkillConformanceIssue[];
}

/**
 * Where this skill departs from the Agent Skills specification.
 *
 * Advisory only — HAM keys skills on their package directory, so none of this stops
 * the skill working. Each note says what to correct rather than naming a rule, so it
 * is actionable without opening the spec.
 */
export function SkillConformanceNotes({ issues }: SkillConformanceNotesProps) {
  if (issues.length === 0) return null;

  return (
    <ul className="skill-conformance">
      {issues.map((issue) => (
        <li key={issue.code} className="skill-conformance__note">
          <AlertTriangle size={13} aria-hidden="true" />
          <span>{issue.message}</span>
        </li>
      ))}
    </ul>
  );
}
