// Single source of truth for "may this edge exist?" in the editor. The canvas
// (interactive connection dragging), the live handle-highlight overlay, and
// flow validation all answer compatibility questions here, so the rules can't
// drift apart between the three.

import {
  canConnectModelToTarget,
  getOutputHandles,
  isModelInputHandle,
  isModelOutputHandle,
  type NodeTypeDef,
} from "./nodeCatalog";

/** Every input handle a node exposes, required and optional alike. */
export function getInputHandles(def: NodeTypeDef): string[] {
  return [...def.inputHandles, ...(def.optionalInputHandles ?? [])];
}

/**
 * Whether an edge from `sourceDef.sourceHandle` to `targetDef.targetHandle`
 * is allowed by the node topology:
 *  - the source must emit something and the handle must be one it declares;
 *  - the target must accept input on that handle;
 *  - a model wire only connects a model output to a model input (never a model
 *    onto a data input, nor a dataframe onto a model input);
 *  - cross-validate only accepts unfitted model definitions, not train nodes.
 *
 * A null/undefined handle resolves like the runtime does: the source's primary
 * output handle, the "in" input handle. Cycle prevention is a graph question,
 * not a topology one, and stays with the caller.
 */
export function isCompatibleConnection(
  sourceDef: NodeTypeDef | undefined,
  sourceHandle: string | null | undefined,
  targetDef: NodeTypeDef | undefined,
  targetHandle: string | null | undefined,
): boolean {
  if (!sourceDef || !targetDef) return false;
  if (!sourceDef.hasOutput) return false;

  const outputs = getOutputHandles(sourceDef);
  const resolvedSource = sourceHandle ?? outputs[0];
  if (resolvedSource == null || !outputs.includes(resolvedSource)) return false;

  const inputs = getInputHandles(targetDef);
  const resolvedTarget = targetHandle ?? "in";
  if (!inputs.includes(resolvedTarget)) return false;

  const carriesModel = isModelOutputHandle(sourceDef, resolvedSource);
  const wantsModel = isModelInputHandle(targetDef, resolvedTarget);
  if (carriesModel !== wantsModel) return false;
  if (carriesModel && !canConnectModelToTarget(sourceDef, targetDef)) return false;

  return true;
}

export interface EdgeLike {
  source: string;
  target: string;
  sourceHandle?: string | null;
  targetHandle?: string | null;
}

/**
 * Whether `conn` already exists in `edges`. Handles are compared after
 * resolving null to the source's primary output handle / the "in" input
 * handle, so an imported edge stored without explicit handles still matches
 * its interactively-drawn twin. Distinct source handles (train vs test on a
 * split node) are distinct edges — both may target the same multi-input node.
 */
export function isDuplicateEdge(
  edges: EdgeLike[],
  conn: EdgeLike,
  primarySourceHandle = "out",
): boolean {
  const norm = (e: EdgeLike) =>
    `${e.source}|${e.sourceHandle ?? primarySourceHandle}|${e.target}|${e.targetHandle ?? "in"}`;
  const key = norm(conn);
  return edges.some((e) => e.source === conn.source && norm(e) === key);
}

/** Stable, collision-free id for a new edge. Includes the source handle so a
 *  split node's two outputs into the same multi-input target don't clash. */
export function buildEdgeId(conn: EdgeLike): string {
  return `e_${conn.source}_${conn.sourceHandle ?? "out"}_${conn.target}_${conn.targetHandle ?? "in"}`;
}

// ---- Live connection feedback ------------------------------------------------

/** The in-progress connection drag, published to the store by the canvas so
 *  every node can style its handles while the wire is being dragged. */
export interface PendingConnection {
  nodeId: string;
  /** Handle the drag started from (null for a node's single default handle). */
  handleId: string | null;
  /** Whether the drag started from a source (output) or target (input) handle. */
  handleType: "source" | "target";
  /** Node type of the drag's origin, captured so consumers don't need the node list. */
  nodeType: string;
}

export type HandleStatus = "idle" | "compatible" | "incompatible";

/**
 * How a specific handle should render while a connection is being dragged.
 * `handleKind` is what the handle IS on its own node ("source" = output,
 * "target" = input). Handles on the origin node stay idle; handles of the same
 * kind as the origin can never complete the wire, so they dim; opposite-kind
 * handles light up when `isCompatibleConnection` allows the pairing.
 */
export function handleCompatibility(
  pending: PendingConnection | null,
  pendingDef: NodeTypeDef | undefined,
  nodeId: string,
  nodeDef: NodeTypeDef | undefined,
  handleId: string,
  handleKind: "source" | "target",
): HandleStatus {
  if (!pending || !pendingDef || !nodeDef) return "idle";
  if (pending.nodeId === nodeId) return "idle";
  if (pending.handleType === handleKind) return "incompatible";
  const ok =
    pending.handleType === "source"
      ? isCompatibleConnection(pendingDef, pending.handleId, nodeDef, handleId)
      : isCompatibleConnection(nodeDef, handleId, pendingDef, pending.handleId);
  return ok ? "compatible" : "incompatible";
}

/** True when, during a drag, a node offers no handle that could complete the
 *  wire — the canvas dims the whole card so the eye skips it. */
export function nodeHasNoCompatibleHandle(
  pending: PendingConnection | null,
  pendingDef: NodeTypeDef | undefined,
  nodeId: string,
  nodeDef: NodeTypeDef | undefined,
): boolean {
  if (!pending || !pendingDef || !nodeDef) return false;
  if (pending.nodeId === nodeId) return false;
  const candidates =
    pending.handleType === "source" ? getInputHandles(nodeDef) : getOutputHandles(nodeDef);
  return !candidates.some(
    (h) =>
      handleCompatibility(
        pending,
        pendingDef,
        nodeId,
        nodeDef,
        h,
        pending.handleType === "source" ? "target" : "source",
      ) === "compatible",
  );
}
