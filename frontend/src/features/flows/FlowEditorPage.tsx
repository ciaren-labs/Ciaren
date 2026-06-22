import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ReactFlowProvider } from "@xyflow/react";
import { useFlow, useUpdateFlow } from "./hooks";
import { useFlowEditorStore } from "@/stores/flowEditorStore";
import { graphToStore, storeToGraph } from "./graphMapper";
import { type NodeTypeDef } from "@/lib/nodeCatalog";
import { FlowCanvas } from "@/components/flow/FlowCanvas";
import { NodePalette } from "@/components/flow/NodePalette";
import { NodeSidebar } from "@/components/flow/NodeSidebar";
import { PreviewPanel } from "@/components/flow/PreviewPanel";
import { ExportCodeDialog } from "./ExportCodeDialog";
import { RunPanel } from "@/features/runs/RunPanel";
import { Button } from "@/components/ui/button";

let nodeCounter = 0;

export function FlowEditorPage() {
  const { flowId } = useParams<{ flowId: string }>();
  const navigate = useNavigate();
  const { data: flow, isLoading } = useFlow(flowId ?? null);
  const updateFlow = useUpdateFlow();

  const setGraph = useFlowEditorStore((s) => s.setGraph);
  const addNode = useFlowEditorStore((s) => s.addNode);
  const reset = useFlowEditorStore((s) => s.reset);
  const dirty = useFlowEditorStore((s) => s.dirty);
  const markClean = useFlowEditorStore((s) => s.markClean);
  const previewOpen = useFlowEditorStore((s) => s.previewOpen);
  const setPreviewOpen = useFlowEditorStore((s) => s.setPreviewOpen);

  const [exportOpen, setExportOpen] = useState(false);
  const [runOpen, setRunOpen] = useState(false);

  // Load the persisted graph into the editor store once fetched.
  useEffect(() => {
    if (flow?.graph_json) {
      const { nodes, edges } = graphToStore(flow.graph_json);
      setGraph(nodes, edges);
    } else if (flow) {
      setGraph([], []);
    }
    return () => reset();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [flow?.id]);

  const handleAddNode = (def: NodeTypeDef) => {
    nodeCounter += 1;
    const id = `${def.type}_${Date.now()}_${nodeCounter}`;
    addNode({
      id,
      type: def.type,
      position: {
        x: 120 + (nodeCounter % 5) * 40,
        y: 120 + (nodeCounter % 5) * 40,
      },
      data: {
        label: def.label,
        config: structuredClone(def.defaultConfig),
      },
    });
  };

  const handleSave = () => {
    if (!flowId) return;
    const graph = storeToGraph(
      useFlowEditorStore.getState().nodes,
      useFlowEditorStore.getState().edges,
    );
    updateFlow.mutate(
      { id: flowId, body: { graph_json: graph } },
      { onSuccess: () => markClean() },
    );
  };

  if (isLoading) {
    return <div className="p-6 text-sm text-muted-foreground">Loading…</div>;
  }
  if (!flow) {
    return <div className="p-6 text-sm text-destructive">Flow not found.</div>;
  }

  return (
    <ReactFlowProvider>
      <div className="flex h-full flex-col">
        <div className="flex items-center justify-between border-b border-border px-4 py-2">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/")}
            >
              ← Flows
            </Button>
            <h1 className="text-sm font-semibold">{flow.name}</h1>
            {dirty && (
              <span className="text-[11px] text-amber-600">
                unsaved changes
              </span>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => setPreviewOpen(!previewOpen)}
            >
              {previewOpen ? "Hide preview" : "Preview"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setRunOpen(true)}
            >
              Run
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setExportOpen(true)}
            >
              Export Python
            </Button>
            <Button
              size="sm"
              onClick={handleSave}
              disabled={updateFlow.isPending}
            >
              {updateFlow.isPending ? "Saving…" : "Save"}
            </Button>
          </div>
        </div>

        <div className="flex min-h-0 flex-1">
          <NodePalette onAdd={handleAddNode} />
          <div className="flex min-w-0 flex-1 flex-col">
            <div className="min-h-0 flex-1">
              <FlowCanvas />
            </div>
            {previewOpen && (
              <PreviewPanel
                flowId={flow.id}
                onClose={() => setPreviewOpen(false)}
              />
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
      <RunPanel flowId={flow.id} open={runOpen} onOpenChange={setRunOpen} />
    </ReactFlowProvider>
  );
}
