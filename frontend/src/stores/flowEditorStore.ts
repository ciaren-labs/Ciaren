// Local editor UI state. Server data (the persisted flow) lives in TanStack
// Query; this store only holds the in-progress, unsaved graph and panel state.
import { create } from "zustand";
import type {
  Edge,
  Node,
  OnEdgesChange,
  OnNodesChange,
} from "@xyflow/react";
import { applyEdgeChanges, applyNodeChanges } from "@xyflow/react";
import type { GraphNodeData } from "@/lib/types";

export type FlowNodeType = Node<GraphNodeData>;
export type FlowEdgeType = Edge;

interface FlowEditorState {
  nodes: FlowNodeType[];
  edges: FlowEdgeType[];
  selectedNodeId: string | null;
  sidebarOpen: boolean;
  previewOpen: boolean;
  dirty: boolean;
  /** Ids of nodes that currently have validation errors (for canvas badges). */
  invalidNodeIds: string[];

  setGraph: (nodes: FlowNodeType[], edges: FlowEdgeType[]) => void;
  setInvalidNodeIds: (ids: string[]) => void;
  onNodesChange: OnNodesChange<FlowNodeType>;
  onEdgesChange: OnEdgesChange<FlowEdgeType>;
  addNode: (node: FlowNodeType) => void;
  removeNode: (id: string) => void;
  setEdges: (edges: FlowEdgeType[]) => void;
  updateNodeConfig: (id: string, config: Record<string, unknown>) => void;
  updateNodeLabel: (id: string, label: string) => void;
  selectNode: (id: string | null) => void;
  setSidebarOpen: (open: boolean) => void;
  setPreviewOpen: (open: boolean) => void;
  markClean: () => void;
  reset: () => void;
}

export const useFlowEditorStore = create<FlowEditorState>((set) => ({
  nodes: [],
  edges: [],
  selectedNodeId: null,
  sidebarOpen: false,
  previewOpen: false,
  dirty: false,
  invalidNodeIds: [],

  setGraph: (nodes, edges) =>
    set({ nodes, edges, dirty: false, selectedNodeId: null }),

  setInvalidNodeIds: (ids) =>
    set((state) => {
      // Avoid spurious re-renders when the set hasn't actually changed.
      if (
        state.invalidNodeIds.length === ids.length &&
        state.invalidNodeIds.every((id, i) => id === ids[i])
      ) {
        return state;
      }
      return { invalidNodeIds: ids };
    }),

  onNodesChange: (changes) =>
    set((state) => ({
      nodes: applyNodeChanges(changes, state.nodes),
      dirty: true,
    })),

  onEdgesChange: (changes) =>
    set((state) => ({
      edges: applyEdgeChanges(changes, state.edges),
      dirty: true,
    })),

  addNode: (node) =>
    set((state) => ({
      nodes: [...state.nodes, node],
      selectedNodeId: node.id,
      sidebarOpen: true,
      dirty: true,
    })),

  removeNode: (id) =>
    set((state) => ({
      nodes: state.nodes.filter((n) => n.id !== id),
      edges: state.edges.filter((e) => e.source !== id && e.target !== id),
      selectedNodeId: state.selectedNodeId === id ? null : state.selectedNodeId,
      dirty: true,
    })),

  setEdges: (edges) => set({ edges, dirty: true }),

  updateNodeConfig: (id, config) =>
    set((state) => ({
      nodes: state.nodes.map((n) =>
        n.id === id
          ? { ...n, data: { ...n.data, config } }
          : n,
      ),
      dirty: true,
    })),

  updateNodeLabel: (id, label) =>
    set((state) => ({
      nodes: state.nodes.map((n) =>
        n.id === id ? { ...n, data: { ...n.data, label } } : n,
      ),
      dirty: true,
    })),

  selectNode: (id) =>
    set({ selectedNodeId: id, sidebarOpen: id !== null ? true : undefined }),

  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setPreviewOpen: (open) => set({ previewOpen: open }),
  markClean: () => set({ dirty: false }),
  reset: () =>
    set({
      nodes: [],
      edges: [],
      selectedNodeId: null,
      sidebarOpen: false,
      previewOpen: false,
      dirty: false,
      invalidNodeIds: [],
    }),
}));
