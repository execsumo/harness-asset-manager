import { QueryClient, QueryClientProvider, useMutation, useQuery } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it } from "vitest";

import { settleInvalidate } from "./settle";

function deferred<T = void>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function setup(queryFn: () => Promise<string>, mutationFn: () => Promise<string>, extra: Parameters<typeof settleInvalidate>[1][] = []) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  const view = renderHook(
    () => ({
      query: useQuery({ queryKey: ["demo"], queryFn }),
      mutation: useMutation({
        mutationFn,
        onSettled: settleInvalidate(queryClient, ["demo"], ...extra),
      }),
    }),
    { wrapper },
  );
  return { queryClient, ...view };
}

describe("settleInvalidate", () => {
  it("keeps the mutation pending until the refetch resolves", async () => {
    let value = "old";
    const gate = deferred();
    let calls = 0;
    const { result, queryClient } = setup(
      async () => {
        calls += 1;
        if (calls > 1) await gate.promise;
        return value;
      },
      async () => {
        value = "new";
        return "ok";
      },
    );
    await waitFor(() => expect(result.current.query.data).toBe("old"));

    let settled = false;
    let cacheAtResolve: unknown;
    const run = result.current.mutation.mutateAsync().then(() => {
      settled = true;
      cacheAtResolve = queryClient.getQueryData(["demo"]);
    });
    await waitFor(() => expect(calls).toBe(2));
    await Promise.resolve();
    expect(settled).toBe(false);

    await act(async () => { gate.resolve(); await run; });
    expect(settled).toBe(true);
    expect(cacheAtResolve).toBe("new");
  });

  it("invalidates when the mutation fails and keeps the original error", async () => {
    let calls = 0;
    const failure = new Error("boom");
    const { result } = setup(
      async () => `v${++calls}`,
      async () => { throw failure; },
      [async () => { throw new Error("refetch failed"); }],
    );
    await waitFor(() => expect(result.current.query.data).toBe("v1"));

    await act(async () => {
      await expect(result.current.mutation.mutateAsync()).rejects.toBe(failure);
    });
    expect(calls).toBe(2);
  });

  it("does not reject a successful mutation when a refetch rejects", async () => {
    const { result } = setup(
      async () => "x",
      async () => "done",
      [async () => { throw new Error("refetch failed"); }, () => { throw new Error("sync failure"); }],
    );
    await waitFor(() => expect(result.current.query.data).toBe("x"));

    await act(async () => {
      await expect(result.current.mutation.mutateAsync()).resolves.toBe("done");
    });
  });

  it("waits for the newer refetch when an overlapping settle cancels its own", async () => {
    let server = "v0";
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const observer = renderHook(
      () => useQuery({
        queryKey: ["demo"],
        queryFn: async () => {
          const seen = server;
          await new Promise((resolve) => setTimeout(resolve, 40));
          return seen;
        },
      }),
      { wrapper: ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider> },
    );
    await waitFor(() => expect(observer.result.current.data).toBe("v0"));

    // Each later mutation settles mid-flight and cancels the previous refetch.
    const cacheWhenResolved: unknown[] = [];
    const settles: Promise<void>[] = [];
    for (const version of ["v1", "v2", "v3"]) {
      server = version;
      settles.push(settleInvalidate(queryClient, ["demo"])().then(() => { cacheWhenResolved.push(queryClient.getQueryData(["demo"])); }));
      await new Promise((resolve) => setTimeout(resolve, 15));
    }
    await act(async () => { await Promise.all(settles); });

    expect(cacheWhenResolved).toEqual(["v3", "v3", "v3"]);
  });

  it("does not wait for an unrelated query that starts fetching in the same window", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const slow = deferred<string>();
    const view = renderHook(
      ({ showSlow }: { showSlow: boolean }) => ({
        demo: useQuery({ queryKey: ["demo"], queryFn: async () => "fresh" }),
        slow: useQuery({ queryKey: ["unrelated"], queryFn: () => slow.promise, enabled: showSlow }),
      }),
      {
        initialProps: { showSlow: false },
        wrapper: ({ children }: { children: ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>,
      },
    );
    await waitFor(() => expect(view.result.current.demo.data).toBe("fresh"));

    let settled = false;
    const settle = settleInvalidate(queryClient, ["demo"])().then(() => { settled = true; });
    // The unrelated query starts while the settle is in flight and never finishes.
    view.rerender({ showSlow: true });
    await act(async () => { await settle; });

    expect(settled).toBe(true);
    expect(queryClient.getQueryState(["unrelated"])?.fetchStatus).toBe("fetching");
    slow.resolve("done");
  });

  it("accepts family invalidators next to plain keys", async () => {
    const calls: string[] = [];
    const queryClient = new QueryClient();
    await settleInvalidate(queryClient, async (qc) => { calls.push(qc === queryClient ? "family" : "other"); })();
    expect(calls).toEqual(["family"]);
  });
});
