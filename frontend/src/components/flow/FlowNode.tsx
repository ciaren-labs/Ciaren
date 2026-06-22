import { Handle, Position, type NodeProps } from "@xyflow/react";
import { AlertCircle } from "lucide-react";
import { getNodeTypeDef, type NodeCategory } from "@/lib/nodeCatalog";
import { CATEGORY_THEME, getNodeIcon } from "@/lib/nodeVisuals";
import { cn } from "@/lib/utils";
import { useFlowEditorStore } from "@/stores/flowEditorStore";
import type { FlowNodeType } from "@/stores/flowEditorStore";

export function FlowNode({ id, type, data, selected }: NodeProps<FlowNodeType>) {
  const def = getNodeTypeDef(type ?? "");
  const category: NodeCategory = def?.category ?? "transform";
  const theme = CATEGORY_THEME[category];
  const inputHandles = def?.inputHandles ?? ["in"];
  const Icon = getNodeIcon(type);

  const hasError = useFlowEditorStore((s) => s.invalidNodeIds.includes(id));

  return (
    <div
      className={cn(
        "group min-w-[176px] rounded-xl border bg-card px-3 py-2.5 shadow-sm",
        "transition-all duration-150 hover:-translate-y-0.5 hover:shadow-md",
        theme.card,
        selected && cn("ring-2 ring-offset-2", theme.ring),
        hasError && "border-destructive/60 ring-2 ring-destructive/40",
      )}
    >
      {inputHandles.map((handleId, idx) => (
        <Handle
          key={handleId}
          id={handleId}
          type="target"
          position={Position.Left}
          style={{
            top:
              inputHandles.length === 1
                ? "50%"
                : `${((idx + 1) / (inputHandles.length + 1)) * 100}%`,
          }}
          className="!h-3 !w-3 !border-2 !border-background !bg-slate-400"
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
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold leading-tight text-slate-800">
            {data.label}
          </div>
          <div className={cn("text-[10px] font-medium uppercase tracking-wide", theme.text)}>
            {def?.label ?? type}
          </div>
        </div>
        {hasError && (
          <AlertCircle className="ml-auto h-4 w-4 shrink-0 text-destructive" />
        )}
      </div>

      {inputHandles.length > 1 && (
        <div className="mt-1.5 flex justify-between px-0.5 text-[9px] font-medium uppercase text-slate-400">
          {inputHandles.map((h) => (
            <span key={h}>{h}</span>
          ))}
        </div>
      )}

      {def?.hasOutput && (
        <Handle
          id="out"
          type="source"
          position={Position.Right}
          className="!h-3 !w-3 !border-2 !border-background !bg-slate-400"
        />
      )}
    </div>
  );
}
