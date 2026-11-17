import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { agentsKeys } from "../features/agents/api/keys";
import { useAdoptAgentMutation, useAgentsInventoryQuery, useDeleteAgentMutation, useEnableAgentMutation, useUpdateAgentMutation } from "../features/agents/api/queries";
import { hooksManagementKeys } from "../features/hooks/api/keys";
import { permissionsManagementKeys } from "../features/permissions/api/keys";
import { useHarnessSupportMutation } from "../features/settings/public";
import { skillsKeys } from "../features/skills/api/keys";
import { useDeleteSkillMutation } from "../features/skills/api/queries";
import { slashCommandKeys } from "../features/slash-commands/api/keys";
import { useSlashCommandsQuery } from "../features/slash-commands/api/queries";
import { useUpdateSlashCommandMutation } from "../features/slash-commands/public";
import { createRouteFetchMock, errorJson, okJson } from "./fetch";

const fetchMock = vi.fn();

function setup<T>(useHook: () => T) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { queryClient, ...renderHook(useHook, { wrapper }) };
}

const agentList = (state: "enabled" | "disabled") => ({
  columns: [{ harness: "claude", label: "Claude", logoKey: "claude", installed: true }],
  issues: [],
  entries: [{ ref: "a1", name: "A1", description: "", kind: "managed", bindings: [{ harness: "claude", state, detail: null }], actions: {} }],
});

function listBindingState(data: unknown) {
  return (data as ReturnType<typeof agentList>).entries[0].bindings[0].state;
}

