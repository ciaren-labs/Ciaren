import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { NodeContextMenu } from "../NodeContextMenu";

describe("NodeContextMenu", () => {
  function renderMenu(overrides: Partial<React.ComponentProps<typeof NodeContextMenu>> = {}) {
    const onEdit = vi.fn();
    const onDuplicate = vi.fn();
    const onDelete = vi.fn();
    const onClose = vi.fn();
    const utils = render(
      <NodeContextMenu
        x={10}
        y={20}
        onEdit={onEdit}
        onDuplicate={onDuplicate}
        onDelete={onDelete}
        onClose={onClose}
        {...overrides}
      />,
    );
    return { ...utils, onEdit, onDuplicate, onDelete, onClose };
  }

  it("calls onEdit, onDuplicate, onDelete for their respective items", async () => {
    const user = userEvent.setup();
    const { onEdit, onDuplicate, onDelete } = renderMenu();

    await user.click(screen.getByRole("button", { name: "Edit" }));
    await user.click(screen.getByRole("button", { name: "Duplicate" }));
    await user.click(screen.getByRole("button", { name: "Delete" }));

    expect(onEdit).toHaveBeenCalledTimes(1);
    expect(onDuplicate).toHaveBeenCalledTimes(1);
    expect(onDelete).toHaveBeenCalledTimes(1);
  });

  it("calls onClose when clicking outside the menu (the click-away overlay)", async () => {
    const user = userEvent.setup();
    const { onClose, container } = renderMenu();
    const overlay = container.querySelector(".fixed.inset-0") as HTMLElement;

    await user.click(overlay);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("calls onClose (and prevents the native menu) on right-clicking the overlay", () => {
    const { onClose, container } = renderMenu();
    const overlay = container.querySelector(".fixed.inset-0") as HTMLElement;
    const event = new MouseEvent("contextmenu", { bubbles: true, cancelable: true });
    const preventDefaultSpy = vi.spyOn(event, "preventDefault");

    overlay.dispatchEvent(event);

    expect(preventDefaultSpy).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("positions the menu at the given x/y", () => {
    const { container } = renderMenu({ x: 42, y: 99 });
    const menu = container.querySelector(".z-50") as HTMLElement;

    expect(menu.style.left).toBe("42px");
    expect(menu.style.top).toBe("99px");
  });
});
