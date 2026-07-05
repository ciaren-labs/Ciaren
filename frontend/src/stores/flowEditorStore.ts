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
import type { GraphNodeData, ParameterSpec } from "@/lib/types";
import type { PendingConnection } from "@/lib/connectionRules";

export type FlowNodeType = Node<GraphNodeData>;
export type FlowEdgeType = Edge;

interface HistoryEntry {
  nodes: FlowNodeType[];
  edges: FlowEdgeType[];
}

// Cap the undo stack so a long editing session doesn't grow memory unbounded.
const HISTORY_LIMIT = 50;
// Rapid same-kind edits (dragging a node, typing in a config field) within
// this window collapse into a single undo step instead of one per tick.
const COALESCE_WINDOW_MS = 700;

interface FlowEditorState {
  nodes: FlowNodeType[];
  edges: FlowEdgeType[];
  /**
   * Bumped on every change to the graph's *structure* — node set, types,
   * configs, labels, edges — but NOT on position-only changes (drags) or
   * selection. Derived computations whose output doesn't depend on layout
   * (validation, column propagation, edge styling) key their memos on this
   * instead of `nodes`, so dragging stays O(1) per frame on large graphs.
   */
  structureVersion: number;
  selectedNodeId: string | null;
  sidebarOpen: boolean;
  previewOpen: boolean;
  dirty: boolean;
  /** Ids of nodes that currently have validation errors (for canvas badges). */
  invalidNodeIds: string[];
  /** Project the current flow belongs to — used to scope the dataset picker. */
  flowProjectId: string | null;
  /** Parameter specs declared on the current flow (graph_json.parameters). */
  parameters: ParameterSpec[];
  /** Origin of the connection currently being dragged, if any. Nodes read it
   *  to highlight compatible handles. Transient UI state: never dirties the
   *  flow and never enters the undo history. */
  pendingConnection: PendingConnection | null;

  /** Undo/redo stacks. Only nodes/edges are versioned — panel state isn't. */
  past: HistoryEntry[];
  future: HistoryEntry[];
  /** Internal bookkeeping for coalescing rapid edits (see COALESCE_WINDOW_MS). */
  historyGroupKey: string | null;
  historyGroupAt: number;

  setPendingConnection: (pending: PendingConnection | null) => void;
  setGraph: (nodes: FlowNodeType[], edges: FlowEdgeType[]) => void;
  setParameters: (parameters: ParameterSpec[]) => void;
  setInvalidNodeIds: (ids: string[]) => void;
  onNodesChange: OnNodesChange<FlowNodeType>;
  onEdgesChange: OnEdgesChange<FlowEdgeType>;
  addNode: (node: FlowNodeType) => void;
  /** Paste a cloned selection (nodes + their internal edges) as one undo step. */
  pasteSelection: (nodes: FlowNodeType[], edges: FlowEdgeType[]) => void;
  removeNode: (id: string) => void;
  setEdges: (edges: FlowEdgeType[]) => void;
  updateNodeConfig: (id: string, config: Record<string, unknown>) => void;
  patchMultipleNodeConfigs: (patches: Record<string, Record<string, unknown>>) => void;
  updateNodeLabel: (id: string, label: string) => void;
  selectNode: (id: string | null) => void;
  /** Untracked node positioning — used only for the one-time initial auto-layout
   *  on load, which isn't a user edit and shouldn't be on the undo stack. */
  setNodes: (nodes: FlowNodeType[]) => void;
  /** User-triggered re-layout (the Auto-arrange button) — undoable. */
  relayoutNodes: (nodes: FlowNodeType[]) => void;
  setFlowProjectId: (id: string | null) => void;
  setSidebarOpen: (open: boolean) => void;
  setPreviewOpen: (open: boolean) => void;
  markClean: () => void;
  markDirty: () => void;
  undo: () => void;
  redo: () => void;
  reset: () => void;
}

