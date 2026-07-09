const MENU_WIDTH = 160;
const MENU_HEIGHT = 116;
const VIEWPORT_MARGIN = 8;

/**
 * Clamp a context menu's top-left corner so it never overflows off the
 * right/bottom edge of the viewport. Uses a fixed estimate of the menu's own
 * size rather than a measured one — its contents (three fixed-height rows)
 * don't vary with the node it was opened for, so this is exact, not a guess.
 */
export function clampNodeContextMenuPosition(
  x: number,
  y: number,
  viewportWidth: number,
  viewportHeight: number,
): { x: number; y: number } {
  return {
    x: Math.min(x, viewportWidth - MENU_WIDTH - VIEWPORT_MARGIN),
    y: Math.min(y, viewportHeight - MENU_HEIGHT - VIEWPORT_MARGIN),
  };
}
