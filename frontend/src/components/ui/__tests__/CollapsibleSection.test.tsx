import { describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
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
  });

  it("toggles its children when the header is clicked", () => {
    render(
      <CollapsibleSection title="Sales">
        <p>body content</p>
      </CollapsibleSection>,
    );
    fireEvent.click(screen.getByRole("button"));
    expect(screen.queryByText("body content")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("body content")).toBeInTheDocument();
  });

  it("can start collapsed", () => {
    render(
      <CollapsibleSection title="Sales" defaultOpen={false}>
        <p>body content</p>
      </CollapsibleSection>,
    );
    expect(screen.queryByText("body content")).not.toBeInTheDocument();
  });
});
