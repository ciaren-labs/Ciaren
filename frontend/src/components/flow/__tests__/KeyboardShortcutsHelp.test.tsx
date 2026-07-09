import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { KeyboardShortcutsHelp } from "../KeyboardShortcutsHelp";

describe("KeyboardShortcutsHelp", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("is closed by default", () => {
    render(<KeyboardShortcutsHelp />);

    expect(screen.queryByText("Keyboard shortcuts")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Keyboard shortcuts" })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("opens the shortcut list on click and lists the documented shortcuts", async () => {
    const user = userEvent.setup();
    render(<KeyboardShortcutsHelp />);

    await user.click(screen.getByRole("button", { name: "Keyboard shortcuts" }));

    expect(screen.getByText("Undo")).toBeInTheDocument();
    expect(screen.getByText("Ctrl/Cmd+Z")).toBeInTheDocument();
    expect(screen.getByText("Delete selected node or edge")).toBeInTheDocument();
    expect(screen.getByText("Open its context menu")).toBeInTheDocument();
  });

  it("toggles closed when the trigger is clicked again", async () => {
    const user = userEvent.setup();
    render(<KeyboardShortcutsHelp />);
    const trigger = screen.getByRole("button", { name: "Keyboard shortcuts" });

    await user.click(trigger);
    expect(screen.getByText("Keyboard shortcuts")).toBeInTheDocument();

    await user.click(trigger);
    expect(screen.queryByText("Keyboard shortcuts")).not.toBeInTheDocument();
  });

  it("closes on click-away", async () => {
    const user = userEvent.setup();
    render(
      <div>
        <div data-testid="outside">outside</div>
        <KeyboardShortcutsHelp />
      </div>,
    );

    await user.click(screen.getByRole("button", { name: "Keyboard shortcuts" }));
    expect(screen.getByText("Keyboard shortcuts")).toBeInTheDocument();

    // The click-away overlay covers the viewport, so clicking "outside" still
    // lands on the overlay (as it would in the real, fixed-position layout).
    await user.click(document.querySelector(".fixed.inset-0")!);
    expect(screen.queryByText("Keyboard shortcuts")).not.toBeInTheDocument();
  });

  it("closes on Escape", async () => {
    const user = userEvent.setup();
    render(<KeyboardShortcutsHelp />);

    await user.click(screen.getByRole("button", { name: "Keyboard shortcuts" }));
    expect(screen.getByText("Keyboard shortcuts")).toBeInTheDocument();

    await user.keyboard("{Escape}");
    expect(screen.queryByText("Keyboard shortcuts")).not.toBeInTheDocument();
  });

  it("closes on window resize rather than repositioning", async () => {
    const user = userEvent.setup();
    render(<KeyboardShortcutsHelp />);

    await user.click(screen.getByRole("button", { name: "Keyboard shortcuts" }));
    expect(screen.getByText("Keyboard shortcuts")).toBeInTheDocument();

    fireEvent(window, new Event("resize"));
    expect(screen.queryByText("Keyboard shortcuts")).not.toBeInTheDocument();
  });

  it("renders the panel as a direct child of document.body (a real portal), not inline in the render tree", async () => {
    const user = userEvent.setup();
    const { container } = render(<KeyboardShortcutsHelp />);

    await user.click(screen.getByRole("button", { name: "Keyboard shortcuts" }));

    const panel = screen.getByText("Keyboard shortcuts").closest(".fixed");
    expect(panel).not.toBeNull();
    // If this were rendered inline (portal silently no-op'd), it would be a
    // descendant of the test's own render container.
    expect(container.contains(panel)).toBe(false);
    expect(document.body.contains(panel)).toBe(true);
  });

  it("positions the panel from the trigger's measured bounding rect", async () => {
    const user = userEvent.setup();
    const originalInnerWidth = window.innerWidth;
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 1000 });
    render(<KeyboardShortcutsHelp />);
    const trigger = screen.getByRole("button", { name: "Keyboard shortcuts" });
    vi.spyOn(trigger, "getBoundingClientRect").mockReturnValue({
      top: 10,
      bottom: 40,
      left: 900,
      right: 940,
      width: 40,
      height: 30,
      x: 900,
      y: 10,
      toJSON: () => {},
    });

    await user.click(trigger);

    const panel = screen.getByText("Keyboard shortcuts").closest(".fixed") as HTMLElement;
    // top = rect.bottom (40) + 4; right = innerWidth (1000) - rect.right (940)
    expect(panel.style.top).toBe("44px");
    expect(panel.style.right).toBe("60px");

    Object.defineProperty(window, "innerWidth", { configurable: true, value: originalInnerWidth });
  });
});
