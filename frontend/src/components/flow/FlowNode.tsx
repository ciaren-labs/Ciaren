import { Handle, Position, type NodeProps } from "@xyflow/react";
import { AlertCircle } from "lucide-react";
import { getNodeTypeDef } from "@/lib/nodeCatalog";
import { getNodeIcon } from "@/lib/nodeVisuals";
import { cn } from "@/lib/utils";
import { useFlowEditorStore } from "@/stores/flowEditorStore";
import type { FlowNodeType } from "@/stores/flowEditorStore";

/**
 * Minimalist node: a neutral surface with a thin purple border and a small,
 * uncoloured icon. Categories are no longer colour-coded on the canvas.
 */
export function FlowNode({ id, type, data, selected }: NodeProps<FlowNodeType>) {
  const def = getNodeTypeDef(type ?? "");
  const inputHandles = def?.inputHandles ?? ["in"];
  const Icon = getNodeIcon(type);

  const hasError = useFlowEditorStore((s) => s.invalidNodeIds.includes(id));

  return (
    <div
      className={cn(
        "group min-w-[168px] rounded-lg border border-brand-200 bg-card px-3 py-2 shadow-sm",
        "transition-all duration-150 hover:-translate-y-0.5 hover:border-brand-400 hover:shadow-md",
        selected && "border-brand-500 ring-2 ring-brand-300/60",
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
          className="!h-2.5 !w-2.5 !border-2 !border-background !bg-brand-300"
        />
      ))}

      <div className="flex items-center gap-2">
        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-muted text-brand-600">
          <Icon className="h-3 w-3" strokeWidth={2.25} />
        </span>
        <div className="min-w-0">
          <div className="truncate text-[13px] font-medium leading-tight text-slate-700">
            {data.label}
          </div>
        </div>
        {hasError && (
          <AlertCircle className="ml-auto h-3.5 w-3.5 shrink-0 text-destructive" />
        )}
      </div>

      {inputHandles.length > 1 && (
        <div className="mt-1 flex justify-between px-0.5 text-[9px] font-medium uppercase text-slate-400">
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
          className="!h-2.5 !w-2.5 !border-2 !border-background !bg-brand-300"
        />
      )}
    </div>
  );
}
