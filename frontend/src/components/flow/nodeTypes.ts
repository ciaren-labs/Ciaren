import type { NodeTypes } from "@xyflow/react";
import { FlowNode } from "./FlowNode";
import { NODE_TYPES } from "@/features/flows/editor/nodeCatalog";

// Every node — built-in or plugin-contributed — renders with the shared FlowNode
// renderer. Plugin node types aren't known at build time (they come from the
// backend catalog at runtime), so a static map would leave them unregistered and
// React Flow would fall back to its plain "default" node (wrong handles, no config
// affordances). A Proxy returns FlowNode for *any* requested type, so plugin nodes
// render exactly like built-ins. React Flow looks types up lazily as
// `nodeTypes?.[type]` (it never enumerates keys for resolution), so the get-trap is
// all that's needed; the underlying object still carries the static keys for the
// dev-only types-changed warning. The object identity is stable across renders.
const base = Object.fromEntries(NODE_TYPES.map((n) => [n.type, FlowNode]));

export const nodeTypes: NodeTypes = new Proxy(base, {
  get(target, prop: string) {
    return Reflect.get(target, prop) ?? FlowNode;
  },
}) as NodeTypes;
