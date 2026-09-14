import type { ReactNode } from "react";

export type DetailNoteTone = "warning" | "danger" | "info";

interface DetailNoteProps {
  children: ReactNode;
  className?: string;
  tone?: DetailNoteTone;
  title?: ReactNode;
  actions?: ReactNode;
}

export function DetailNote({
  children,
  className,
  tone = "warning",
  title,
  actions,
}: DetailNoteProps) {
  const classes = ["detail-note", `detail-note--${tone}`, className]
    .filter(Boolean)
    .join(" ");
  return (
    <div className={classes}>
      {title ? <p className="detail-note__title">{title}</p> : null}
      <div className="detail-note__body">{children}</div>
      {actions ? <div className="detail-note__actions">{actions}</div> : null}
    </div>
  );
}
