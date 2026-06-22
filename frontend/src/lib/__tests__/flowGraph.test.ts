import { describe, expect, it } from "vitest";
import {
  computeNodeColumns,
  hasCycle,
  isInputType,
  topologicalOrder,
  type GraphEdgeLike,
  type GraphNodeLike,
} from "../flowGraph";
import type { Dataset } from "../types";

function dataset(id: string, cols: string[], source: Dataset["source_type"] = "csv"): Dataset {
  return {
    id,
    name: `${id}.csv`,
    source_type: source,
    column_schema: cols.map((name) => ({ name, type: "string" })),
    data_sample: [],
    created_at: "",
    updated_at: "",
  };
}

function node(id: string, type: string, config: Record<string, unknown> = {}): GraphNodeLike {
  return { id, type, data: { config } };
}

function edge(source: string, target: string, targetHandle?: string): GraphEdgeLike {
  return { source, target, targetHandle: targetHandle ?? null };
}

describe("isInputType", () => {
  it("recognises input node types", () => {
    expect(isInputType("csvInput")).toBe(true);
    expect(isInputType("excelInput")).toBe(true);
    expect(isInputType("dropColumns")).toBe(false);
    expect(isInputType(undefined)).toBe(false);
  });
});

describe("topologicalOrder", () => {
  it("orders sources before targets", () => {
    const nodes = [node("a", "csvInput"), node("b", "dropColumns"), node("c", "csvOutput")];
    const edges = [edge("a", "b"), edge("b", "c")];
    const order = topologicalOrder(nodes, edges);
    expect(order.indexOf("a")).toBeLessThan(order.indexOf("b"));
    expect(order.indexOf("b")).toBeLessThan(order.indexOf("c"));
  });

  it("still returns every node when a cycle exists", () => {
    const nodes = [node("a", "dropColumns"), node("b", "dropColumns")];
    const edges = [edge("a", "b"), edge("b", "a")];
    expect(topologicalOrder(nodes, edges).sort()).toEqual(["a", "b"]);
  });
});

describe("hasCycle", () => {
  it("is false for a linear pipeline", () => {
    const nodes = [node("a", "csvInput"), node("b", "csvOutput")];
    expect(hasCycle(nodes, [edge("a", "b")])).toBe(false);
  });

  it("is true when nodes form a loop", () => {
    const nodes = [node("a", "dropColumns"), node("b", "dropColumns")];
    expect(hasCycle(nodes, [edge("a", "b"), edge("b", "a")])).toBe(true);
  });
});

describe("computeNodeColumns", () => {
  const datasets = [dataset("d1", ["name", "age", "score"])];

  it("seeds input nodes from the dataset schema", () => {
    const nodes = [node("in", "csvInput", { dataset_id: "d1" })];
    const cols = computeNodeColumns(nodes, [], datasets);
    expect(cols.get("in")?.output).toEqual(["name", "age", "score"]);
  });

  it("propagates columns and applies dropColumns", () => {
    const nodes = [
      node("in", "csvInput", { dataset_id: "d1" }),
      node("drop", "dropColumns", { columns: ["age"] }),
    ];
    const cols = computeNodeColumns(nodes, [edge("in", "drop")], datasets);
    expect(cols.get("drop")?.input).toEqual(["name", "age", "score"]);
    expect(cols.get("drop")?.output).toEqual(["name", "score"]);
  });

  it("applies selectColumns and renameColumns", () => {
    const nodes = [
      node("in", "csvInput", { dataset_id: "d1" }),
      node("sel", "selectColumns", { columns: ["name", "age"] }),
      node("ren", "renameColumns", { mapping: { name: "full_name" } }),
    ];
    const edges = [edge("in", "sel"), edge("sel", "ren")];
    const cols = computeNodeColumns(nodes, edges, datasets);
    expect(cols.get("sel")?.output).toEqual(["name", "age"]);
    expect(cols.get("ren")?.output).toEqual(["full_name", "age"]);
  });

  it("adds the calculated column to the output schema", () => {
    const nodes = [
      node("in", "csvInput", { dataset_id: "d1" }),
      node("calc", "calculatedColumn", { column_name: "total", expression: "age * 2" }),
    ];
    const cols = computeNodeColumns(nodes, [edge("in", "calc")], datasets);
    expect(cols.get("calc")?.output).toContain("total");
  });

  it("unions the two sides of a join", () => {
    const ds = [dataset("d1", ["id", "name"]), dataset("d2", ["id", "amount"])];
    const nodes = [
      node("l", "csvInput", { dataset_id: "d1" }),
      node("r", "csvInput", { dataset_id: "d2" }),
      node("j", "join", { on: "id", how: "inner" }),
    ];
    const edges = [edge("l", "j", "left"), edge("r", "j", "right")];
    const cols = computeNodeColumns(nodes, edges, ds);
    expect(cols.get("j")?.input.sort()).toEqual(["amount", "id", "name"]);
  });
});
