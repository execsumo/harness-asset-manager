import { useCallback, useRef } from "react";

import { errorMessage } from "../../../api/http";

export interface ConfigActionError {
  /** Changes on every failure so a repeat of the same message still re-shows its banner. */
  id: number;
  message: string;
}

/** A readable one-line message: what failed, then why, with no "ApiError:" prefix. */
export function describeActionError(headline: string, error: unknown): string {
  const detail = errorMessage(error, "").replace(/^\w*Error:\s*/, "").trim();
  return detail ? `${headline} ${detail}` : headline;
}

/** Run an action and report its failure instead of leaving a rejected promise unhandled. */
export async function reportFailure(
  report: (message: string) => void,
  headline: string,
  action: () => Promise<unknown>,
): Promise<boolean> {
  try {
    await action();
    return true;
  } catch (error) {
    report(describeActionError(headline, error));
    return false;
  }
}

/**
 * Drops a repeat of an action that is still running. A mutation's `isPending`
 * flag reaches the button one render late, so two quick clicks would otherwise
 * both send a request.
 */
export function useSingleFlight(): <T>(key: string, run: () => Promise<T>) => Promise<T | undefined> {
  const running = useRef(new Set<string>());
  return useCallback(async (key, run) => {
    if (running.current.has(key)) return undefined;
    running.current.add(key);
    try {
      return await run();
    } finally {
      running.current.delete(key);
    }
  }, []);
}
