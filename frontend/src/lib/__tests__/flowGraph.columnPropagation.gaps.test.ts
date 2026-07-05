// AUDIT REPRO — outputColumns() in flowGraph.ts handles some column-adding
// transforms (calculatedColumn, binColumn, extractDateParts, …) but not others
// (windowFunction, conditionalColumn, mapValues with new_column, splitColumn).
// Downstream column pickers therefore never offer the very column those nodes
// create, and — combined with NodeSidebar's dataset-change cleanup — refs to
// those columns get wiped as "stale".
//
// Tests assert the CORRECT behaviour and are marked `.fails` so the suite
// stays green while the gap exists. Remove `.fails` after extending
// outputColumns() to see them pass.
import { describe, expect, it } from "vitest";
import { computeNodeColumns, type GraphEdgeLike, type GraphNodeLike } from "../flowGraph";
import type { Dataset } from "../types";

function dataset(id: string, cols: string[]): Dataset {
  return {
    id,
    name: `${id}.csv`,
    source_type: "csv",
    dataset_kind: "input",
    is_disabled: false,
    project_id: null,
    latest_version: 1,
    version_count: 1,
    column_schema: cols.map((name) => ({ name, type: "string" })),
    data_sample: [],
    column_profile: null,
    created_at: "",
    updated_at: "",
  };
}

function node(id: string, type: string, config: Record<string, unknown> = {}): GraphNodeLike {
  return { id, type, data: { config } };
}

const edge = (source: string, target: string): GraphEdgeLike => ({ source, target });

function inputColsOf(mid: GraphNodeLike): string[] {
  const nodes = [
    node("in", "csvInput", { dataset_id: "d1" }),
    mid,
    node("down", "sortRows", { columns: [] }),
  ];
  const edges = [edge("in", mid.id), edge(mid.id, "down")];
  const cols = computeNodeColumns(nodes, edges, [dataset("d1", ["a", "b"])]);
  return cols.get("down")?.input ?? [];
}

describe("column propagation for column-adding transforms (BUG repro)", () => {
  // Baseline: calculatedColumn IS handled — proves the harness works.
  it("propagates calculatedColumn's new column (baseline, passes today)", () => {
    expect(
      inputColsOf(node("m", "calculatedColumn", { column_name: "profit", expression: "a*2" })),
    ).toContain("profit");
  });

  it("propagates windowFunction's new_column", () => {
    expect(
      inputColsOf(
        node("m", "windowFunction", { function: "row_number", new_column: "rank", order_by: ["a"] }),
      ),
    ).toContain("rank");
  });

  it("propagates conditionalColumn's new_column", () => {
    expect(
      inputColsOf(node("m", "conditionalColumn", { new_column: "tier", rules: [], default: "x" })),
    ).toContain("tier");
  });

  it("propagates splitColumn's `into` columns", () => {
    expect(
      inputColsOf(
        node("m", "splitColumn", {
          column: "a",
          mode: "delimiter",
          delimiter: "-",
          into: ["first", "last"],
          keep_original: true,
        }),
      ),
    ).toEqual(expect.arrayContaining(["first", "last"]));
  });

  it("propagates mapValues' optional new_column", () => {
    expect(
      inputColsOf(node("m", "mapValues", { column: "a", new_column: "mapped", mapping: {} })),
    ).toContain("mapped");
  });
});
