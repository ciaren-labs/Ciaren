import { describe, expect, it } from "vitest";
import { clampNodeContextMenuPosition } from "../nodeContextMenuPosition";

describe("clampNodeContextMenuPosition", () => {
  it("leaves the position untouched when it fits comfortably in the viewport", () => {
    expect(clampNodeContextMenuPosition(100, 100, 1280, 800)).toEqual({ x: 100, y: 100 });
  });

  it("clamps x so the menu doesn't overflow the right edge", () => {
    // viewport 1280 wide, menu width 160 + 8px margin -> max x is 1112
    expect(clampNodeContextMenuPosition(1270, 100, 1280, 800)).toEqual({ x: 1112, y: 100 });
  });

  it("clamps y so the menu doesn't overflow the bottom edge", () => {
    // viewport 800 tall, menu height 116 + 8px margin -> max y is 676
    expect(clampNodeContextMenuPosition(100, 790, 1280, 800)).toEqual({ x: 100, y: 676 });
  });

  it("clamps both x and y when the click is in the bottom-right corner", () => {
    expect(clampNodeContextMenuPosition(1275, 795, 1280, 800)).toEqual({ x: 1112, y: 676 });
  });

  it("does not clamp near the top-left origin", () => {
    expect(clampNodeContextMenuPosition(0, 0, 1280, 800)).toEqual({ x: 0, y: 0 });
  });
});
