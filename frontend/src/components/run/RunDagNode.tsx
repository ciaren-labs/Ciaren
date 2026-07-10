import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import { AlertCircle, CheckCircle2, MinusCircle } from "lucide-react";
import { getNodeTypeDef, getOutputHandles } from "@/lib/nodeCatalog";
import { getNodeIcon } from "@/lib/nodeVisuals";
import type { NodeResultStatus } from "@/features/runs/types";
import { formatCount } from "@/lib/format";
import { cn } from "@/lib/utils";

function isModelHandle(handle: string): boolean {
  return handle === "model";
}

function topPct(idx: number, count: number): string {
  return count === 1 ? "50%" : `${((idx + 1) / (count + 1)) * 100}%`;
}

export interface RunDagNodeData {
  label: string;
  nodeType: string;
  status: NodeResultStatus | "unknown";
  rows: number | null;
  [key: string]: unknown;
}

export type RunDagNodeType = Node<RunDagNodeData>;

const STATUS_RING: Record<string, string> = {
  success: "ring-2 ring-emerald-400",
  failed: "ring-2 ring-red-400",
  skipped: "ring-1 ring-border",
  unknown: "ring-2 ring-blue-400",
};

const STATUS_ICON: Record<string, { icon: typeof CheckCircle2; className: string } | null> = {
  success: { icon: CheckCircle2, className: "text-emerald-500" },
  failed: { icon: AlertCircle, className: "text-red-500" },
  skipped: { icon: MinusCircle, className: "text-muted-foreground" },
  unknown: null,
};

/** Read-only node for the run DAG — same visual as the editor node, with a
 * coloured ring indicating status: green = success, red = failed, blue = pending. */
export function RunDagNode({ data, selected }: NodeProps<RunDagNodeType>) {
  const def = getNodeTypeDef(data.nodeType);
  // Mirror the editor node's handles exactly (incl. optional + multi-output
  // handles like model/train/test) so the saved edges' sourceHandle/targetHandle
  // attach — otherwise multi-handle ML nodes render disconnected.
  const inputHandles = [
    ...(def?.inputHandles ?? ["in"]),
    ...(def?.optionalInputHandles ?? []),
  ];
  const outputHandles = def ? getOutputHandles(def) : ["out"];
  const Icon = getNodeIcon(data.nodeType);
  const statusIcon = STATUS_ICON[data.status];

  return (
    <div
      className={cn(
        "min-w-[168px] rounded-lg border border-brand-200 bg-card px-3 py-2 shadow-sm transition-all",
        STATUS_RING[data.status] ?? STATUS_RING.unknown,
        data.status === "skipped" && "opacity-60",
        selected && "ring-offset-2",
      )}
    >
      {inputHandles.map((handleId, idx) => (
        <Handle
          key={handleId}
          id={handleId}
          type="target"
          position={Position.Left}
          isConnectable={false}
          style={{ top: topPct(idx, inputHandles.length) }}
          className={cn(
            "!h-2.5 !w-2.5 !border-2 !border-background",
            isModelHandle(handleId) ? "!bg-purple-400" : "!bg-brand-300",
          )}
        />
      ))}

      <div className="flex items-center gap-2">
        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-muted text-brand-600">
          <Icon className="h-3 w-3" strokeWidth={2.25} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate text-[13px] font-medium leading-tight text-slate-700">
            {data.label}
          </div>
          {data.rows !== null && (
            <div className="text-[10px] text-muted-foreground">
              {formatCount(data.rows)} rows
            </div>
          )}
        </div>
        {statusIcon && (
          <statusIcon.icon className={cn("h-3.5 w-3.5 shrink-0", statusIcon.className)} />
        )}
      </div>

      {def?.hasOutput &&
        outputHandles.map((handleId, idx) => (
          <Handle
            key={handleId}
            id={handleId}
            type="source"
            position={Position.Right}
            isConnectable={false}
            style={{ top: topPct(idx, outputHandles.length) }}
            className={cn(
              "!h-2.5 !w-2.5 !border-2 !border-background",
              isModelHandle(handleId) ? "!bg-purple-400" : "!bg-brand-300",
            )}
          />
        ))}
    </div>
  );
}
