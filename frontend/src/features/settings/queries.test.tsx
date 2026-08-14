import { fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { mcpManagementKeys } from "../mcp/public";
import { skillsKeys } from "../skills/public";
import { okJson } from "../../test/fetch";
import { renderWithAppProviders } from "../../test/render";
import { settingsKeys, useAutoAdoptMutation, useHarnessSupportMutation } from "./queries";

const fetchMock = vi.fn();

function HarnessSupportProbe() {
  const mutation = useHarnessSupportMutation();

  return (
    <button
      type="button"
      onClick={() => mutation.mutate({ harness: "codex", enabled: false })}
    >
      Disable Codex support
    </button>
  );
}

describe("settings queries", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("invalidates settings, skills, and MCP after harness support changes", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/api/settings/harnesses/codex/support") {
        expect(init?.method).toBe("PUT");
        expect(JSON.parse(String(init?.body))).toEqual({ enabled: false });
        return okJson({ ok: true, enabled: false });
      }
      throw new Error(`Unhandled URL ${url}`);
    });

    const { queryClient } = renderWithAppProviders(<HarnessSupportProbe />);
    queryClient.setQueryData(settingsKeys.detail(), {
      storage: {
        platform: "linux",
        configDir: "/tmp/config/harnessam",
        dataDir: "/tmp/data/harnessam",
        stateDir: "/tmp/state/harnessam",
        skillsStorePath: "/tmp/data/harnessam/shared",
        marketplaceCachePath: "/tmp/data/harnessam/marketplace",
        settingsPath: "/tmp/config/harnessam/settings.json",
      },
      harnesses: [
        {
          harness: "codex",
          label: "Codex",
          logoKey: "codex",
          supportEnabled: true,
          installed: true,
          managedLocation: "/tmp/codex",
        },
      ],
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    fireEvent.click(screen.getByRole("button", { name: "Disable Codex support" }));

    await waitFor(() =>
      expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: mcpManagementKeys.all }),
    );
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: settingsKeys.all });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: skillsKeys.list() });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: skillsKeys.detailPrefix() });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: skillsKeys.sourceStatusPrefix() });
  });

  it("calls exact URL /api/settings/auto-adopt/agents when mutating auto-adopt", async () => {
    fetchMock.mockImplementation(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url === "/api/settings/auto-adopt/agents") {
        expect(init?.method).toBe("PUT");
        expect(JSON.parse(String(init?.body))).toEqual({ enabled: false });
        return okJson({ ok: true, autoAdopt: { agents: false, skills: false } });
      }
      throw new Error(`Unhandled URL ${url}`);
    });

    function AutoAdoptProbe() {
      const mutation = useAutoAdoptMutation();
      return (
        <button
          type="button"
          onClick={() => mutation.mutate({ family: "agents", enabled: false })}
        >
          Toggle auto-adopt agents
        </button>
      );
    }

    renderWithAppProviders(<AutoAdoptProbe />);

    fireEvent.click(screen.getByRole("button", { name: "Toggle auto-adopt agents" }));

    await waitFor(() => {
      const call = fetchMock.mock.calls.find((c) => {
        const u = typeof c[0] === "string" ? c[0] : c[0].toString();
        return u === "/api/settings/auto-adopt/agents";
      });
      expect(call).toBeDefined();
      if (!call) return;
      expect(typeof call[0] === "string" ? call[0] : call[0].toString()).toBe("/api/settings/auto-adopt/agents");
    });
  });
});
