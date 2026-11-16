import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { okJson } from "../../test/fetch";
import { ToastProvider } from "../Toast";
import { TagFilterBar } from "./TagFilterBar";

function Location() { return <div data-testid="location">{useLocation().search}</div>; }

afterEach(() => vi.unstubAllGlobals());

describe("rename tag", () => {
  it("warns on merge, updates the URL and refreshes queries", async () => {
    const fetchMock = vi.fn().mockResolvedValueOnce(okJson({ tags: ["DevOps", "Development"] }))
      .mockResolvedValueOnce(okJson({ assets_changed: 3 }));
    vi.stubGlobal("fetch", fetchMock);
    const client = new QueryClient();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    render(<QueryClientProvider client={client}><MemoryRouter initialEntries={["/?tag=devops&tag=Other&status=all"]}><ToastProvider>
      <TagFilterBar tags={[{ tag: "DevOps", count: 3, isStarred: false }]} selectedTags={["devops"]} onToggleTag={vi.fn()} />
      <Location />
    </ToastProvider></MemoryRouter></QueryClientProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Rename tag", description: "DevOps" }));
    expect(screen.getByRole("dialog", { name: "Rename tag" })).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    fireEvent.change(screen.getByLabelText("New name"), { target: { value: "Development" } });
    expect(screen.getByText(/will be merged/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Rename" }));
    await waitFor(() => expect(screen.getByTestId("location")).toHaveTextContent("tag=Development"));
    expect(screen.getByTestId("location")).toHaveTextContent("tag=Other");
    expect(screen.getByText("Renamed tag on 3 assets.")).toBeInTheDocument();
    expect(invalidate).toHaveBeenCalled();
  });
});
