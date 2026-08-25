import { FileText, Folder, Terminal } from "lucide-react";

import { groupPackageFiles } from "../../model/package-contents";

interface SkillPackageContentsProps {
  files: string[];
}

/**
 * What is in the skill folder besides `SKILL.md`.
 *
 * Adoption copies the whole package, so a user has to be able to see whether a
 * skill ships scripts before enabling it on a harness that will run them.
 */
export function SkillPackageContents({ files }: SkillPackageContentsProps) {
  const groups = groupPackageFiles(files);
  if (groups.length === 0) return null;

  return (
    <ul className="skill-package-contents">
      {groups.map((group) => (
        <li key={group.name} className="skill-package-contents__group">
          <div className="skill-package-contents__header">
            {group.executable ? (
              <Terminal size={13} aria-hidden="true" />
            ) : group.isDirectory ? (
              <Folder size={13} aria-hidden="true" />
            ) : (
              <FileText size={13} aria-hidden="true" />
            )}
            <span className="skill-package-contents__name">
              {group.isDirectory ? `${group.name}/` : group.name}
            </span>
            {group.executable ? (
              <span className="skill-package-contents__badge">Executable</span>
            ) : null}
            {group.isDirectory ? (
              <span className="skill-package-contents__count">
                {group.files.length} {group.files.length === 1 ? "file" : "files"}
              </span>
            ) : null}
          </div>
          {group.files.length > 0 ? (
            <ul className="skill-package-contents__files">
              {group.files.map((file) => (
                <li key={file}>{file}</li>
              ))}
            </ul>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
