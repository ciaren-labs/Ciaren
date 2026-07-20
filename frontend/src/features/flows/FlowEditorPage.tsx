import { useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ReactFlowProvider } from "@xyflow/react";
import { ArrowLeft, Loader2 } from "lucide-react";
import { useCreateRun, useFlow, useToggleFlow, useUpdateFlow } from "./hooks";
import { useCreateSchedule } from "@/features/schedules/hooks";
import { ScheduleFormDialog } from "@/features/schedules/ScheduleFormDialog";
import { FlowEditDialog } from "./FlowEditDialog";
import { useDatasets } from "@/features/datasets/hooks";
import { useProjects } from "@/features/projects/hooks";
import { useFlowEditorStore } from "@/stores/flowEditorStore";
import { readLocalStorage, writeLocalStorage } from "@/lib/safeStorage";
import { useUnsavedChangesGuard } from "@/lib/useUnsavedChangesGuard";
import { toast } from "@/stores/toastStore";
import { graphToStore, storeToGraph } from "./graphMapper";
import { type NodeTypeDef } from "@/features/flows/editor/nodeCatalog";
import { createFlowNode } from "@/features/flows/editor/createNode";
import { hasReadyInput } from "@/features/flows/editor/flowGraph";
import { validateFlow } from "@/features/flows/editor/flowValidation";
import { FlowCanvas } from "@/components/flow/FlowCanvas";
import { NodePalette } from "@/components/flow/NodePalette";
import { NodeSidebar } from "@/components/flow/NodeSidebar";
import { PreviewPanel } from "@/components/flow/PreviewPanel";
import { ExportCodeDialog } from "./ExportCodeDialog";
import { ParametersDialog } from "./ParametersDialog";
import { RunParametersDialog } from "./RunParametersDialog";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/PageState";
import { EditorToolbar } from "./components/EditorToolbar";
import { DisabledFlowBanner } from "./components/DisabledFlowBanner";

