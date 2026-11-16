import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useSetAgentTagsMutation } from "../../features/agents/api/queries";
import { useSetConfigTagsMutation } from "../../features/configs/api/queries";
import { useSetHookTagsMutation } from "../../features/hooks/api/management-queries";
import { useSetMcpServerTagsMutation } from "../../features/mcp/api/management-queries";
import { useSetPermissionTagsMutation } from "../../features/permissions/api/management-queries";
import { useSetSkillTagsMutation } from "../../features/skills/api/queries";
import { useSetSlashCommandTagsMutation } from "../../features/slash-commands/api/queries";

const cases = [
  { name: "agents", hook: useSetAgentTagsMutation, key: ["agents", "list", true], field: "entries", id: "ref", args: { ref: "a", tags: ["starred"] } },
  { name: "hooks", hook: useSetHookTagsMutation, key: ["hooks", "inventory"], field: "entries", id: "id", args: { id: "a", tags: ["starred"] } },
  { name: "permissions", hook: useSetPermissionTagsMutation, key: ["permissions", "inventory"], field: "entries", id: "id", args: { id: "a", tags: ["starred"] } },
  { name: "mcp", hook: useSetMcpServerTagsMutation, key: ["mcp", "inventory", true], field: "entries", id: "name", args: { name: "a", tags: ["starred"] } },
  { name: "skills", hook: useSetSkillTagsMutation, key: ["skills", "list", "with-archived"], field: "rows", id: "skillRef", args: { skillRef: "a", tags: ["starred"] } },
  { name: "slash commands", hook: useSetSlashCommandTagsMutation, key: ["slash-commands", "list", true], field: "commands", id: "name", args: { name: "a", tags: ["starred"] } },
] as const;

afterEach(() => vi.unstubAllGlobals());

describe("tag mutations", () => {
  it.each(cases)("updates $name before the request completes and restores on failure", async ({ hook, key, field, id, args }) => {
    const client = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
    const original = { [field]: [{ [id]: "a", tags: [] }] };
    client.setQueryData(key, original);
    let reject!: (error: Error) => void;
    vi.stubGlobal("fetch", vi.fn(() => new Promise((_resolve, fail) => { reject = fail; })));
    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
    const { result } = renderHook(() => hook(), { wrapper });
    act(() => { (result.current.mutate as unknown as (value: typeof args) => void)(args); });
    await waitFor(() => expect(client.getQueryData(key)).toEqual({ [field]: [{ [id]: "a", tags: ["starred"] }] }));
    act(() => reject(new Error("offline")));
    await waitFor(() => expect(client.getQueryData(key)).toEqual(original));
  });

  it("updates config tags before the request completes", async () => {
    const client = new QueryClient();
    client.setQueryData(["configs", "list"], { a: { tags: [] } });
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {})));
    const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>;
    const { result } = renderHook(() => useSetConfigTagsMutation(), { wrapper });
    act(() => result.current.mutate({ harness: "a", tags: ["starred"] }));
    await waitFor(() => expect(client.getQueryData(["configs", "list"])).toEqual({ a: { tags: ["starred"] } }));
  });
});
