import { describe, expect, it } from "vitest";
import { FLOW_TEMPLATES, buildTemplateGraph } from "../flowTemplates";
import { getNodeTypeDef } from "@/features/flows/editor/nodeCatalog";

describe("flowTemplates", () => {
  it.each(FLOW_TEMPLATES)("$id builds a valid, linearly-wired graph", (template) => {
    const graph = buildTemplateGraph(template);

    expect(graph.nodes).toHaveLength(template.nodeTypes.length);
    graph.nodes.forEach((node, i) => {
      expect(node.type).toBe(template.nodeTypes[i]);
      expect(node.id).toBeTruthy();
      // Positions must be distinct so nodes don't render stacked.
      expect(node.position.x).toBe(80 + i * 260);
    });

    // Every node id is unique.
    expect(new Set(graph.nodes.map((n) => n.id)).size).toBe(graph.nodes.length);

    // Wired as a straight chain: node[i] -> node[i+1], nothing more or less.
    expect(graph.edges).toHaveLength(template.nodeTypes.length - 1);
    graph.edges.forEach((edge, i) => {
      expect(edge.source).toBe(graph.nodes[i].id);
      expect(edge.target).toBe(graph.nodes[i + 1].id);
    });
  });

  it("starts with an input node and ends with an output node", () => {
    for (const template of FLOW_TEMPLATES) {
      const first = getNodeTypeDef(template.nodeTypes[0]);
      const last = getNodeTypeDef(template.nodeTypes[template.nodeTypes.length - 1]);
      expect(first?.category).toBe("input");
      expect(last?.category).toBe("output");
    }
  });

  it("every referenced node type exists in the catalog", () => {
    for (const template of FLOW_TEMPLATES) {
      for (const type of template.nodeTypes) {
        expect(getNodeTypeDef(type), `${template.id}: unknown node type "${type}"`).toBeDefined();
      }
    }
  });

  it("template ids are unique", () => {
    const ids = FLOW_TEMPLATES.map((t) => t.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
