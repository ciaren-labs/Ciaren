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
  type OnConnectStart,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { ChevronDown, LayoutGrid } from "lucide-react";
import { nodeTypes } from "./nodeTypes";
import { NODE_DND_MIME } from "./NodePalette";
import { useFlowEditorStore } from "@/stores/flowEditorStore";
import type { FlowEdgeType, FlowNodeType } from "@/stores/flowEditorStore";
import { getNodeTypeDef, getOutputHandles, isModelOutputHandle } from "@/lib/nodeCatalog";
import {
  buildEdgeId,
  isCompatibleConnection,
  isDuplicateEdge,
} from "@/lib/connectionRules";
import { cloneSelection, hasReadyInput, isFlowStartNode, wouldCreateCycle } from "@/lib/flowGraph";
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
        // Normalize null → "in" like the runtime does, so an imported edge
        // stored without an explicit handle is still replaced (not doubled up)
        // when the user drops a new wire on the same single-input handle.
        nextEdges = edges.filter(
          (e) =>
            !(
              e.target === connection.target &&
              (e.targetHandle ?? "in") === (connection.targetHandle ?? "in")
            ),
        );
      }
      const newEdge: Edge = { ...connection, id: buildEdgeId(connection) };
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
      // Topology rules (model wires, declared handles, CV restriction) live in
      // connectionRules so validation and the drag highlight share them.
      if (!isCompatibleConnection(sourceDef, conn.sourceHandle, targetDef, conn.targetHandle)) {
        return false;
      }
      // Duplicate detection keys on the source handle too: a split node's
      // "train" and "test" outputs are distinct edges even to the same target.
      if (
        sourceDef &&
        isDuplicateEdge(edges, conn, getOutputHandles(sourceDef)[0])
      ) {
        return false;
      }
      return !wouldCreateCycle(edges, conn.source, conn.target);
    },
    [nodes, edges],
  );

  // While a wire is being dragged, publish its origin so every node can light
  // up compatible handles and dim incompatible ones (see FlowNode).
  const setPendingConnection = useFlowEditorStore((s) => s.setPendingConnection);
  const onConnectStart = useCallback<OnConnectStart>(
    (_event, { nodeId, handleId, handleType }) => {
      if (!nodeId || !handleType) return;
      setPendingConnection({
        nodeId,
        handleId: handleId ?? null,
        handleType,
        nodeType: nodes.find((n) => n.id === nodeId)?.type ?? "",
      });
    },
    [nodes, setPendingConnection],
  );
  const onConnectEnd = useCallback(() => setPendingConnection(null), [setPendingConnection]);

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

  // Copy/paste of the selected nodes (plus the edges between them). The
  // clipboard is a ref, not OS clipboard: node configs may reference local
  // datasets, so they're only meaningful inside this editor session anyway.
  const clipboardRef = useRef<{ nodes: FlowNodeType[]; edges: FlowEdgeType[] } | null>(null);
  // How many times the current clipboard has been pasted — each paste lands a
  // step further so repeated pastes don't stack pixel-identically.
  const pasteCountRef = useRef(0);
  const pasteSelection = useFlowEditorStore((s) => s.pasteSelection);
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (!(e.ctrlKey || e.metaKey)) return;
      // Plain Ctrl/Cmd only: combos like Ctrl+Shift+V (paste without
      // formatting) or Ctrl+Alt+V belong to the browser/OS, not the canvas.
      if (e.shiftKey || e.altKey) return;
      const target = e.target as HTMLElement | null;
      // Never hijack copy/paste from form fields or editable content.
      if (target && (target.closest("input, textarea, select, [contenteditable=true]") !== null)) return;
      const key = e.key.toLowerCase();
      if (key === "c") {
        // Copying selected page text must win over the node clipboard.
        const selection = window.getSelection();
        if (selection && !selection.isCollapsed) return;
        const selected = nodes.filter((n) => n.selected);
        if (selected.length === 0) return;
        const ids = new Set(selected.map((n) => n.id));
        clipboardRef.current = {
          nodes: structuredClone(selected),
          edges: structuredClone(edges.filter((ed) => ids.has(ed.source) && ids.has(ed.target))),
        };
        pasteCountRef.current = 0;
      } else if (key === "v") {
        if (!clipboardRef.current) return;
        pasteCountRef.current += 1;
        const cloned = cloneSelection(
          clipboardRef.current.nodes,
          clipboardRef.current.edges,
          32 * pasteCountRef.current,
        );
        pasteSelection(cloned.nodes, cloned.edges);
      } else if (key === "d") {
        // Ctrl+D: duplicate the selection in place (copy+paste in one).
        const selected = nodes.filter((n) => n.selected);
        if (selected.length === 0) return;
        e.preventDefault();
        const ids = new Set(selected.map((n) => n.id));
        const cloned = cloneSelection(
          selected,
          edges.filter((ed) => ids.has(ed.source) && ids.has(ed.target)),
        );
        pasteSelection(cloned.nodes, cloned.edges);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [nodes, edges, pasteSelection]);

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
  // Two memos: the id→type Map only changes with graph structure (keyed on
  // structureVersion, so node drags don't rebuild it), while styledEdges must
  // follow the `edges` array's own identity — select-only edge changes replace
  // it without bumping structureVersion, and a stale cached array here would
  // make edges unselectable (and thus undeletable) in controlled mode.
  const structureVersion = useFlowEditorStore((s) => s.structureVersion);
  const typeById = useMemo(
    () => new Map(nodes.map((n) => [n.id, n.type ?? ""])),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- structureVersion tracks the node set structurally
    [structureVersion],
  );
  const styledEdges = useMemo(
    () =>
      edges.map((e) => {
        const sourceDef = getNodeTypeDef(typeById.get(e.source) ?? "");
        return sourceDef && isModelOutputHandle(sourceDef, e.sourceHandle)
          ? { ...e, animated: false, style: { ...e.style, stroke: "#a855f7", strokeWidth: 2 } }
          : e;
      }),
    [edges, typeById],
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
        onConnectStart={onConnectStart}
        onConnectEnd={onConnectEnd}
        onClickConnectStart={onConnectStart}
        onClickConnectEnd={onConnectEnd}
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