export function FlowEditorPage() {
  const { flowId } = useParams<{ flowId: string }>();
  const navigate = useNavigate();
  const { data: flow, isPending, isError, error, refetch } = useFlow(flowId ?? null);
  const updateFlow = useUpdateFlow();
  const { data: datasets } = useDatasets(flow?.project_id ?? undefined);
  const { data: projects } = useProjects();

  const nodes = useFlowEditorStore((s) => s.nodes);
  const edges = useFlowEditorStore((s) => s.edges);
  const setGraph = useFlowEditorStore((s) => s.setGraph);
  const addNode = useFlowEditorStore((s) => s.addNode);
  const reset = useFlowEditorStore((s) => s.reset);
  const dirty = useFlowEditorStore((s) => s.dirty);
  // Warn before losing unsaved edits: browser prompt on tab close/reload, and a
  // confirm on in-app navigation away from the editor (see the toolbar Back).
  const confirmNavigation = useUnsavedChangesGuard(dirty);
  const markClean = useFlowEditorStore((s) => s.markClean);
  const markDirty = useFlowEditorStore((s) => s.markDirty);
  const canUndo = useFlowEditorStore((s) => s.past.length > 0);
  const canRedo = useFlowEditorStore((s) => s.future.length > 0);
  const undo = useFlowEditorStore((s) => s.undo);
  const redo = useFlowEditorStore((s) => s.redo);
  const previewOpen = useFlowEditorStore((s) => s.previewOpen);
  const setPreviewOpen = useFlowEditorStore((s) => s.setPreviewOpen);
  const setInvalidNodeIds = useFlowEditorStore((s) => s.setInvalidNodeIds);
  const setFlowProjectId = useFlowEditorStore((s) => s.setFlowProjectId);
  const flowProjectId = useFlowEditorStore((s) => s.flowProjectId);
  const projectName = (projects ?? []).find((p) => p.id === flowProjectId)?.name ?? null;

  const [exportOpen, setExportOpen] = useState(false);
  const [paramsOpen, setParamsOpen] = useState(false);
  const [runParamsOpen, setRunParamsOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  // Height of the bottom preview pane, drag-resizable and remembered locally.
  const [previewHeight, setPreviewHeight] = useState(() => {
    const saved = Number(readLocalStorage("ciaren_preview_height"));
    return saved >= 180 ? saved : 420;
  });
  useEffect(() => {
    writeLocalStorage("ciaren_preview_height", String(previewHeight));
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
  // Parameter specs declared on the flow. Kept in the editor store (so the node
  // sidebar can surface them) and re-attached to graph_json on save/run, since
  // storeToGraph only carries nodes + edges.
  const parameters = useFlowEditorStore((s) => s.parameters);
  const setParameters = useFlowEditorStore((s) => s.setParameters);
  const createRun = useCreateRun(flowId ?? "");
  const createSchedule = useCreateSchedule();
  const toggleFlow = useToggleFlow();

  // Keyed on structureVersion, not `nodes`: validation doesn't depend on node
  // positions, and `nodes` is replaced on every drag frame.
  const structureVersion = useFlowEditorStore((s) => s.structureVersion);
  const validation = useMemo(
    () => validateFlow(nodes, edges, datasets ?? []),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- structureVersion tracks nodes/edges structurally
    [structureVersion, datasets],
  );

  // Push the set of invalid node ids into the store so the canvas can badge them.
  useEffect(() => {
    setInvalidNodeIds([...validation.errorsByNode.keys()]);
  }, [validation, setInvalidNodeIds]);

  // Load the persisted graph into the editor store once fetched. FlowCanvas
  // must not mount until this has run — otherwise React Flow's `fitView`
  // resolves against the still-empty store from the first render and never
  // re-fits once the real graph arrives a tick later (nodes render clipped in
  // the top-left corner). `graphReadyForFlowId` lets the render below hold off
  // mounting <FlowCanvas> for that one extra frame.
  const [graphReadyForFlowId, setGraphReadyForFlowId] = useState<string | null>(null);
  useEffect(() => {
    if (flow?.graph_json) {
      const { nodes, edges } = graphToStore(flow.graph_json);
      setGraph(nodes, edges);
      setEngine(flow.graph_json.engine ?? "pandas");
      setParameters(flow.graph_json.parameters ?? []);
    } else if (flow) {
      setGraph([], []);
      setEngine("pandas");
      setParameters([]);
    }
    setFlowProjectId(flow?.project_id ?? null);
    setGraphReadyForFlowId(flow?.id ?? null);
    return () => reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flow?.id]);

  // Ctrl/Cmd+Z to undo, Ctrl/Cmd+Shift+Z or Ctrl+Y to redo. Ignored while
  // typing in a field (so native text-undo still works) or while the flow is
  // disabled (read-only).
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (flow?.is_disabled) return;
      const mod = e.ctrlKey || e.metaKey;
      if (!mod || e.key.toLowerCase() !== "z" && e.key.toLowerCase() !== "y") return;
      const target = e.target as HTMLElement | null;
      const tag = target?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || target?.isContentEditable) {
        return;
      }
      const key = e.key.toLowerCase();
      if (key === "z" && !e.shiftKey) {
        e.preventDefault();
        undo();
      } else if ((key === "z" && e.shiftKey) || key === "y") {
        e.preventDefault();
        redo();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [flow?.is_disabled, undo, redo]);

  const handleAddNode = (def: NodeTypeDef) => addNode(createFlowNode(def));

  // Gate: the first step must be an input node with a dataset chosen.
  const inputReady = hasReadyInput(nodes);

  // Build the persisted graph from the live editor state plus the engine and
  // parameter specs (which storeToGraph does not carry).
  const buildGraph = () => {
    const graph = storeToGraph(
      useFlowEditorStore.getState().nodes,
      useFlowEditorStore.getState().edges,
    );
    graph.engine = engine;
    if (parameters.length > 0) graph.parameters = parameters;
    return graph;
  };

  const handleSave = () => {
    if (!flowId) return;
    updateFlow.mutate(
      { id: flowId, body: { graph_json: buildGraph() } },
      {
        onSuccess: () => {
          markClean();
          toast.success("Flow saved");
        },
      },
    );
  };

  if (isPending) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading…
      </div>
    );
  }
  // A request failure (backend down, 500, …) is not the same as a deleted flow —
  // don't tell the user their flow is gone when we simply couldn't ask.
  if (isError) {
    return <ErrorState error={error} title="Couldn't load this flow" onRetry={() => refetch()} />;
  }
  if (!flow) {
    return (
      <div className="mx-auto flex max-w-md flex-col items-center gap-3 p-10 text-center">
        <h2 className="text-sm font-semibold">Flow not found</h2>
        <p className="text-sm text-muted-foreground">
          It may have been deleted, or the link is out of date.
        </p>
        <Button variant="outline" size="sm" onClick={() => navigate("/flows")}>
          <ArrowLeft className="h-3.5 w-3.5" /> Back to flows
        </Button>
      </div>
    );
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
  const handleRun = (paramValues?: Record<string, unknown>) => {
    if (!flowId) return;
    updateFlow.mutate(
      { id: flowId, body: { graph_json: buildGraph() } },
      {
        onSuccess: () => {
          markClean();
          createRun.mutate(
            { engine, parameters: paramValues },
            { onSuccess: (run) => navigate(`/runs/${run.id}`) },
          );
        },
      },
    );
  };

  return (
    <ReactFlowProvider>
      <div className="flex h-full flex-col">
        <EditorToolbar
          flowName={flow.name}
          onBack={() => confirmNavigation(() => navigate("/flows"))}
          onRename={() => setEditOpen(true)}
          projectName={projectName}
          isDisabled={isDisabled}
          dirty={dirty}
          validation={validation}
          onReEnable={() => toggleFlow.mutate({ id: flow.id, is_disabled: false })}
          toggleFlowPending={toggleFlow.isPending}
          canUndo={canUndo}
          canRedo={canRedo}
          onUndo={() => undo()}
          onRedo={() => redo()}
          previewOpen={previewOpen}
          onTogglePreview={() => setPreviewOpen(!previewOpen)}
          previewReason={previewReason}
          engine={engine}
          onEngineChange={(e) => {
            setEngine(e);
            markDirty();
          }}
          canRun={validation.canRun}
          createRunPending={createRun.isPending}
          runReason={runReason}
          onRun={() => (parameters.length > 0 ? setRunParamsOpen(true) : handleRun())}
          canExport={validation.canExport}
          onExport={() => setExportOpen(true)}
          parametersCount={parameters.length}
          onOpenParameters={() => setParamsOpen(true)}
          onOpenSchedule={() => setScheduleOpen(true)}
          onSave={handleSave}
          savePending={updateFlow.isPending}
        />

        {isDisabled && (
          <DisabledFlowBanner
            onReEnable={() => toggleFlow.mutate({ id: flow.id, is_disabled: false })}
          />
        )}

        <div className="flex min-h-0 flex-1">
          <NodePalette onAdd={handleAddNode} unlocked={inputReady} />
          <div className="flex min-w-0 flex-1 flex-col">
            <div className="min-h-0 flex-1">
              {graphReadyForFlowId === flow.id ? (
                <FlowCanvas key={flow.id} />
              ) : (
                <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" /> Loading…
                </div>
              )}
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

      <ParametersDialog
        open={paramsOpen}
        onOpenChange={setParamsOpen}
        value={parameters}
        onChange={(specs) => {
          setParameters(specs);
          markDirty();
        }}
      />

      <RunParametersDialog
        open={runParamsOpen}
        onOpenChange={setRunParamsOpen}
        specs={parameters}
        submitting={updateFlow.isPending || createRun.isPending}
        onSubmit={(values) => {
          setRunParamsOpen(false);
          handleRun(values);
        }}
      />

      <ScheduleFormDialog
        open={scheduleOpen}
        onOpenChange={setScheduleOpen}
        lockedFlowId={flow.id}
        parameterSpecs={parameters}
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
