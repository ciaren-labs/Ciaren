import { useCallback } from "react";
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  addEdge,
  useReactFlow,
  type Connection,
  type Edge,
  type IsValidConnection,
  type Node,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { nodeTypes } from "./nodeTypes";
import { NODE_DND_MIME } from "./NodePalette";
import { useFlowEditorStore } from "@/stores/flowEditorStore";
import { getNodeTypeDef, type NodeCategory } from "@/lib/nodeCatalog";
import { hasReadyInput, isInputType, wouldCreateCycle } from "@/lib/flowGraph";
import { createFlowNode } from "@/lib/createNode";

const MINIMAP_COLORS: Record<NodeCategory, string> = {
  input: "#10b981",
  clean: "#0ea5e9",
  transform: "#8b5cf6",
  output: "#f59e0b",
};

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
  const addNode = useFlowEditorStore((s) => s.addNode);
  const selectNode = useFlowEditorStore((s) => s.selectNode);
  const { screenToFlowPosition } = useReactFlow();

  const onConnect = useCallback(
    (connection: Connection) => {
      // Enforce handle topology: a single-input target can only have one
      // incoming edge per handle; join uses left/right; concatRows allows many.
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

  // Guard which connections are allowed. Fan-out (one source → many targets)
  // is intentionally permitted; self-loops, cycles, duplicates, and edges into
  // input nodes / out of output nodes are rejected.
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

  // Accept nodes dragged from the palette. Non-input nodes stay blocked until a
  // dataset-bound input exists (the same gate the palette enforces visually).
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
      if (!isInputType(def.type) && !hasReadyInput(nodes)) return;
      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });
      addNode(createFlowNode(def, position));
    },
    [nodes, screenToFlowPosition, addNode],
  );

  const minimapColor = (node: Node) => {
    const cat = getNodeTypeDef(node.type ?? "")?.category;
    return cat ? MINIMAP_COLORS[cat] : "#94a3b8";
  };

  return (
    <div className="canvas-surface h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
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
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={18} size={1} color="#cbd5e1" />
        <Controls className="!rounded-lg !border !border-border !shadow-sm" showInteractive={false} />
        <MiniMap
          pannable
          zoomable
          nodeColor={minimapColor}
          className="!rounded-lg !border !border-border"
        />
      </ReactFlow>
    </div>
  );
}
