import { describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CollapsibleSection } from "../CollapsibleSection";

describe("CollapsibleSection", () => {
  it("renders the title, count, and children open by default", () => {
    render(
      <CollapsibleSection title="Sales" count={3}>
        <p>body content</p>
      </CollapsibleSection>,
    );
    expect(screen.getByText("Sales")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("body content")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Sales/ })).toHaveAttribute("aria-expanded", "true");
  });

  it("toggles its children when the header is clicked", () => {
    render(
      <CollapsibleSection title="Sales">
        <p>body content</p>
      </CollapsibleSection>,
    );
    const header = screen.getByRole("button");
    fireEvent.click(header);
    expect(screen.queryByText("body content")).not.toBeInTheDocument();
    expect(header).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(header);
    expect(screen.getByText("body content")).toBeInTheDocument();
    expect(header).toHaveAttribute("aria-expanded", "true");
  });

  it("toggles with Enter and Space and keeps aria-expanded in sync", async () => {
    const user = userEvent.setup();
    render(
      <CollapsibleSection title="Sales">
        <p>body content</p>
      </CollapsibleSection>,
    );
    const header = screen.getByRole("button");
    await user.tab();
    expect(header).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(screen.queryByText("body content")).not.toBeInTheDocument();
    expect(header).toHaveAttribute("aria-expanded", "false");
    await user.keyboard(" ");
    expect(screen.getByText("body content")).toBeInTheDocument();
    expect(header).toHaveAttribute("aria-expanded", "true");
  });

  it("can start collapsed", () => {
    render(
      <CollapsibleSection title="Sales" defaultOpen={false}>
        <p>body content</p>
      </CollapsibleSection>,
    );
    expect(screen.queryByText("body content")).not.toBeInTheDocument();
    expect(screen.getByRole("button")).toHaveAttribute("aria-expanded", "false");
  });
});
