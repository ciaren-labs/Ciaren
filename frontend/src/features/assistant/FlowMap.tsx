import { nodeMark } from "./nodePresentation";
import type { GraphJson, GraphNode } from "@/features/flows/types";
import { getNodeTypeDef } from "@/features/flows/editor/nodeCatalog";
import type { Delta } from "./api";

const captions: Record<string, string> = {
  fileInput: "Input",
  trainTestSplit: "Split",
  mlTrainRegressor: "Train",
  mlPredict: "Predict",
  mlEvaluate: "Evaluate",
  fileOutput: "Output",
  join: "Join",
  conditionalColumn: "Flag",
  limitRows: "Limit",
  sortRows: "Sort",
  filterRows: "Filter",
  removeDuplicates: "Deduplicate",
  selectColumns: "Select",
  dropColumns: "Drop columns",
  dropNulls: "Drop nulls",
};

/**
 * A compact wiring diagram of the changed nodes and their immediate neighbours.
 * Removed nodes keep their old connections, drawn dashed, so the map shows what goes away.
 */
export function FlowMap({ base, delta }: { base: GraphJson; delta: Delta }) {
  const removed = new Set(delta.removed);
  const changed = new Set([
    ...[...delta.added, ...delta.changed].map((n) => n.id),
    ...removed,
  ]);
  const edges = [
    ...base.edges.filter((e) => !delta.disconnected.includes(e.id)),
    ...delta.connected,
  ].filter((e) => changed.has(e.source) || changed.has(e.target));
  const dropped = (e: { source: string; target: string }) =>
    removed.has(e.source) || removed.has(e.target);
  const visible = new Set([
    ...changed,
    ...edges.flatMap((e) => [e.source, e.target]),
  ]);
  const nodes = [...base.nodes, ...delta.added].filter((n) =>
    visible.has(n.id),
  );
  if (!nodes.length || nodes.length > 12) return null;
  const levels = new Map<string, number>();
  for (let pass = 0; pass < nodes.length; pass++) {
    for (const n of nodes) {
      const incoming = edges.filter((e) => e.target === n.id);
      if (!levels.has(n.id) && incoming.every((e) => levels.has(e.source))) {
        levels.set(
          n.id,
          incoming.length
            ? Math.max(...incoming.map((e) => levels.get(e.source)!)) + 1
            : 0,
        );
      }
    }
  }
  if (levels.size !== nodes.length) return null;
  const columns: GraphNode[][] = [];
  for (const n of nodes) (columns[levels.get(n.id)!] ??= []).push(n);
  const rows = Math.max(...columns.map((c) => c.length));
  // Drawn at 1:1 so captions keep their 11px size; wide maps scroll instead of shrinking.
  const height = rows * 64 + 8;
  const width = columns.length * 88;
  const coords = new Map(
    columns.flatMap((col, i) =>
      col.map(
        (n, j) =>
          [
            n.id,
            {
              x: 44 + i * 88,
              y: height / 2 - 8 + (j - (col.length - 1) / 2) * 64,
            },
          ] as const,
      ),
    ),
  );
  return (
    <div
      aria-hidden="true"
      className="assistant-map overflow-x-auto rounded-xl border border-border px-3 py-3"
    >
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width={width}
        height={height}
        className="mx-auto block shrink-0"
        fill="none"
      >
        {edges.map((e) => {
          const a = coords.get(e.source)!,
            b = coords.get(e.target)!,
            mid = (a.x + b.x) / 2;
          return (
            <path
              key={e.id}
              d={`M${a.x + 15} ${a.y} C${mid} ${a.y} ${mid} ${b.y} ${b.x - 15} ${b.y}`}
              stroke={dropped(e) ? "hsl(var(--destructive) / .6)" : "hsl(var(--primary) / .52)"}
              strokeWidth="2.2"
              strokeDasharray={dropped(e) ? "4 3" : undefined}
            />
          );
        })}
        {nodes.map((n) => {
          const { x, y } = coords.get(n.id)!,
            { Icon, color } = nodeMark(n.type);
          const side = edges.find(
            (e) =>
              e.source === n.id &&
              (e.targetHandle === "left" || e.targetHandle === "right"),
          )?.targetHandle;
          const caption =
            n.type === "fileInput" && (side === "left" || side === "right")
              ? side === "left"
                ? "Left input"
                : "Right input"
              : (captions[n.type] ?? getNodeTypeDef(n.type)?.label);
          return (
            <g
              key={n.id}
              transform={`translate(${x},${y})`}
              className={removed.has(n.id) ? "text-destructive" : color}
              data-removed={removed.has(n.id) ? n.id : undefined}
              opacity={removed.has(n.id) ? 0.7 : undefined}
            >
              {delta.changed.some((existing) => existing.id === n.id) && (
                <rect
                  x="-20"
                  y="-20"
                  width="40"
                  height="40"
                  rx="11"
                  fill="hsl(var(--primary) / .16)"
                />
              )}
              <rect
                x="-16"
                y="-16"
                width="32"
                height="32"
                rx="8"
                fill="hsl(var(--card))"
                stroke="currentColor"
                strokeWidth={changed.has(n.id) ? 2 : 1}
                strokeDasharray={removed.has(n.id) ? "4 3" : undefined}
              />
              <Icon x="-9" y="-9" width="18" height="18" strokeWidth="1.9" />
              <text
                x="0"
                y="31"
                textAnchor="middle"
                fill="hsl(var(--foreground))"
                fontSize="11"
                fontWeight="600"
              >
                {caption}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
