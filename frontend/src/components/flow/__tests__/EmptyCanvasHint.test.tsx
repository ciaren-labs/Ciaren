import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { EmptyCanvasHint } from "../EmptyCanvasHint";

describe("EmptyCanvasHint", () => {
  it("renders the onboarding copy pointing at the node palette", () => {
    render(<EmptyCanvasHint />);

    expect(screen.getByText("Start building your flow")).toBeInTheDocument();
    expect(screen.getByText("Input")).toBeInTheDocument();
  });

  it("never intercepts pointer events (drag-and-drop, canvas pan/click)", () => {
    const { container } = render(<EmptyCanvasHint />);
    const wrapper = container.firstElementChild as HTMLElement;

    expect(wrapper.className).toContain("pointer-events-none");
  });
});
