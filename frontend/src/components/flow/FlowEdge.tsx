import { useState } from "react";
import { BaseEdge, EdgeLabelRenderer, getSmoothStepPath, type EdgeProps } from "@xyflow/react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import { useFlowEditorStore } from "@/stores/flowEditorStore";

/**
 * Smoothstep edge (the app's only edge shape, set via FlowCanvas's
 * defaultEdgeOptions) with a small "x" button that appears at the midpoint on
 * hover, so a wire can be removed without first selecting it and reaching for
 * Backspace/Delete. EdgeLabelRenderer portals the button outside this edge's
 * own <g>, so CSS-only hover (a shared ancestor) can't drive its visibility —
 * local hover state, set from both the path and the button, does instead.
 */
export function FlowEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style,
  markerStart,
  markerEnd,
  selected,
  deletable,
}: EdgeProps) {
  const [hovered, setHovered] = useState(false);
  const removeEdge = useFlowEditorStore((s) => s.removeEdge);
  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const canDelete = deletable ?? true;
  const showButton = canDelete && (hovered || selected);

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={style}
        markerStart={markerStart}
        markerEnd={markerEnd}
        interactionWidth={20}
      />
      {canDelete && (
        <path
          d={edgePath}
          fill="none"
          strokeOpacity={0}
          strokeWidth={20}
          className="cursor-pointer"
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
        />
      )}
      {canDelete && (
        <EdgeLabelRenderer>
          <div
            className={cn(
              "nodrag nopan absolute transition-opacity duration-150",
              // Keyboard users can still Tab to the button while it's
              // hidden (opacity/pointer-events don't remove it from the tab
              // order) — focus-within reveals it, mirroring FlowNode's
              // hover toolbar, so it's never invisibly activatable.
              "focus-within:pointer-events-auto focus-within:opacity-100",
              // The EdgeLabelRenderer container is `pointer-events: none` so it
              // doesn't block canvas panning where there's no label — this
              // child must opt back in explicitly or the button is unclickable.
              showButton ? "pointer-events-auto opacity-100" : "pointer-events-none opacity-0",
            )}
            style={{
              transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
            }}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
          >
            <button
              type="button"
              title="Delete edge"
              aria-label="Delete edge"
              onClick={(e) => {
                e.stopPropagation();
                removeEdge(id);
              }}
              className="flex h-4 w-4 items-center justify-center rounded-full border border-border bg-card text-slate-500 shadow-sm hover:bg-destructive/10 hover:text-destructive"
            >
              <X className="h-2.5 w-2.5" />
            </button>
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
