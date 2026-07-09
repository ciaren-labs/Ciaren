import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SearchInput } from "../FilterBar";

function ControlledSearchInput({ initial = "" }: { initial?: string }) {
  const [value, setValue] = useState(initial);
  return <SearchInput value={value} onChange={setValue} />;
}

describe("SearchInput", () => {
  it("has no clear button when empty", () => {
    render(<SearchInput value="" onChange={() => {}} />);
    expect(screen.queryByRole("button", { name: "Clear search" })).not.toBeInTheDocument();
  });

  it("shows a clear button once text is typed, which empties the value", async () => {
    const user = userEvent.setup();
    render(<ControlledSearchInput />);

    const input = screen.getByPlaceholderText("Search…");
    await user.type(input, "invoices");
    expect(input).toHaveValue("invoices");

    const clearBtn = screen.getByRole("button", { name: "Clear search" });
    await user.click(clearBtn);

    expect(input).toHaveValue("");
    expect(screen.queryByRole("button", { name: "Clear search" })).not.toBeInTheDocument();
  });

  it("clears pre-existing (non-empty initial) values too", async () => {
    const user = userEvent.setup();
    render(<ControlledSearchInput initial="pre-filled" />);

    expect(screen.getByPlaceholderText("Search…")).toHaveValue("pre-filled");
    await user.click(screen.getByRole("button", { name: "Clear search" }));
    expect(screen.getByPlaceholderText("Search…")).toHaveValue("");
  });

  it("returns focus to the input after clearing, instead of dropping it to the body", async () => {
    const user = userEvent.setup();
    render(<ControlledSearchInput />);

    const input = screen.getByPlaceholderText("Search…");
    await user.type(input, "invoices");
    await user.click(screen.getByRole("button", { name: "Clear search" }));

    expect(input).toHaveFocus();
  });

  it("does not submit an enclosing form when the clear button is clicked", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn((e: React.FormEvent) => e.preventDefault());
    function Wrapper() {
      const [value, setValue] = useState("query");
      return (
        <form onSubmit={onSubmit}>
          <SearchInput value={value} onChange={setValue} />
        </form>
      );
    }
    render(<Wrapper />);

    await user.click(screen.getByRole("button", { name: "Clear search" }));
    expect(onSubmit).not.toHaveBeenCalled();
  });
});
