import { Link } from "react-router-dom";

import type { OverviewShortcut } from "../../../app/capability-registry";
import { useOverviewCopy } from "../i18n";

interface QuickLinksProps {
  shortcuts: OverviewShortcut[];
}

export function QuickLinks({ shortcuts }: QuickLinksProps) {
  const copy = useOverviewCopy();
  const groups: Array<{ key: OverviewShortcut["group"]; label: string }> = [
    { key: "manage", label: copy.sections.manageGroup },
    { key: "discover", label: copy.sections.discoverGroup },
  ];

  return (
    <section className="overview-shortcuts" aria-labelledby="overview-shortcuts-title">
      <div className="overview-section__head">
        <h2 id="overview-shortcuts-title">{copy.sections.shortcuts}</h2>
      </div>
      <div className="overview-shortcuts__groups">
        {groups.map((group) => (
          <div className="overview-shortcuts__group" key={group.key}>
            <span className="overview-shortcuts__group-label">{group.label}</span>
            <div className="overview-shortcuts__chips">
              {shortcuts
                .filter((shortcut) => shortcut.group === group.key)
                .map((shortcut) => (
                  <Link
                    key={shortcut.key}
                    to={shortcut.to}
                    className={`overview-route-chip${group.key === "manage" ? " overview-route-chip--primary" : ""}`}
                  >
                    {shortcut.label}
                  </Link>
                ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
