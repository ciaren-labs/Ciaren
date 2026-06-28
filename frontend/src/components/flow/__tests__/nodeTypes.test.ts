import { describe, expect, it } from "vitest";
import { nodeTypes } from "../nodeTypes";
import { FlowNode } from "../FlowNode";

describe("nodeTypes registration", () => {
  it("resolves built-in node types to FlowNode", () => {
    expect(nodeTypes["filterRows"]).toBe(FlowNode);
  });

  it("resolves unknown (plugin-contributed) node types to FlowNode too", () => {
    // A plugin node type isn't known at build time; React Flow looks it up as
    // nodeTypes[type] at render, so the proxy must return FlowNode for any type
    // (otherwise React Flow falls back to its plain default node).
    expect(nodeTypes["acme.customNode"]).toBe(FlowNode);
    expect(nodeTypes["whatever_123"]).toBe(FlowNode);
  });
});
