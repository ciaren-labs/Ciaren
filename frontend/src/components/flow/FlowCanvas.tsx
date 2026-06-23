import { useCallback } from "react";
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
import { LayoutGrid } from "lucide-react";
import { nodeTypes } from "./nodeTypes";
import { NODE_DND_MIME } from "./NodePalette";
import { useFlowEditorStore } from "@/stores/flowEditorStore";
import { getNodeTypeDef } from "@/lib/nodeCatalog";
import { hasReadyInput, isInputType, wouldCreateCycle } from "@/lib/flowGraph";
import { createFlowNode } from "@/lib/createNode";
import { autoLayout } from "@/lib/autoLayout";

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
      if (!isInputType(def.type) && !hasReadyInput(nodes)) return;
      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });
      addNode(createFlowNode(def, position));
    },
    [nodes, screenToFlowPosition, addNode],
  );

  const handleAutoLayout = useCallback(() => {
    const laid = autoLayout(nodes, edges);
    setNodes(laid);
    // Double-rAF: first frame commits new positions, second lets React Flow
    // measure them, then fitView calculates against the real bounding box.
    requestAnimationFrame(() =>
      requestAnimationFrame(() =>
        fitView({ padding: 0.12, duration: 350, maxZoom: 1.5 })
      )
    );
  }, [nodes, edges, setNodes, fitView]);

  const minimapColor = (_node: Node) => "#a78bfa";

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
        fitViewOptions={{ padding: 0.12, maxZoom: 1.5 }}
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
        <Panel position="top-right">
          <button
            onClick={handleAutoLayout}
            title="Auto-arrange nodes"
            className="flex items-center gap-1.5 rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs font-medium shadow-sm hover:bg-accent transition-colors"
          >
            <LayoutGrid className="h-3.5 w-3.5" />
            Auto-arrange
          </button>
        </Panel>
      </ReactFlow>
    </div>
  );
}
