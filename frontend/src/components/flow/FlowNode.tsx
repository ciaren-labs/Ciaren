import { Handle, Position, type NodeProps } from "@xyflow/react";
import { AlertCircle } from "lucide-react";
import { getNodeTypeDef, getOutputHandles } from "@/lib/nodeCatalog";
import { getNodeIcon } from "@/lib/nodeVisuals";
import { getModelDef } from "@/lib/mlModels";
import { cn } from "@/lib/utils";
import { useFlowEditorStore } from "@/stores/flowEditorStore";
import type { FlowNodeType } from "@/stores/flowEditorStore";

/** A "model" handle carries a model reference, not data — drawn purple. */
function isModelHandle(handle: string): boolean {
  return handle === "model";
}

/** Friendly label shown next to a handle on the canvas. */
function handleLabel(id: string): string {
  return { in: "data", out: "data", model: "model", train: "train", test: "test" }[id] ?? id;
}

function topPct(idx: number, count: number): string {
  return count === 1 ? "50%" : `${((idx + 1) / (count + 1)) * 100}%`;
}

/** A small label pinned just outside the card at a handle's vertical position. */
function HandleLabel({ side, top, label, model }: { side: "left" | "right"; top: string; label: string; model: boolean }) {
  return (
    <span
      className={cn(
        "pointer-events-none absolute z-10 -translate-y-1/2 whitespace-nowrap rounded bg-card/90 px-1 text-[9px] font-medium uppercase tracking-tight shadow-sm",
        model ? "text-purple-600" : "text-slate-500",
      )}
      style={{ top, [side === "left" ? "right" : "left"]: "100%", [side === "left" ? "marginRight" : "marginLeft"]: 6 }}
    >
      {label}
    </span>
  );
}

/**
 * Minimalist node: a neutral surface with a thin purple border and a small icon.
 * Multi-handle nodes (split, train, predict, join) label each port so it's clear
 * which wire is which; mlTrain shows the chosen model.
 */
export function FlowNode({ id, type, data, selected }: NodeProps<FlowNodeType>) {
  const def = getNodeTypeDef(type ?? "");
  const inputHandles = [
    ...(def?.inputHandles ?? ["in"]),
    ...(def?.optionalInputHandles ?? []),
  ];
  const outputHandles = def ? getOutputHandles(def) : ["out"];
  const Icon = getNodeIcon(type);
  const hasError = useFlowEditorStore((s) => s.invalidNodeIds.includes(id));

  // mlTrain shows the selected model under its label.
  const subtitle =
    type === "mlTrain"
      ? getModelDef(String((data.config as Record<string, unknown>)?.model_type ?? ""))?.label
      : undefined;

  return (
    <div
      className={cn(
        "group relative min-w-[168px] rounded-lg border border-brand-200 bg-card px-3 py-2 shadow-sm",
        "transition-all duration-150 hover:-translate-y-0.5 hover:border-brand-400 hover:shadow-md",
        selected && "border-brand-500 ring-2 ring-brand-300/60",
        hasError && "border-destructive/60 ring-2 ring-destructive/40",
      )}
    >
      {inputHandles.map((handleId, idx) => {
        const top = topPct(idx, inputHandles.length);
        return (
          <div key={handleId}>
            <Handle
              id={handleId}
              type="target"
              position={Position.Left}
              style={{ top }}
              className={cn(
                "!h-2.5 !w-2.5 !border-2 !border-background",
                isModelHandle(handleId) ? "!bg-purple-400" : "!bg-brand-300",
              )}
            />
            {inputHandles.length > 1 && (
              <HandleLabel side="left" top={top} label={handleLabel(handleId)} model={isModelHandle(handleId)} />
            )}
          </div>
        );
      })}

      <div className="flex items-center gap-2">
        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-muted text-brand-600">
          <Icon className="h-3 w-3" strokeWidth={2.25} />
        </span>
        <div className="min-w-0">
          <div className="truncate text-[13px] font-medium leading-tight text-slate-700">
            {data.label}
          </div>
          {subtitle && (
            <div className="truncate text-[10px] leading-tight text-purple-600">{subtitle}</div>
          )}
        </div>
        {hasError && <AlertCircle className="ml-auto h-3.5 w-3.5 shrink-0 text-destructive" />}
      </div>

      {outputHandles.map((handleId, idx) => {
        const top = topPct(idx, outputHandles.length);
        return (
          <div key={handleId}>
            <Handle
              id={handleId}
              type="source"
              position={Position.Right}
              style={{ top }}
              className={cn(
                "!h-2.5 !w-2.5 !border-2 !border-background",
                isModelHandle(handleId) ? "!bg-purple-400" : "!bg-brand-300",
              )}
            />
            {outputHandles.length > 1 && (
              <HandleLabel side="right" top={top} label={handleLabel(handleId)} model={isModelHandle(handleId)} />
            )}
          </div>
        );
      })}
    </div>
  );
}
