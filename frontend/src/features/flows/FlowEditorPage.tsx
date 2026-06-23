import { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ReactFlowProvider } from "@xyflow/react";
import {
  ArrowLeft,
  CalendarClock,
  Code2,
  Eye,
  EyeOff,
  Loader2,
  Pencil,
  Play,
  Power,
  Save,
} from "lucide-react";
import { useCreateRun, useFlow, useToggleFlow, useUpdateFlow } from "./hooks";
import { useCreateSchedule } from "@/features/schedules/hooks";
import { ScheduleFormDialog } from "@/features/schedules/ScheduleFormDialog";
import { FlowEditDialog } from "./FlowEditDialog";
import { useDatasets } from "@/features/datasets/hooks";
import { useProjects } from "@/features/projects/hooks";
import { useFlowEditorStore } from "@/stores/flowEditorStore";
import { graphToStore, storeToGraph } from "./graphMapper";
import { type NodeTypeDef } from "@/lib/nodeCatalog";
import { createFlowNode } from "@/lib/createNode";
import { hasReadyInput } from "@/lib/flowGraph";
import { validateFlow } from "@/lib/flowValidation";
import { FlowCanvas } from "@/components/flow/FlowCanvas";
import { NodePalette } from "@/components/flow/NodePalette";
import { NodeSidebar } from "@/components/flow/NodeSidebar";
import { PreviewPanel } from "@/components/flow/PreviewPanel";
import { ValidationSummary } from "@/components/flow/ValidationSummary";
import { ExportCodeDialog } from "./ExportCodeDialog";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export function FlowEditorPage() {
  const { flowId } = useParams<{ flowId: string }>();
  const navigate = useNavigate();
  const { data: flow, isLoading } = useFlow(flowId ?? null);
  const updateFlow = useUpdateFlow();
  const { data: datasets } = useDatasets();
  const { data: projects } = useProjects();

  const nodes = useFlowEditorStore((s) => s.nodes);
  const edges = useFlowEditorStore((s) => s.edges);
  const setGraph = useFlowEditorStore((s) => s.setGraph);
  const addNode = useFlowEditorStore((s) => s.addNode);
  const reset = useFlowEditorStore((s) => s.reset);
  const dirty = useFlowEditorStore((s) => s.dirty);
  const markClean = useFlowEditorStore((s) => s.markClean);
  const previewOpen = useFlowEditorStore((s) => s.previewOpen);
  const setPreviewOpen = useFlowEditorStore((s) => s.setPreviewOpen);
  const setInvalidNodeIds = useFlowEditorStore((s) => s.setInvalidNodeIds);
  const setFlowProjectId = useFlowEditorStore((s) => s.setFlowProjectId);
  const flowProjectId = useFlowEditorStore((s) => s.flowProjectId);
  const projectName = (projects ?? []).find((p) => p.id === flowProjectId)?.name ?? null;

  const [exportOpen, setExportOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  // Height of the bottom preview pane, drag-resizable and remembered locally.
  const [previewHeight, setPreviewHeight] = useState(() => {
    const saved = Number(localStorage.getItem("ff_preview_height"));
    return saved >= 180 ? saved : 420;
  });
  useEffect(() => {
    localStorage.setItem("ff_preview_height", String(previewHeight));
  }, [previewHeight]);

  const startPreviewResize = (e: React.MouseEvent) => {
    e.preventDefault();
    const startY = e.clientY;
    const startHeight = previewHeight;
    const onMove = (ev: MouseEvent) => {
      // Drag up grows the pane; clamp so the canvas keeps usable space.
      const next = startHeight + (startY - ev.clientY);
      setPreviewHeight(Math.min(Math.max(next, 180), window.innerHeight - 200));
    };
    const onUp = () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
      document.body.style.userSelect = "";
    };
    document.body.style.userSelect = "none";
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  };
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [engine, setEngine] = useState<"pandas" | "polars">("pandas");
  const createRun = useCreateRun(flowId ?? "");
  const createSchedule = useCreateSchedule();
  const toggleFlow = useToggleFlow();

  const validation = useMemo(
    () => validateFlow(nodes, edges, datasets ?? []),
    [nodes, edges, datasets],
  );

  // Push the set of invalid node ids into the store so the canvas can badge them.
  useEffect(() => {
    setInvalidNodeIds([...validation.errorsByNode.keys()]);
  }, [validation, setInvalidNodeIds]);

  // Load the persisted graph into the editor store once fetched.
  useEffect(() => {
    if (flow?.graph_json) {
      const { nodes, edges } = graphToStore(flow.graph_json);
      setGraph(nodes, edges);
      setEngine(flow.graph_json.engine ?? "pandas");
    } else if (flow) {
      setGraph([], []);
      setEngine("pandas");
    }
    setFlowProjectId(flow?.project_id ?? null);
    return () => reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flow?.id]);

  const handleAddNode = (def: NodeTypeDef) => addNode(createFlowNode(def));

  // Gate: the first step must be an input node with a dataset chosen.
  const inputReady = hasReadyInput(nodes);

  const handleSave = () => {
    if (!flowId) return;
    const graph = storeToGraph(
      useFlowEditorStore.getState().nodes,
      useFlowEditorStore.getState().edges,
    );
    graph.engine = engine;
    updateFlow.mutate(
      { id: flowId, body: { graph_json: graph } },
      { onSuccess: () => markClean() },
    );
  };

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading…
      </div>
    );
  }
  if (!flow) {
    return <div className="p-6 text-sm text-destructive">Flow not found.</div>;
  }

  const isDisabled = flow.is_disabled;
  const runReason = isDisabled
    ? "This flow is disabled. Re-enable it first."
    : validation.errors[0]?.message;
  const previewReason = isDisabled
    ? "This flow is disabled."
    : validation.errors.find((e) => e.code !== "NO_OUTPUT")?.message;

  // Inputs already pin their datasets, so running just executes the saved graph
  // (on the chosen engine) and takes you to the run's results.
  const handleRun = () => {
    if (!flowId) return;
    const graph = storeToGraph(
      useFlowEditorStore.getState().nodes,
      useFlowEditorStore.getState().edges,
    );
    graph.engine = engine;
    updateFlow.mutate(
      { id: flowId, body: { graph_json: graph } },
      {
        onSuccess: () => {
          markClean();
          createRun.mutate(
            { engine },
            { onSuccess: (run) => navigate(`/runs/${run.id}`) },
          );
        },
      },
    );
  };

  return (
    <ReactFlowProvider>
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between border-b border-border bg-background/80 px-4 py-2 backdrop-blur">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="sm" onClick={() => navigate("/flows")}>
              <ArrowLeft className="h-4 w-4" /> Flows
            </Button>
            <h1 className="text-sm font-semibold">{flow.name}</h1>
            <button
              onClick={() => setEditOpen(true)}
              className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              title="Rename flow"
            >
              <Pencil className="h-3.5 w-3.5" />
            </button>
            {projectName && (
              <span className="text-xs text-muted-foreground">
                / {projectName}
              </span>
            )}
            {isDisabled && (
              <span className="rounded-md bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                disabled
              </span>
            )}
            {!isDisabled && dirty && (
              <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-700">
                unsaved
              </span>
            )}
            {!isDisabled && <ValidationSummary validation={validation} />}
          </div>
          <div className="flex items-center gap-2">
            {isDisabled ? (
              <Button
                size="sm"
                variant="outline"
                onClick={() => toggleFlow.mutate({ id: flow.id, is_disabled: false })}
                disabled={toggleFlow.isPending}
              >
                <Power className="h-4 w-4" /> Re-enable flow
              </Button>
            ) : (
              <>
                <GatedButton
                  disabled={!validation.canPreview}
                  reason={previewReason}
                  variant="outline"
                  onClick={() => setPreviewOpen(!previewOpen)}
                >
                  {previewOpen ? (
                    <EyeOff className="h-4 w-4" />
                  ) : (
                    <Eye className="h-4 w-4" />
                  )}
                  {previewOpen ? "Hide preview" : "Preview"}
                </GatedButton>
                <div className="flex items-center overflow-hidden rounded-md border border-input">
                  <select
                    value={engine}
                    onChange={(e) => setEngine(e.target.value as "pandas" | "polars")}
                    title="Execution engine"
                    className="h-9 border-r border-input bg-background px-2 text-xs font-medium focus-visible:outline-none"
                  >
                    <option value="pandas">pandas</option>
                    <option value="polars">polars</option>
                  </select>
                  <GatedButton
                    disabled={!validation.canRun || createRun.isPending}
                    reason={runReason}
                    onClick={handleRun}
                    className="rounded-none border-0"
                  >
                    {createRun.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Play className="h-4 w-4" />
                    )}
                    Run
                  </GatedButton>
                </div>
                <GatedButton
                  disabled={!validation.canExport}
                  reason={runReason}
                  variant="outline"
                  onClick={() => setExportOpen(true)}
                >
                  <Code2 className="h-4 w-4" /> Export
                </GatedButton>
                <Button size="sm" variant="outline" onClick={() => setScheduleOpen(true)}>
                  <CalendarClock className="h-4 w-4" /> Schedule
                </Button>
                <Button size="sm" onClick={handleSave} disabled={updateFlow.isPending}>
                  {updateFlow.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4" />
                  )}
                  {updateFlow.isPending ? "Saving…" : "Save"}
                </Button>
              </>
            )}
          </div>
        </div>

        {isDisabled && (
          <div className="flex items-center gap-2 border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800">
            <Power className="h-4 w-4 shrink-0" />
            This flow is disabled — it is read-only and cannot be run. Click
            <button
              className="font-semibold underline underline-offset-2 hover:text-amber-900"
              onClick={() => toggleFlow.mutate({ id: flow.id, is_disabled: false })}
            >
              Re-enable
            </button>
            to restore it.
          </div>
        )}

        <div className="flex min-h-0 flex-1">
          <NodePalette onAdd={handleAddNode} unlocked={inputReady} />
          <div className="flex min-w-0 flex-1 flex-col">
            <div className="min-h-0 flex-1">
              <FlowCanvas />
            </div>
            {previewOpen && (
              <>
                <div
                  onMouseDown={startPreviewResize}
                  className="group flex h-2 shrink-0 cursor-row-resize items-center justify-center border-t border-border bg-muted/40 hover:bg-primary/10"
                  title="Drag to resize the preview"
                >
                  <div className="h-1 w-10 rounded-full bg-border transition-colors group-hover:bg-primary/50" />
                </div>
                <div className="shrink-0" style={{ height: previewHeight }}>
                  <PreviewPanel flowId={flow.id} onClose={() => setPreviewOpen(false)} />
                </div>
              </>
            )}
          </div>
          <NodeSidebar />
        </div>
      </div>

      <ExportCodeDialog
        flowId={flow.id}
        open={exportOpen}
        onOpenChange={setExportOpen}
      />

      <ScheduleFormDialog
        open={scheduleOpen}
        onOpenChange={setScheduleOpen}
        lockedFlowId={flow.id}
        submitting={createSchedule.isPending}
        error={createSchedule.error}
        onSubmit={(flowId, body) =>
          createSchedule.mutate(
            { flowId, body },
            { onSuccess: (schedule) => { setScheduleOpen(false); navigate(`/schedules/${schedule.id}`); } },
          )
        }
      />

      <FlowEditDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        flow={flow}
        submitting={updateFlow.isPending}
        error={updateFlow.error}
        onSubmit={(values) =>
          updateFlow.mutate(
            { id: flow.id, body: { name: values.name, description: values.description } },
            { onSuccess: () => setEditOpen(false) },
          )
        }
      />
    </ReactFlowProvider>
  );
}

/**
 * A header action button that, when disabled by validation, explains why on
 * hover. The tooltip wraps a span so it still fires for the disabled button.
 */
function GatedButton({
  disabled,
  reason,
  children,
  ...props
}: {
  disabled: boolean;
  reason?: string;
  variant?: "outline";
  className?: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  const button = (
    <Button size="sm" disabled={disabled} {...props}>
      {children}
    </Button>
  );
  if (!disabled || !reason) return button;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-flex cursor-not-allowed">{button}</span>
      </TooltipTrigger>
      <TooltipContent>{reason}</TooltipContent>
    </Tooltip>
  );
}
