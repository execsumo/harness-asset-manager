import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SkillTagFilterBar } from "./SkillTagFilterBar";

describe("SkillTagFilterBar", () => {
  const sampleTags = [
    { tag: "starred", count: 3, isStarred: true },
    { tag: "core", count: 5, isStarred: false },
    { tag: "devops", count: 2, isStarred: false },
  ];

  it("renders pinned star chip and regular tag chips with counts", () => {
    render(
      <SkillTagFilterBar
        tags={sampleTags}
        selectedTags={[]}
        onToggleTag={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: /starred/i })).toHaveTextContent("starred3");
    expect(screen.getByRole("button", { name: /^core/i })).toHaveTextContent("core5");
    expect(screen.getByRole("button", { name: /^devops/i })).toHaveTextContent("devops2");
  });

  it("calls onToggleTag when a tag chip is clicked", () => {
    const onToggleTag = vi.fn();
    render(
      <SkillTagFilterBar
        tags={sampleTags}
        selectedTags={["core"]}
        onToggleTag={onToggleTag}
      />,
    );

    const starredChip = screen.getByRole("button", { name: /starred/i });
    fireEvent.click(starredChip);
    expect(onToggleTag).toHaveBeenCalledWith("starred");

    const devopsChip = screen.getByRole("button", { name: /^devops/i });
    fireEvent.click(devopsChip);
    expect(onToggleTag).toHaveBeenCalledWith("devops");
  });

  it("renders active state on selected chips and renders clear tags button", () => {
    const onClearTags = vi.fn();
    render(
      <SkillTagFilterBar
        tags={sampleTags}
        selectedTags={["core", "starred"]}
        onToggleTag={vi.fn()}
        onClearTags={onClearTags}
      />,
    );

    const coreChip = screen.getByRole("button", { name: /^core/i });
    expect(coreChip).toHaveAttribute("aria-pressed", "true");

    const clearBtn = screen.getByRole("button", { name: /clear tag filters/i });
    expect(clearBtn).toBeInTheDocument();
    fireEvent.click(clearBtn);
    expect(onClearTags).toHaveBeenCalledTimes(1);
  });
});
