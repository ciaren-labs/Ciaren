import type { EdgeTypes } from "@xyflow/react";
import { FlowEdge } from "./FlowEdge";

// FlowCanvas's defaultEdgeOptions sets every edge's type to "smoothstep"
// (React Flow merges that in for any edge lacking its own `type`), so that's
// the only key that matters; "default" is kept too in case an edge is ever
// created or imported with an explicit type.
export const edgeTypes: EdgeTypes = {
  smoothstep: FlowEdge,
  default: FlowEdge,
};
