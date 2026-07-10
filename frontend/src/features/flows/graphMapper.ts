// Maps between the persisted React-Flow-compatible GraphJson and the
// @xyflow runtime node/edge objects used by the editor store.
import type { GraphEdge, GraphJson, GraphNode } from "@/features/flows/types";
import type { FlowEdgeType, FlowNodeType } from "@/stores/flowEditorStore";

export function graphToStore(graph: GraphJson): {
  nodes: FlowNodeType[];
  edges: FlowEdgeType[];
} {
  const nodes: FlowNodeType[] = (graph.nodes ?? []).map((n: GraphNode) => ({
    id: n.id,
    type: n.type,
    // Nodes created outside the editor (raw API/SDK, malformed imports) may
    // omit position entirely — React Flow requires one to render.
    position: n.position ?? { x: 0, y: 0 },
    data: {
      label: n.data?.label ?? n.type,
      config: n.data?.config ?? {},
    },
  }));

  const edges: FlowEdgeType[] = (graph.edges ?? []).map((e: GraphEdge) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    sourceHandle: e.sourceHandle ?? undefined,
    targetHandle: e.targetHandle ?? undefined,
  }));

  return { nodes, edges };
}

export function storeToGraph(
  nodes: FlowNodeType[],
  edges: FlowEdgeType[],
): GraphJson {
  return {
    nodes: nodes.map((n) => ({
      id: n.id,
      type: n.type ?? "",
      position: n.position,
      data: {
        label: n.data.label,
        config: n.data.config,
      },
    })),
    edges: edges.map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      sourceHandle: e.sourceHandle ?? null,
      targetHandle: e.targetHandle ?? null,
    })),
  };
}