/** Push a checkpoint of the current nodes/edges onto `past`, unless this call
 *  belongs to the same edit "group" as the last one (e.g. the same drag or
 *  the same field being typed into) within the coalesce window — in which
 *  case history is left alone and only the group's timestamp is refreshed. */
function checkpoint(
  state: FlowEditorState,
  key: string,
): Pick<FlowEditorState, "past" | "future" | "historyGroupKey" | "historyGroupAt"> {
  const now = Date.now();
  if (state.historyGroupKey === key && now - state.historyGroupAt < COALESCE_WINDOW_MS) {
    return {
      past: state.past,
      future: state.future,
      historyGroupKey: key,
      historyGroupAt: now,
    };
  }
  return {
    past: [...state.past, { nodes: state.nodes, edges: state.edges }].slice(-HISTORY_LIMIT),
    future: [],
    historyGroupKey: key,
    historyGroupAt: now,
  };
}

const HISTORY_RESET = {
  past: [] as HistoryEntry[],
  future: [] as HistoryEntry[],
  historyGroupKey: null,
  historyGroupAt: 0,
};

export const useFlowEditorStore = create<FlowEditorState>((set) => ({
  nodes: [],
  edges: [],
  structureVersion: 0,
  selectedNodeId: null,
  sidebarOpen: false,
  previewOpen: false,
  dirty: false,
  invalidNodeIds: [],
  flowProjectId: null,
  parameters: [],
  pendingConnection: null,
  ...HISTORY_RESET,

  setPendingConnection: (pending) => set({ pendingConnection: pending }),

  setGraph: (nodes, edges) =>
    set((state) => ({
      nodes,
      edges,
      structureVersion: state.structureVersion + 1,
      dirty: false,
      selectedNodeId: null,
      pendingConnection: null,
      ...HISTORY_RESET,
    })),

  setParameters: (parameters) => set({ parameters }),

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
    set((state) => {
      // Selection-only changes aren't edits — don't touch history or `dirty`.
      const meaningful = changes.filter((c) => c.type !== "select");
      if (meaningful.length === 0) {
        return { nodes: applyNodeChanges(changes, state.nodes) };
      }
      // Drags and dimension changes move nodes without changing what the
      // graph *is* — they don't invalidate structure-keyed memos.
      const isLayoutOnly = meaningful.every((c) => c.type === "position" || c.type === "dimensions");
      const isPureDrag = meaningful.every((c) => c.type === "position");
      const draggedId =
        isPureDrag && meaningful[0].type === "position" ? meaningful[0].id : null;
      const key = isPureDrag ? `drag:${draggedId}` : `nodeschange:${Date.now()}`;
      return {
        ...checkpoint(state, key),
        nodes: applyNodeChanges(changes, state.nodes),
        structureVersion: isLayoutOnly ? state.structureVersion : state.structureVersion + 1,
        dirty: true,
      };
    }),

  onEdgesChange: (changes) =>
    set((state) => {
      const meaningful = changes.filter((c) => c.type !== "select");
      if (meaningful.length === 0) {
        return { edges: applyEdgeChanges(changes, state.edges) };
      }
      return {
        ...checkpoint(state, `edgeschange:${Date.now()}`),
        edges: applyEdgeChanges(changes, state.edges),
        structureVersion: state.structureVersion + 1,
        dirty: true,
      };
    }),

  addNode: (node) =>
    set((state) => ({
      ...checkpoint(state, `add:${Date.now()}`),
      nodes: [...state.nodes, node],
      structureVersion: state.structureVersion + 1,
      selectedNodeId: node.id,
      sidebarOpen: true,
      dirty: true,
    })),

  pasteSelection: (nodes, edges) =>
    set((state) => ({
      ...checkpoint(state, `paste:${Date.now()}`),
      // Deselect the originals so the pasted copy is the active selection.
      nodes: [...state.nodes.map((n) => ({ ...n, selected: false })), ...nodes],
      edges: [...state.edges, ...edges],
      structureVersion: state.structureVersion + 1,
      dirty: true,
    })),

  removeNode: (id) =>
    set((state) => ({
      ...checkpoint(state, `remove:${Date.now()}`),
      nodes: state.nodes.filter((n) => n.id !== id),
      structureVersion: state.structureVersion + 1,
      edges: state.edges.filter((e) => e.source !== id && e.target !== id),
      selectedNodeId: state.selectedNodeId === id ? null : state.selectedNodeId,
      dirty: true,
    })),

  setEdges: (edges) =>
    set((state) => ({
      ...checkpoint(state, `edges:${Date.now()}`),
      edges,
      structureVersion: state.structureVersion + 1,
      dirty: true,
    })),

  updateNodeConfig: (id, config) =>
    set((state) => ({
      ...checkpoint(state, `config:${id}`),
      nodes: state.nodes.map((n) =>
        n.id === id
          ? { ...n, data: { ...n.data, config } }
          : n,
      ),
      structureVersion: state.structureVersion + 1,
      dirty: true,
    })),

  patchMultipleNodeConfigs: (patches) =>
    set((state) => ({
      ...checkpoint(state, `patch:${Date.now()}`),
      nodes: state.nodes.map((n) =>
        n.id in patches ? { ...n, data: { ...n.data, config: patches[n.id] } } : n,
      ),
      structureVersion: state.structureVersion + 1,
      dirty: true,
    })),

  updateNodeLabel: (id, label) =>
    set((state) => ({
      ...checkpoint(state, `label:${id}`),
      nodes: state.nodes.map((n) =>
        n.id === id ? { ...n, data: { ...n.data, label } } : n,
      ),
      structureVersion: state.structureVersion + 1,
      dirty: true,
    })),

  selectNode: (id) =>
    set({ selectedNodeId: id, sidebarOpen: id !== null ? true : undefined }),

  setNodes: (nodes) => set({ nodes }),

  relayoutNodes: (nodes) =>
    set((state) => ({
      ...checkpoint(state, `layout:${Date.now()}`),
      nodes,
      dirty: true,
    })),

  setFlowProjectId: (id) => set({ flowProjectId: id }),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setPreviewOpen: (open) => set({ previewOpen: open }),
  markClean: () => set({ dirty: false }),
  markDirty: () => set({ dirty: true }),

  undo: () =>
    set((state) => {
      if (state.past.length === 0) return state;
      const previous = state.past[state.past.length - 1];
      return {
        past: state.past.slice(0, -1),
        future: [{ nodes: state.nodes, edges: state.edges }, ...state.future].slice(
          0,
          HISTORY_LIMIT,
        ),
        nodes: previous.nodes,
        edges: previous.edges,
        structureVersion: state.structureVersion + 1,
        selectedNodeId: null,
        dirty: true,
        historyGroupKey: null,
        historyGroupAt: 0,
      };
    }),

  redo: () =>
    set((state) => {
      if (state.future.length === 0) return state;
      const next = state.future[0];
      return {
        future: state.future.slice(1),
        past: [...state.past, { nodes: state.nodes, edges: state.edges }].slice(
          -HISTORY_LIMIT,
        ),
        nodes: next.nodes,
        edges: next.edges,
        structureVersion: state.structureVersion + 1,
        selectedNodeId: null,
        dirty: true,
        historyGroupKey: null,
        historyGroupAt: 0,
      };
    }),

  reset: () =>
    set((state) => ({
      nodes: [],
      edges: [],
      structureVersion: state.structureVersion + 1,
      selectedNodeId: null,
      sidebarOpen: false,
      previewOpen: false,
      dirty: false,
      invalidNodeIds: [],
      flowProjectId: null,
      parameters: [],
      pendingConnection: null,
      ...HISTORY_RESET,
    })),
}));
