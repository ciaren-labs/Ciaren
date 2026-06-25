import { useMemo } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  ReactFlow,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { RunDagNode, type RunDagNodeType } from "./RunDagNode";
import { getNodeTypeDef, isModelOutputHandle } from "@/lib/nodeCatalog";
import type { GraphJson, NodeResult } from "@/lib/types";

const nodeTypes = { runNode: RunDagNode };

interface RunDagProps {
  graph: GraphJson;
  results: NodeResult[];
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string | null) => void;
}

/**
 * Read-only DAG of a finished run. The layout/edges come from the flow's graph;
 * each node is decorated with its recorded execution status and row count.
 */
export function RunDag({ graph, results, selectedNodeId, onSelectNode }: RunDagProps) {
  const resultsById = useMemo(
    () => new Map(results.map((r) => [r.node_id, r])),
    [results],
  );

  const nodes: RunDagNodeType[] = useMemo(
    () =>
      graph.nodes.map((n) => {
        const result = resultsById.get(n.id);
        return {
          id: n.id,
          type: "runNode",
          position: n.position,
          selected: n.id === selectedNodeId,
          data: {
            label: n.data?.label ?? n.type,
            nodeType: n.type,
            status: result?.status ?? "unknown",
            rows: result?.rows ?? null,
          },
        };
      }),
    [graph.nodes, resultsById, selectedNodeId],
  );

  const typeById = useMemo(
    () => new Map(graph.nodes.map((n) => [n.id, n.type])),
    [graph.nodes],
  );

  const edges: Edge[] = useMemo(
    () =>
      graph.edges.map((e) => {
        // Model-reference edges read purple, matching the editor canvas. Resolve
        // via the source node's def so a single-output model edge (no explicit
        // sourceHandle, e.g. seeded/imported flows) is still recognised.
        const sourceDef = getNodeTypeDef(typeById.get(e.source) ?? "");
        const isModel = !!sourceDef && isModelOutputHandle(sourceDef, e.sourceHandle);
        return {
          id: e.id,
          source: e.source,
          target: e.target,
          sourceHandle: e.sourceHandle ?? undefined,
          targetHandle: e.targetHandle ?? undefined,
          type: "smoothstep",
          animated: false,
          ...(isModel ? { style: { stroke: "#a855f7", strokeWidth: 2 } } : {}),
        };
      }),
    [graph.edges, typeById],
  );

  return (
    <div className="canvas-surface h-full w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        nodesDraggable={false}
        nodesConnectable={false}
        edgesFocusable={false}
        onNodeClick={(_, node) => onSelectNode(node.id)}
        onPaneClick={() => onSelectNode(null)}
        fitView
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={18} size={1} color="#d8cdf0" />
        <Controls showInteractive={false} className="!rounded-lg !border !border-border !shadow-sm" />
      </ReactFlow>
    </div>
  );
}
