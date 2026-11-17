import { Component, type ErrorInfo, type ReactNode } from "react";
import { useLocation } from "react-router-dom";

import { commonCopy } from "../i18n/common";

/** sessionStorage key holding the time of the last automatic stale-chunk reload. */
export const CHUNK_RELOAD_STORAGE_KEY = "ham:chunk-reload-at";
/** An automatic reload that happened within this window blocks another one. */
export const CHUNK_RELOAD_GUARD_MS = 30_000;

const CHUNK_ERROR_PATTERNS = [
  /failed to fetch dynamically imported module/i,
  /error loading dynamically imported module/i,
  /importing a module script failed/i,
  /unable to preload css/i,
];

/** True when the error is a failed dynamic import, e.g. a chunk hash that no longer exists. */
export function isChunkLoadError(error: unknown): boolean {
  if (!error || typeof error !== "object") return false;
  const { name, message } = error as { name?: unknown; message?: unknown };
  if (name === "ChunkLoadError") return true;
  return typeof message === "string" && CHUNK_ERROR_PATTERNS.some((pattern) => pattern.test(message));
}

/**
 * Claim the one automatic reload allowed per guard window. Returns false when a
 * reload already ran recently, or when sessionStorage is unavailable and the
 * guard cannot be recorded (so a reload loop cannot be ruled out).
 */
export function claimStaleChunkReload(now: number = Date.now()): boolean {
  try {
    const last = Number(window.sessionStorage.getItem(CHUNK_RELOAD_STORAGE_KEY));
    if (Number.isFinite(last) && last > 0 && now - last < CHUNK_RELOAD_GUARD_MS) return false;
    window.sessionStorage.setItem(CHUNK_RELOAD_STORAGE_KEY, String(now));
    return true;
  } catch {
    return false;
  }
}

function reloadPage() {
  window.location.reload();
}

interface ErrorBoundaryProps {
  children: ReactNode;
  /** "route" keeps the shell usable and offers Try again; "app" is a minimal last resort. */
  variant?: "route" | "app";
  /** The boundary resets when this value changes. */
  resetKey?: unknown;
}

interface ErrorBoundaryState {
  error: Error | null;
  reloading: boolean;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null, reloading: false };

  static getDerivedStateFromError(error: unknown): ErrorBoundaryState {
    return { error: error instanceof Error ? error : new Error(String(error)), reloading: false };
  }

  componentDidCatch(error: unknown, info: ErrorInfo) {
    console.error("Unhandled render error", error, info.componentStack);
    if (isChunkLoadError(error) && claimStaleChunkReload()) {
      this.setState({ reloading: true });
      reloadPage();
    }
  }

  componentDidUpdate(prevProps: ErrorBoundaryProps) {
    if (this.state.error && !Object.is(prevProps.resetKey, this.props.resetKey)) {
      this.reset();
    }
  }

  private reset = () => {
    this.setState({ error: null, reloading: false });
  };

  render() {
    const { error, reloading } = this.state;
    if (!error) return this.props.children;

    const copy = commonCopy.errorBoundary;
    const variant = this.props.variant ?? "route";
    const stale = isChunkLoadError(error);

    let title: string = variant === "app" ? copy.appTitle : copy.title;
    let description: string = variant === "app" ? copy.appDescription : copy.description;
    if (stale) {
      title = reloading ? copy.reloadingTitle : copy.updatedTitle;
      description = reloading ? copy.reloadingDescription : copy.updatedDescription;
    }

    return (
      <section
        role="alert"
        className={`error-boundary error-boundary--${variant}${variant === "route" ? " page-panel" : ""}`}
      >
        <h2 className="error-boundary__title">{title}</h2>
        <p className="error-boundary__description">{description}</p>
        {!stale && <pre className="error-boundary__detail">{error.message || String(error)}</pre>}
        <div className="error-boundary__actions">
          {variant === "route" && !stale && (
            <button type="button" className="action-pill action-pill--md action-pill--accent" onClick={this.reset}>
              {copy.tryAgain}
            </button>
          )}
          <button type="button" className="action-pill action-pill--md" onClick={reloadPage}>
            {copy.reload}
          </button>
        </div>
      </section>
    );
  }
}

/** Route-level boundary: resets whenever the location pathname changes. */
export function RouteErrorBoundary({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  return (
    <ErrorBoundary variant="route" resetKey={pathname}>
      {children}
    </ErrorBoundary>
  );
}
