import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  Panel,
  addEdge,
  useReactFlow,
  type Connection,
  type Edge,
  type IsValidConnection,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { ChevronDown, LayoutGrid } from "lucide-react";
import { nodeTypes } from "./nodeTypes";
import { NODE_DND_MIME } from "./NodePalette";
import { useFlowEditorStore } from "@/stores/flowEditorStore";
import {
  canConnectModelToTarget,
  getNodeTypeDef,
  isModelInputHandle,
  isModelOutputHandle,
} from "@/lib/nodeCatalog";
import { hasReadyInput, isFlowStartNode, wouldCreateCycle } from "@/lib/flowGraph";
import { createFlowNode } from "@/lib/createNode";
import { applyLayout, DEFAULT_LAYOUT, LAYOUT_OPTIONS, type LayoutKind } from "@/lib/autoLayout";
import { cn } from "@/lib/utils";

const defaultEdgeOptions = {
  type: "smoothstep" as const,
  animated: true,
};

/**
 * The @xyflow canvas. All graph mutations are funneled through the zustand
 * editor store so the rest of the app reads a single source of truth.
 */
export function FlowCanvas() {
  const nodes = useFlowEditorStore((s) => s.nodes);
  const edges = useFlowEditorStore((s) => s.edges);
  const onNodesChange = useFlowEditorStore((s) => s.onNodesChange);
  const onEdgesChange = useFlowEditorStore((s) => s.onEdgesChange);
  const setEdges = useFlowEditorStore((s) => s.setEdges);
  const setNodes = useFlowEditorStore((s) => s.setNodes);
  const relayoutNodes = useFlowEditorStore((s) => s.relayoutNodes);
  const addNode = useFlowEditorStore((s) => s.addNode);
  const selectNode = useFlowEditorStore((s) => s.selectNode);
  const { screenToFlowPosition, fitView } = useReactFlow();

  const onConnect = useCallback(
    (connection: Connection) => {
      const targetDef = getNodeTypeDef(
        nodes.find((n) => n.id === connection.target)?.type ?? "",
      );
      let nextEdges = edges;
      if (targetDef && !targetDef.multiInput) {
        nextEdges = edges.filter(
          (e) =>
            !(
              e.target === connection.target &&
              (e.targetHandle ?? null) === (connection.targetHandle ?? null)
            ),
        );
      }
      const newEdge: Edge = {
        ...connection,
        id: `e_${connection.source}_${connection.target}_${
          connection.targetHandle ?? "in"
        }`,
      };
      setEdges(addEdge(newEdge, nextEdges));
    },
    [edges, nodes, setEdges],
  );

  const isValidConnection = useCallback<IsValidConnection>(
    (conn) => {
      if (!conn.source || !conn.target || conn.source === conn.target) return false;
      const sourceDef = getNodeTypeDef(
        nodes.find((n) => n.id === conn.source)?.type ?? "",
      );
      const targetDef = getNodeTypeDef(
        nodes.find((n) => n.id === conn.target)?.type ?? "",
      );
      if (!sourceDef?.hasOutput) return false;
      if (!targetDef || targetDef.inputHandles.length === 0) return false;
      // A model wire only connects a model output to a model input (and vice
      // versa) — mirrors the backend guard so a model can't be dropped onto a
      // data input or a dataframe onto a model input.
      if (
        isModelOutputHandle(sourceDef, conn.sourceHandle) !==
        isModelInputHandle(targetDef, conn.targetHandle)
      ) {
        return false;
      }
      if (
        isModelOutputHandle(sourceDef, conn.sourceHandle) &&
        isModelInputHandle(targetDef, conn.targetHandle) &&
        !canConnectModelToTarget(sourceDef, targetDef)
      ) {
        return false;
      }
      const duplicate = edges.some(
        (e) =>
          e.source === conn.source &&
          e.target === conn.target &&
          (e.targetHandle ?? null) === (conn.targetHandle ?? null),
      );
      if (duplicate) return false;
      return !wouldCreateCycle(edges, conn.source, conn.target);
    },
    [nodes, edges],
  );

  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const type = event.dataTransfer.getData(NODE_DND_MIME);
      const def = getNodeTypeDef(type);
      if (!def) return;
      if (!isFlowStartNode(def.type) && !hasReadyInput(nodes)) return;
      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });
      addNode(createFlowNode(def, position));
    },
    [nodes, screenToFlowPosition, addNode],
  );

  const didInitialLayout = useRef(false);
  useEffect(() => {
    if (nodes.length === 0 || didInitialLayout.current) return;
    didInitialLayout.current = true;
    requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        const laid = applyLayout(DEFAULT_LAYOUT, nodes, edges);
        setNodes(laid);
        requestAnimationFrame(() =>
          requestAnimationFrame(() =>
            fitView({ padding: 0.12, duration: 350, maxZoom: 1.5 })
          )
        );
      })
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes.length]);

  const [layoutMenuOpen, setLayoutMenuOpen] = useState(false);
  // Remember the last layout the user picked so the main button reapplies it.
  const [lastLayout, setLastLayout] = useState<LayoutKind>(DEFAULT_LAYOUT);

  const handleAutoLayout = useCallback(
    (kind: LayoutKind) => {
      setLastLayout(kind);
      setLayoutMenuOpen(false);
      const laid = applyLayout(kind, nodes, edges);
      relayoutNodes(laid);
      // Double-rAF: first frame commits new positions, second lets React Flow
      // measure them, then fitView calculates against the real bounding box.
      requestAnimationFrame(() =>
        requestAnimationFrame(() =>
          fitView({ padding: 0.12, duration: 350, maxZoom: 1.5 })
        )
      );
    },
    [nodes, edges, relayoutNodes, fitView],
  );

  const minimapColor = (_node: Node) => "#a78bfa";

  // Edges leaving a "model" output (mlTrain → mlPredict/featureImportance) carry a
  // model reference, not data — draw them purple and non-animated to read at a
  // glance: blue = data flow, purple = model flow. Resolve via the source node's
  // def so a single-output model edge (no explicit sourceHandle, e.g. seeded or
  // imported flows) is still recognised as a model wire.
  const styledEdges = useMemo(
    () =>
      edges.map((e) => {
        const sourceDef = getNodeTypeDef(
          nodes.find((n) => n.id === e.source)?.type ?? "",
        );
        return sourceDef && isModelOutputHandle(sourceDef, e.sourceHandle)
          ? { ...e, animated: false, style: { ...e.style, stroke: "#a855f7", strokeWidth: 2 } }
          : e;
      }),
    [edges, nodes],
  );

  return (
    <div className="canvas-surface h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={styledEdges}
        nodeTypes={nodeTypes}
        defaultEdgeOptions={defaultEdgeOptions}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        isValidConnection={isValidConnection}
        onNodeClick={(_, node) => selectNode(node.id)}
        onPaneClick={() => selectNode(null)}
        onDrop={onDrop}
        onDragOver={onDragOver}
        fitView
        fitViewOptions={{ padding: 0.12, maxZoom: 1.5 }}
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={18}
          size={1}
          color="hsl(var(--canvas-dot))"
        />
        <Controls className="!rounded-lg !border !border-border !shadow-sm" showInteractive={false} />
        <MiniMap
          pannable
          zoomable
          nodeColor={minimapColor}
          className="!rounded-lg !border !border-border"
        />
        <Panel position="top-right">
          <div className="relative flex items-stretch rounded-lg border border-border bg-background shadow-sm">
            <button
              onClick={() => handleAutoLayout(lastLayout)}
              title="Auto-arrange nodes"
              className="flex items-center gap-1.5 rounded-l-lg px-2.5 py-1.5 text-xs font-medium hover:bg-accent transition-colors"
            >
              <LayoutGrid className="h-3.5 w-3.5" />
              Auto-arrange
            </button>
            <button
              onClick={() => setLayoutMenuOpen((o) => !o)}
              title="Choose a layout"
              aria-label="Choose a layout"
              className="flex items-center border-l border-border px-1.5 hover:bg-accent transition-colors rounded-r-lg"
            >
              <ChevronDown className="h-3.5 w-3.5" />
            </button>
            {layoutMenuOpen && (
              <>
                {/* click-away */}
                <div className="fixed inset-0 z-10" onClick={() => setLayoutMenuOpen(false)} />
                <div className="absolute right-0 top-full z-20 mt-1 w-52 overflow-hidden rounded-lg border border-border bg-background py-1 shadow-md">
                  {LAYOUT_OPTIONS.map((opt) => (
                    <button
                      key={opt.kind}
                      onClick={() => handleAutoLayout(opt.kind)}
                      className={cn(
                        "flex w-full flex-col items-start px-3 py-1.5 text-left transition-colors hover:bg-accent",
                        opt.kind === lastLayout && "bg-accent/50",
                      )}
                    >
                      <span className="text-xs font-medium">{opt.label}</span>
                      <span className="text-[10px] text-muted-foreground">{opt.hint}</span>
                    </button>
                  ))}
                </div>
              </>
            )}
          </div>
        </Panel>
      </ReactFlow>
    </div>
  );
}
