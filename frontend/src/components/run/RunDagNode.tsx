import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import { AlertCircle, CheckCircle2, MinusCircle } from "lucide-react";
import { getNodeTypeDef, type NodeCategory } from "@/lib/nodeCatalog";
import { CATEGORY_THEME, getNodeIcon } from "@/lib/nodeVisuals";
import type { NodeResultStatus } from "@/lib/types";
import { formatCount } from "@/lib/format";
import { cn } from "@/lib/utils";

export interface RunDagNodeData {
  label: string;
  nodeType: string;
  status: NodeResultStatus | "unknown";
  rows: number | null;
  [key: string]: unknown;
}

export type RunDagNodeType = Node<RunDagNodeData>;

const STATUS_RING: Record<string, string> = {
  success: "ring-success/50",
  failed: "ring-destructive/60",
  skipped: "ring-muted-foreground/30",
  unknown: "ring-border",
};

const STATUS_ICON: Record<string, { icon: typeof CheckCircle2; className: string } | null> = {
  success: { icon: CheckCircle2, className: "text-success" },
  failed: { icon: AlertCircle, className: "text-destructive" },
  skipped: { icon: MinusCircle, className: "text-muted-foreground" },
  unknown: null,
};

/** A read-only node for the run DAG: same visual language as the editor, but
 * decorated with the node's execution status and row count. */
export function RunDagNode({ data, selected }: NodeProps<RunDagNodeType>) {
  const def = getNodeTypeDef(data.nodeType);
  const category: NodeCategory = def?.category ?? "transform";
  const theme = CATEGORY_THEME[category];
  const inputHandles = def?.inputHandles ?? ["in"];
  const Icon = getNodeIcon(data.nodeType);
  const statusIcon = STATUS_ICON[data.status];

  return (
    <div
      className={cn(
        "min-w-[184px] rounded-xl border bg-card px-3 py-2.5 shadow-sm transition-all",
        theme.card,
        "ring-2",
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
          style={{
            top:
              inputHandles.length === 1
                ? "50%"
                : `${((idx + 1) / (inputHandles.length + 1)) * 100}%`,
          }}
          className="!h-2.5 !w-2.5 !border-2 !border-background !bg-slate-400"
        />
      ))}

      <div className="flex items-center gap-2.5">
        <span
          className={cn(
            "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg shadow-sm",
            theme.badge,
          )}
        >
          <Icon className="h-4 w-4" strokeWidth={2.25} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold leading-tight text-slate-800">
            {data.label}
          </div>
          <div className="text-[10px] font-medium text-muted-foreground">
            {data.rows !== null ? `${formatCount(data.rows)} rows` : def?.label ?? data.nodeType}
          </div>
        </div>
        {statusIcon && (
          <statusIcon.icon className={cn("h-4 w-4 shrink-0", statusIcon.className)} />
        )}
      </div>

      {def?.hasOutput && (
        <Handle
          id="out"
          type="source"
          position={Position.Right}
          isConnectable={false}
          className="!h-2.5 !w-2.5 !border-2 !border-background !bg-slate-400"
        />
      )}
    </div>
  );
}
