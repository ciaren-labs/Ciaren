import { MousePointerClick } from "lucide-react";

/**
 * Onboarding hint shown centered on the canvas while a flow has zero nodes.
 * Purely visual — the wrapper is pointer-events-none so it never intercepts
 * the palette's drag-and-drop or the canvas's own click/pan handling.
 */
export function EmptyCanvasHint() {
  return (
    <div className="pointer-events-none absolute inset-0 z-10 flex items-center justify-center">
      <div className="max-w-[15rem] rounded-lg border border-dashed border-border bg-card/70 px-5 py-4 text-center">
        <MousePointerClick className="mx-auto mb-2 h-5 w-5 text-muted-foreground" />
        <p className="text-sm font-medium text-foreground">Start building your flow</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Drag an <strong>Input</strong> node from the panel on the left onto the canvas.
        </p>
      </div>
    </div>
  );
}
