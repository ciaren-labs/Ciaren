import { Handle, Position, type NodeProps } from "@xyflow/react";
import { AlertCircle, Copy, Pencil, Trash2 } from "lucide-react";
import { getNodeTypeDef, getOutputHandles } from "@/features/flows/editor/nodeCatalog";
import {
  handleCompatibility,
  nodeHasNoCompatibleHandle,
  type HandleStatus,
} from "@/features/flows/editor/connectionRules";
import { getNodeIcon } from "@/lib/nodeVisuals";
import { getNodeSummary } from "@/lib/nodeSummary";
import { TRAIN_NODE_TASKS } from "@/lib/mlModels";
import { cn } from "@/lib/utils";
import { useDatasets } from "@/features/datasets/hooks";
import { useFlowEditorStore } from "@/stores/flowEditorStore";
import type { FlowNodeType } from "@/stores/flowEditorStore";
import { undoableToast } from "./undoableToast";

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

/** Vertical offset (px) that pulls a label off its handle so the connecting wire
 * isn't hidden behind the text: upper handles nudge up, lower handles down. */
function labelNudge(idx: number, count: number): number {
  if (count < 2) return 0;
  const NUDGE = 11;
  return (idx / (count - 1) - 0.5) * 2 * NUDGE;
}

/** Handle styling: model handles are purple, data handles brand-blue. While a
 * wire is being dragged, a handle that could complete it grows and gains a
 * ring; one that can't fades out, so the eye lands on the legal drop points. */
function handleClasses(model: boolean, status: HandleStatus): string {
  return cn(
    "!h-2.5 !w-2.5 !border-2 !border-background transition-all duration-150",
    model ? "!bg-purple-400" : "!bg-brand-300",
    status === "compatible" &&
      (model
        ? "!h-3.5 !w-3.5 !bg-purple-500 ring-2 ring-purple-300"
        : "!h-3.5 !w-3.5 !bg-brand-500 ring-2 ring-brand-300"),
    status === "incompatible" && "!opacity-30",
  );
}

/** A small label pinned just outside the card near a handle, nudged off the wire. */
function HandleLabel({
  side,
  top,
  nudge,
  label,
  model,
}: {
  side: "left" | "right";
  top: string;
  nudge: number;
  label: string;
  model: boolean;
}) {
  return (
    <span
      className={cn(
        "pointer-events-none absolute z-10 whitespace-nowrap rounded bg-card/90 px-1 text-[9px] font-medium uppercase tracking-tight shadow-sm",
        model ? "text-purple-600" : "text-slate-500",
      )}
      style={{
        top,
        transform: `translateY(calc(-50% + ${nudge}px))`,
        [side === "left" ? "right" : "left"]: "100%",
        [side === "left" ? "marginRight" : "marginLeft"]: 6,
      }}
    >
      {label}
    </span>
  );
}

