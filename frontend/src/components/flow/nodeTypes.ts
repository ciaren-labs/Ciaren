import type { NodeTypes } from "@xyflow/react";
import { FlowNode } from "./FlowNode";
import { NODE_TYPES } from "@/lib/nodeCatalog";

// Register every catalog node type to render with the shared FlowNode renderer.
export const nodeTypes: NodeTypes = Object.fromEntries(
  NODE_TYPES.map((n) => [n.type, FlowNode]),
) as NodeTypes;
