import { Handle, Position, type NodeProps } from "@xyflow/react";
import { getNodeTypeDef, type NodeCategory } from "@/lib/nodeCatalog";
import { cn } from "@/lib/utils";
import type { FlowNodeType } from "@/stores/flowEditorStore";

const CATEGORY_STYLES: Record<NodeCategory, string> = {
  input: "border-emerald-400 bg-emerald-50",
  clean: "border-sky-400 bg-sky-50",
  transform: "border-violet-400 bg-violet-50",
  output: "border-amber-400 bg-amber-50",
};

export function FlowNode({ type, data, selected }: NodeProps<FlowNodeType>) {
  const def = getNodeTypeDef(type ?? "");
  const category = def?.category ?? "transform";
  const inputHandles = def?.inputHandles ?? ["in"];

  return (
    <div
      className={cn(
        "min-w-[160px] rounded-md border-2 px-3 py-2 shadow-sm transition-shadow",
        CATEGORY_STYLES[category],
        selected && "ring-2 ring-primary ring-offset-1",
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
          className="!h-2.5 !w-2.5 !bg-slate-500"
        />
      ))}

      <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">
        {type}
      </div>
      <div className="text-sm font-medium text-slate-800">
        {data.label}
      </div>
      {inputHandles.length > 1 && (
        <div className="mt-1 flex justify-between text-[9px] text-slate-400">
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
          className="!h-2.5 !w-2.5 !bg-slate-500"
        />
      )}
    </div>
  );
}
