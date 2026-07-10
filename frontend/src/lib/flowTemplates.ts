// Starter flow templates offered when creating a new flow — dataset-agnostic
// pipeline skeletons (an unconfigured File Input through a few common
// transforms to a File Output) that save a few clicks for common ETL shapes.
// Distinct from the backend's ML demo/seed flows (app/demo/flows.py), which
// are pre-loaded example runs rather than creation-time starting points.
import { Columns3, Filter, ShieldCheck, Sparkles, type LucideIcon } from "lucide-react";
import { getNodeTypeDef } from "@/features/flows/editor/nodeCatalog";
import { createFlowNode } from "@/features/flows/editor/createNode";
import type { GraphEdge, GraphJson, GraphNode } from "@/features/flows/types";

export interface FlowTemplate {
  id: string;
  name: string;
  description: string;
  icon: LucideIcon;
  /** Node types in pipeline order — wired source -> target linearly. */
  nodeTypes: string[];
}

export const FLOW_TEMPLATES: FlowTemplate[] = [
  {
    id: "clean-dedupe",
    name: "Clean & Deduplicate",
    description: "Drop null rows, then remove duplicates.",
    icon: Sparkles,
    nodeTypes: ["fileInput", "dropNulls", "removeDuplicates", "fileOutput"],
  },
  {
    id: "filter-aggregate",
    name: "Filter & Aggregate",
    description: "Keep rows matching a condition, then group and summarize.",
    icon: Filter,
    nodeTypes: ["fileInput", "filterRows", "groupByAggregate", "fileOutput"],
  },
  {
    id: "data-quality",
    name: "Data Quality Checks",
    description: "Assert no nulls or duplicate keys before writing out.",
    icon: ShieldCheck,
    nodeTypes: ["fileInput", "assertNotNull", "assertUnique", "fileOutput"],
  },
  {
    id: "tidy-columns",
    name: "Tidy Columns",
    description: "Rename columns and keep only the ones you need.",
    icon: Columns3,
    nodeTypes: ["fileInput", "renameColumns", "selectColumns", "fileOutput"],
  },
];

const NODE_SPACING_X = 260;
const ROW_Y = 160;

/** Builds a ready-to-save graph for a template: real node defaults from the
 *  catalog (so it stays in sync if defaults change), positioned in a row and
 *  wired source -> target. Input/filter/column fields are left at their
 *  defaults for the user to fill in once they pick a dataset. */
export function buildTemplateGraph(template: FlowTemplate): GraphJson {
  const flowNodes = template.nodeTypes.map((type, i) => {
    const def = getNodeTypeDef(type);
    if (!def) throw new Error(`Unknown template node type: ${type}`);
    return createFlowNode(def, { x: 80 + i * NODE_SPACING_X, y: ROW_Y });
  });

  const nodes: GraphNode[] = flowNodes.map((n) => ({
    id: n.id,
    type: n.type ?? "",
    position: n.position,
    data: { label: n.data.label, config: n.data.config },
  }));

  const edges: GraphEdge[] = flowNodes.slice(1).map((node, i) => {
    const source = flowNodes[i];
    return { id: `e_${source.id}_${node.id}`, source: source.id, target: node.id };
  });

  return { nodes, edges };
}