describe("mutation settle policy", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    fetchMock.mockReset();
  });

  it("agent enable resolves only after the list holds the refetched data", async () => {
    let server: "enabled" | "disabled" = "disabled";
    let listCalls = 0;
    fetchMock.mockImplementation(createRouteFetchMock([
      { match: "/enable", response: () => { server = "enabled"; return okJson({}); } },
      { match: "/api/agents", response: async () => { listCalls += 1; await new Promise((r) => setTimeout(r, 30)); return agentList(server); } },
    ]));
    const { result, queryClient } = setup(() => ({ list: useAgentsInventoryQuery(true), enable: useEnableAgentMutation() }));
    await waitFor(() => expect(listBindingState(result.current.list.data)).toBe("disabled"));

    let atResolve: unknown;
    await act(async () => {
      await result.current.enable.mutateAsync({ ref: "a1", harness: "claude" });
      atResolve = queryClient.getQueryData([...agentsKeys.list(), true]);
    });
    expect(listBindingState(atResolve)).toBe("enabled");
    expect(listCalls).toBe(2);
  });

  it("agent enable that fails with 409 still refetches the list", async () => {
    let listCalls = 0;
    fetchMock.mockImplementation(createRouteFetchMock([
      { match: "/enable", response: errorJson("Conflict", { status: 409, statusText: "Conflict" }) },
      { match: "/api/agents", response: () => { listCalls += 1; return agentList("disabled"); } },
    ]));
    const { result } = setup(() => ({ list: useAgentsInventoryQuery(true), enable: useEnableAgentMutation() }));
    await waitFor(() => expect(listCalls).toBe(1));

    await act(async () => {
      await expect(result.current.enable.mutateAsync({ ref: "a1", harness: "claude" })).rejects.toThrow("Conflict");
    });
    expect(listCalls).toBe(2);
  });

  it("agent adopt skips the refetch when the server answers with a conflict to resolve", async () => {
    fetchMock.mockImplementation(createRouteFetchMock([
      { match: "/adopt", response: { ...okJson({ conflict: "store-name-exists", slug: "a1" }), ok: false, status: 409 } },
    ]));
    const { result, queryClient } = setup(() => useAdoptAgentMutation());
    queryClient.setQueryData(agentsKeys.list(), agentList("disabled"));
    queryClient.setQueryData(skillsKeys.list(), { rows: [] });

    await act(async () => { await result.current.mutateAsync({ ref: "a1" }); });
    expect(queryClient.getQueryState(agentsKeys.list())?.isInvalidated).toBe(false);
    expect(queryClient.getQueryState(skillsKeys.list())?.isInvalidated).toBe(false);
  });

  it("slash-command update stays pending until the list refetch lands", async () => {
    let name = "old";
    fetchMock.mockImplementation(createRouteFetchMock([
      { match: (url, _i, init) => url.includes("/slash-commands/") && init?.method === "PUT", response: () => { name = "new"; return okJson({ ok: true }); } },
      { match: "/slash-commands", response: async () => { await new Promise((r) => setTimeout(r, 30)); return { commands: [{ name }], reviewCommands: [] }; } },
    ]));
    const { result, queryClient } = setup(() => ({ list: useSlashCommandsQuery(), update: useUpdateSlashCommandMutation() }));
    await waitFor(() => expect(result.current.list.data).toBeDefined());

    let atResolve: unknown;
    await act(async () => {
      await result.current.update.mutateAsync({ name: "old", body: {} as never });
      atResolve = queryClient.getQueryData([...slashCommandKeys.list(), false]);
    });
    expect((atResolve as { commands: { name: string }[] }).commands[0].name).toBe("new");
  });

  it("an agent skills change invalidates the skills list", async () => {
    fetchMock.mockImplementation(createRouteFetchMock([{ match: "/api/agents", response: okJson({ ref: "a1" }) }]));
    const { result, queryClient } = setup(() => useUpdateAgentMutation());
    queryClient.setQueryData(skillsKeys.list(), { rows: [] });
    queryClient.setQueryData(skillsKeys.detail("shared:s"), {});

    await act(async () => { await result.current.mutateAsync({ ref: "a1", request: {} as never }); });
    expect(queryClient.getQueryState(skillsKeys.list())?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(skillsKeys.detail("shared:s"))?.isInvalidated).toBe(true);
  });

  it("a failed agent delete still invalidates agents and skills", async () => {
    fetchMock.mockImplementation(createRouteFetchMock([{ match: "/api/agents", response: errorJson("nope", { status: 500 }) }]));
    const { result, queryClient } = setup(() => useDeleteAgentMutation());
    queryClient.setQueryData(skillsKeys.list(), { rows: [] });

    await act(async () => { await expect(result.current.mutateAsync("a1")).rejects.toThrow("nope"); });
    expect(queryClient.getQueryState(skillsKeys.list())?.isInvalidated).toBe(true);
  });

  it("a skill delete invalidates the agents list", async () => {
    fetchMock.mockImplementation(createRouteFetchMock([{ match: "/api/skills", response: okJson({ ok: true }) }]));
    const { result, queryClient } = setup(() => useDeleteSkillMutation());
    queryClient.setQueryData(agentsKeys.list(), agentList("enabled"));
    queryClient.setQueryData(agentsKeys.detail("a1"), {});

    await act(async () => { await result.current.mutateAsync({ skillRef: "shared:s" }); });
    expect(queryClient.getQueryState(agentsKeys.list())?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(agentsKeys.detail("a1"))?.isInvalidated).toBe(true);
  });

  it("a harness-support toggle invalidates hooks, permissions and slash-command queries", async () => {
    fetchMock.mockImplementation(createRouteFetchMock([{ match: "/support", response: okJson({ ok: true, enabled: true }) }]));
    const { result, queryClient } = setup(() => useHarnessSupportMutation());
    const keys = [hooksManagementKeys.inventory(), permissionsManagementKeys.inventory(), slashCommandKeys.list(), agentsKeys.list(), skillsKeys.list(), ["configs", "list"]];
    for (const key of keys) queryClient.setQueryData(key, {});

    await act(async () => { await result.current.mutateAsync({ harness: "claude", enabled: true }); });
    for (const key of keys) expect(queryClient.getQueryState(key)?.isInvalidated, key.join("/")).toBe(true);
  });
});
