import { act, fireEvent, render, screen } from "@testing-library/react";
import { Link, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { okJson } from "../test/fetch";
import { renderWithAppProviders, stubDesktopMatchMedia } from "../test/render";
import { ThemeProvider } from "../lib/theme";
import {
  CHUNK_RELOAD_GUARD_MS,
  CHUNK_RELOAD_STORAGE_KEY,
  ErrorBoundary,
  claimStaleChunkReload,
  isChunkLoadError,
} from "./ErrorBoundary";
import { Shell } from "./Shell";

const CHUNK_MESSAGE = "Failed to fetch dynamically imported module: http://x/assets/Page-abc.js";

let shouldThrow = true;
let throwMessage = "Boom from page";

function Bomb() {
  if (shouldThrow) throw new Error(throwMessage);
  return <p>page ok</p>;
}

function ShellWithRoutes() {
  return (
    <ThemeProvider>
      <Shell onRefresh={() => undefined} refreshPending={false}>
        <Routes>
          <Route path="broken" element={<Bomb />} />
          <Route path="fine" element={<p>fine page</p>} />
        </Routes>
      </Shell>
    </ThemeProvider>
  );
}

function renderShell(route = "/broken") {
  return renderWithAppProviders(<ShellWithRoutes />, { route });
}

describe("ErrorBoundary", () => {
  const reload = vi.fn();

  beforeEach(() => {
    shouldThrow = true;
    throwMessage = "Boom from page";
    reload.mockReset();
    window.sessionStorage.clear();
    stubDesktopMatchMedia();
    vi.stubGlobal("fetch", vi.fn(async () => okJson({})));
    vi.stubGlobal("location", { ...window.location, reload });
    vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("shows the route fallback with the error text while the Shell navigation stays", () => {
    renderShell();
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("Something went wrong");
    expect(alert).toHaveTextContent("Boom from page");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reload page" })).toBeInTheDocument();
    expect(screen.getByLabelText(/primary navigation/i)).toBeInTheDocument();
  });

  it("logs the error with its component stack", () => {
    renderShell();
    const calls = vi.mocked(console.error).mock.calls;
    const logged = calls.find(([message]) => message === "Unhandled render error");
    expect(logged).toBeDefined();
    expect((logged?.[1] as Error).message).toBe("Boom from page");
    expect(String(logged?.[2])).toContain("Bomb");
  });

  it("re-renders the child when Try again is pressed", () => {
    renderShell();
    shouldThrow = false;
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText("page ok")).toBeInTheDocument();
  });

  it("reloads the page from the Reload page button", () => {
    renderShell();
    fireEvent.click(screen.getByRole("button", { name: "Reload page" }));
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("reloads once for a chunk-load error, then shows the updated fallback", () => {
    throwMessage = CHUNK_MESSAGE;
    const first = renderShell();
    expect(reload).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("alert")).toHaveTextContent("Reloading the page");
    first.unmount();

    renderShell();
    expect(reload).toHaveBeenCalledTimes(1);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("HarnessAM was updated");
    expect(alert).toHaveTextContent("Reload the page to use it");
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reload page" })).toBeInTheDocument();
  });

  it("reloads again once the guard window has passed", () => {
    window.sessionStorage.setItem(
      CHUNK_RELOAD_STORAGE_KEY,
      String(Date.now() - CHUNK_RELOAD_GUARD_MS - 1),
    );
    throwMessage = CHUNK_MESSAGE;
    renderShell();
    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("does not reload for an ordinary render error", () => {
    renderShell();
    expect(reload).not.toHaveBeenCalled();
    expect(window.sessionStorage.getItem(CHUNK_RELOAD_STORAGE_KEY)).toBeNull();
  });

  it("renders the minimal top-level fallback", () => {
    render(
      <ErrorBoundary variant="app">
        <Bomb />
      </ErrorBoundary>,
    );
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("HarnessAM hit an unexpected error");
    expect(alert).toHaveTextContent("Boom from page");
    expect(screen.queryByRole("button", { name: "Try again" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reload page" }));
    expect(reload).toHaveBeenCalledTimes(1);
  });
});

describe("isChunkLoadError", () => {
  it.each([
    "Failed to fetch dynamically imported module: /a.js",
    "error loading dynamically imported module: /a.js",
    "Importing a module script failed.",
    "Unable to preload CSS for /assets/a.css",
  ])("matches %s", (message) => {
    expect(isChunkLoadError(new Error(message))).toBe(true);
  });

  it("rejects ordinary errors and non-errors", () => {
    expect(isChunkLoadError(new Error("nope"))).toBe(false);
    expect(isChunkLoadError(null)).toBe(false);
    expect(isChunkLoadError("Failed to fetch dynamically imported module")).toBe(false);
  });
});

describe("claimStaleChunkReload", () => {
  beforeEach(() => window.sessionStorage.clear());

  it("grants one claim per guard window", () => {
    expect(claimStaleChunkReload(1_000_000)).toBe(true);
    expect(claimStaleChunkReload(1_000_000 + 1)).toBe(false);
    expect(claimStaleChunkReload(1_000_000 + CHUNK_RELOAD_GUARD_MS)).toBe(true);
  });

  it("refuses when sessionStorage is unavailable", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("denied");
    });
    expect(claimStaleChunkReload()).toBe(false);
    vi.restoreAllMocks();
  });
});

// Route-reset behaviour lives in its own block: it needs a navigation inside the Shell.
describe("RouteErrorBoundary reset", () => {
  beforeEach(() => {
    shouldThrow = true;
    throwMessage = "Boom from page";
    stubDesktopMatchMedia();
    vi.stubGlobal("fetch", vi.fn(async () => okJson({})));
    vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("clears the fallback when the pathname changes", async () => {
    // A link outside the boundary stands in for the Shell sidebar.
    renderWithAppProviders(
      <>
        <Link to="/fine">go fine</Link>
        <ShellWithRoutes />
      </>,
      { route: "/broken" },
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    await act(async () => {
      fireEvent.click(screen.getByRole("link", { name: "go fine" }));
    });
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText("fine page")).toBeInTheDocument();
  });
});