/**
 * Minimalist node: a neutral surface with a thin purple border and a small icon.
 * Multi-handle nodes (split, train, predict, join) label each port so it's clear
 * which wire is which. Under the label sits a one-line config summary (dataset,
 * filter expression, join keys, …) so a misconfigured node is spotted without
 * opening the sidebar. During a connection drag, handles that can accept the
 * wire light up and everything incompatible dims.
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
  const selectNode = useFlowEditorStore((s) => s.selectNode);
  const duplicateNode = useFlowEditorStore((s) => s.duplicateNode);
  const removeNode = useFlowEditorStore((s) => s.removeNode);

  // Live connection feedback: while a wire is dragged from some handle, style
  // this node's handles by whether they could legally complete the connection.
  const pending = useFlowEditorStore((s) => s.pendingConnection);
  const pendingDef = pending ? getNodeTypeDef(pending.nodeType) : undefined;
  const dimmed = nodeHasNoCompatibleHandle(pending, pendingDef, id, def);

  // Config summary: input nodes show their dataset's name, so resolve it here.
  // The query only runs for nodes that reference a dataset (react-query dedupes
  // the request across all such nodes; other nodes never subscribe-fetch).
  const flowProjectId = useFlowEditorStore((s) => s.flowProjectId);
  const referencesDataset =
    typeof (data.config as Record<string, unknown> | undefined)?.dataset_id === "string" &&
    (data.config as Record<string, unknown>).dataset_id !== "";
  const { data: datasets } = useDatasets(flowProjectId ?? undefined, referencesDataset);
  const config = (data.config ?? {}) as Record<string, unknown>;
  const datasetName = referencesDataset
    ? datasets?.find((d) => d.id === config.dataset_id)?.name ?? null
    : null;
  const subtitle = getNodeSummary(type ?? "", config, { datasetName });
  // Train/model nodes keep their purple "model" accent; other summaries are muted.
  const subtitleIsModel = (type ?? "") in TRAIN_NODE_TASKS;

  return (
    <div
      className={cn(
        "group relative min-w-[168px] rounded-lg border border-brand-200 bg-card px-3 py-2 shadow-sm",
        "transition-all duration-150 hover:-translate-y-0.5 hover:border-brand-400 hover:shadow-md",
        selected && "border-brand-500 ring-2 ring-brand-300/60",
        hasError && "border-destructive/60 ring-2 ring-destructive/40",
        dimmed && "opacity-40",
      )}
    >
      <div
        className={cn(
          "nodrag nopan absolute -top-3 right-1.5 z-20 flex items-center gap-0.5 rounded-md border border-border bg-card p-0.5 opacity-0 shadow-sm transition-opacity duration-150",
          "group-hover:opacity-100 focus-within:opacity-100",
          selected && "opacity-100",
        )}
      >
        <button
          type="button"
          title="Edit node"
          aria-label="Edit node"
          onClick={(e) => {
            e.stopPropagation();
            selectNode(id);
          }}
          className="flex h-5 w-5 items-center justify-center rounded text-slate-500 hover:bg-muted hover:text-brand-600"
        >
          <Pencil className="h-3 w-3" />
        </button>
        <button
          type="button"
          title="Duplicate node"
          aria-label="Duplicate node"
          onClick={(e) => {
            e.stopPropagation();
            const existed = useFlowEditorStore.getState().nodes.some((n) => n.id === id);
            duplicateNode(id);
            if (existed) undoableToast("Node duplicated");
          }}
          className="flex h-5 w-5 items-center justify-center rounded text-slate-500 hover:bg-muted hover:text-brand-600"
        >
          <Copy className="h-3 w-3" />
        </button>
        <button
          type="button"
          title="Delete node"
          aria-label="Delete node"
          onClick={(e) => {
            e.stopPropagation();
            const existed = useFlowEditorStore.getState().nodes.some((n) => n.id === id);
            removeNode(id);
            if (existed) undoableToast("Node deleted");
          }}
          className="flex h-5 w-5 items-center justify-center rounded text-slate-500 hover:bg-destructive/10 hover:text-destructive"
        >
          <Trash2 className="h-3 w-3" />
        </button>
      </div>

      {inputHandles.map((handleId, idx) => {
        const top = topPct(idx, inputHandles.length);
        const status = handleCompatibility(pending, pendingDef, id, def, handleId, "target");
        return (
          <div key={handleId}>
            <Handle
              id={handleId}
              type="target"
              position={Position.Left}
              style={{ top }}
              className={handleClasses(isModelHandle(handleId), status)}
            />
            {inputHandles.length > 1 && (
              <HandleLabel
                side="left"
                top={top}
                nudge={labelNudge(idx, inputHandles.length)}
                label={handleLabel(handleId)}
                model={isModelHandle(handleId)}
              />
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
            <div
              className={cn(
                "max-w-[180px] truncate text-[10px] leading-tight",
                subtitleIsModel ? "text-purple-600" : "text-slate-400",
              )}
              title={subtitle}
            >
              {subtitle}
            </div>
          )}
        </div>
        {hasError && <AlertCircle className="ml-auto h-3.5 w-3.5 shrink-0 text-destructive" />}
      </div>

      {outputHandles.map((handleId, idx) => {
        const top = topPct(idx, outputHandles.length);
        const status = handleCompatibility(pending, pendingDef, id, def, handleId, "source");
        return (
          <div key={handleId}>
            <Handle
              id={handleId}
              type="source"
              position={Position.Right}
              style={{ top }}
              className={handleClasses(isModelHandle(handleId), status)}
            />
            {outputHandles.length > 1 && (
              <HandleLabel
                side="right"
                top={top}
                nudge={labelNudge(idx, outputHandles.length)}
                label={handleLabel(handleId)}
                model={isModelHandle(handleId)}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
