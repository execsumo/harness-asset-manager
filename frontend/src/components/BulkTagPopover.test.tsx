import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { BulkTagPopover } from "./BulkTagPopover";

it("finds case-folded suggestions and stages Unicode tags without duplicates", async () => {
  const onApply = vi.fn().mockResolvedValue(undefined);
  const emoji = "😀".repeat(40);
  render(<BulkTagPopover knownTags={["Straße", emoji]} onApply={onApply} />);
  fireEvent.click(screen.getByRole("button", { name: "Tag selected" }));
  const input = screen.getByRole("textbox", { name: "New tag name" });
  fireEvent.change(input, { target: { value: "STRASS" } });
  fireEvent.mouseDown(screen.getByRole("option", { name: "Straße" }));
  fireEvent.change(input, { target: { value: "STRASSE" } });
  fireEvent.keyDown(input, { key: "Enter" });
  expect(screen.getByText("Tag already added")).toBeInTheDocument();
  fireEvent.change(input, { target: { value: "" } });
  fireEvent.mouseDown(screen.getByRole("option", { name: emoji }));
  fireEvent.click(screen.getByRole("button", { name: "Apply" }));
  await waitFor(() => expect(onApply).toHaveBeenCalledWith(["Straße", emoji]));
});
