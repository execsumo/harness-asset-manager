import "@testing-library/jest-dom/vitest";
import { configure } from "@testing-library/react";
import { vi } from "vitest";

import { installMockLocalStorage } from "./local-storage";

// Route and detail views intentionally load some expensive chunks lazily. Keep
// async assertions from racing those imports on slower CI workers.
configure({ asyncUtilTimeout: 5000 });

try {
  if (typeof window.localStorage.clear !== "function") {
    installMockLocalStorage();
  }
} catch {
  installMockLocalStorage();
}

if (typeof ResizeObserver === "undefined") {
  class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }

  vi.stubGlobal("ResizeObserver", ResizeObserver);
}

// jsdom implements no layout, so it ships no `scrollIntoView`. Components that
// keep a keyboard-selected option in view call it on every render.
if (typeof Element.prototype.scrollIntoView !== "function") {
  Element.prototype.scrollIntoView = () => {};
}
