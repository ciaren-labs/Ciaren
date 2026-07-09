import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Keyboard } from "lucide-react";

/** Static reference list — kept next to the handlers it documents so the two
 *  are easy to keep in sync: copy/paste/duplicate in FlowCanvas.tsx, undo/redo
 *  in FlowEditorPage.tsx, delete via React Flow's default deleteKeyCode, and
 *  the right-click menu in NodeContextMenu.tsx. */
const SHORTCUTS: { keys: string; action: string }[] = [
  { keys: "Ctrl/Cmd+Z", action: "Undo" },
  { keys: "Ctrl/Cmd+Shift+Z", action: "Redo" },
  { keys: "Ctrl+Y", action: "Redo" },
  { keys: "Delete / Backspace", action: "Delete selected node or edge" },
  { keys: "Ctrl/Cmd+C", action: "Copy selected nodes" },
  { keys: "Ctrl/Cmd+V", action: "Paste" },
  { keys: "Ctrl/Cmd+D", action: "Duplicate selection" },
  { keys: "Right-click a node", action: "Open its context menu" },
];

/**
 * A small "?"-style affordance that lists the canvas's keyboard shortcuts on
 * click — the shortcuts themselves already work today, they just have no
 * in-app surface where a user would discover them.
 *
 * Rendered through a portal into `document.body` with a position computed
 * from the trigger's own bounding rect, rather than a CSS `absolute` child
 * positioned via `top-full`/`right-0`. This button lives inside
 * FlowEditorPage's in-page toolbar, which sits in the same stacking context
 * as FlowCanvas's own `position: relative` canvas-surface div (a sibling
 * later in that page's DOM) — a plain nested `z-index` there only ranks
 * *within* whichever of those establishes a context first, so it can silently
 * lose to the canvas regardless of how high the number is. A portal
 * sidesteps that stacking-order question entirely by rendering as a direct
 * child of `<body>` instead. (The app's `<header>`, elsewhere, has this same
 * `position: relative` + explicit `z-index` shape — see AppHeader.tsx's
 * timezone `SearchableSelect` dropdown for another place this class of bug
 * can surface.)
 */
export function KeyboardShortcutsHelp() {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<{ top: number; right: number } | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  const toggle = () => {
    if (!open && triggerRef.current) {
      const rect = triggerRef.current.getBoundingClientRect();
      setPosition({ top: rect.bottom + 4, right: window.innerWidth - rect.right });
    }
    setOpen((o) => !o);
  };
  const close = () => setOpen(false);

  // Close rather than reposition on resize/Escape: the trigger's rect (and
  // so the popover's position) is only measured once, at open time, and this
  // is read-only reference content — not worth a resize/scroll listener to
  // keep a stale position pinned to a moving trigger.
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") close();
    };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("resize", close);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("resize", close);
    };
  }, [open]);

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={toggle}
        title="Keyboard shortcuts"
        aria-label="Keyboard shortcuts"
        aria-expanded={open}
        className="flex h-8 w-8 items-center justify-center rounded-md border border-input text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
      >
        <Keyboard className="h-4 w-4" />
      </button>
      {open &&
        position &&
        createPortal(
          <>
            {/* click-away — z-index above Toaster's z-[100] (App.tsx renders
                <Toaster/> inline, not portaled, so it also participates in
                the root stacking context) so an open popover can't silently
                swallow a click meant for a toast's action underneath it. */}
            <div className="fixed inset-0 z-[110]" onClick={close} />
            <div
              className="fixed z-[111] w-72 overflow-hidden rounded-lg border border-border bg-background py-2 shadow-md"
              style={{ top: position.top, right: position.right }}
            >
              <p className="px-3 pb-1.5 text-xs font-semibold text-foreground">Keyboard shortcuts</p>
              <ul>
                {SHORTCUTS.map((s) => (
                  <li
                    key={`${s.keys}-${s.action}`}
                    className="flex items-center justify-between gap-3 px-3 py-1 text-xs"
                  >
                    <span className="text-muted-foreground">{s.action}</span>
                    <kbd className="whitespace-nowrap rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px]">
                      {s.keys}
                    </kbd>
                  </li>
                ))}
              </ul>
            </div>
          </>,
          document.body,
        )}
    </>
  );
}
