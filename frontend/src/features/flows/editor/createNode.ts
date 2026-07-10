// Factory for new editor nodes, shared by the palette (click-to-add) and the
// canvas (drag-and-drop). Keeping one implementation guarantees both paths
// produce identical node shapes and ids.

import type { NodeTypeDef } from "./nodeCatalog";
import type { FlowNodeType } from "@/stores/flowEditorStore";

let counter = 0;

/**
 * Build a fresh node for `def`. When a drop `position` is given the node lands
 * there; otherwise it is offset in a small cascade so click-added nodes don't
 * stack exactly on top of each other.
 */
export function createFlowNode(
  def: NodeTypeDef,
  position?: { x: number; y: number },
): FlowNodeType {
  counter += 1;
  const id = `${def.type}_${Date.now()}_${counter}`;
  return {
    id,
    type: def.type,
    position: position ?? {
      x: 140 + (counter % 5) * 48,
      y: 120 + (counter % 5) * 48,
    },
    data: {
      label: def.label,
      config: structuredClone(def.defaultConfig),
    },
  };
}
