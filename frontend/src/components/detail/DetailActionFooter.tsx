import type { ReactNode } from "react";

export interface DetailActionFooterProps {
  children?: ReactNode;
  ariaLabel?: string;
  className?: string;
}

export function DetailActionFooter({
  children,
  ariaLabel = "Actions",
  className,
}: DetailActionFooterProps) {
  if (!children) {
    return null;
  }

  const classes = className
    ? `detail-action-footer ${className}`
    : "detail-action-footer";

  return (
    <footer className={classes} aria-label={ariaLabel}>
      {children}
    </footer>
  );
}
