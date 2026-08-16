import { screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Routes, useLocation } from "react-router-dom";

import { okJson } from "../../test/fetch";
import { renderWithAppProviders } from "../../test/render";
import { getSlashCommandsRouteElements } from "./routes";

const fetchMock = vi.fn();

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="slash-commands-location">{location.pathname}{location.search}</output>;
}

function renderRoutes(route: string) {
  return renderWithAppProviders(
    <>
      <Routes>{getSlashCommandsRouteElements()}</Routes>
      <LocationProbe />
    </>,
    { route },
  );
}

describe("Slash Commands shared route fragment", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockImplementation(() => okJson({ commands: [], reviewCommands: [], targets: [], defaultTargets: [] }));
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  it("redirects the legacy in-use route to the unified inventory", async () => {
    renderRoutes("/slash-commands/use");
    await waitFor(() => expect(screen.getByTestId("slash-commands-location")).toHaveTextContent("/slash-commands"));
    expect(screen.getByTestId("slash-commands-location")).toHaveTextContent(/^\/slash-commands$/);
  });

  it("redirects the legacy review route to the untracked filter", async () => {
    renderRoutes("/slash-commands/review");
    await waitFor(() =>
      expect(screen.getByTestId("slash-commands-location")).toHaveTextContent("/slash-commands?status=untracked"),
    );
  });
});
