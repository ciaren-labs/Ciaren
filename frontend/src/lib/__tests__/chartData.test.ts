import { describe, expect, it } from "vitest";
import {
  barData,
  correlationMatrix,
  histogram,
  numericColumns,
  pearson,
  toNumber,
  valueCounts,
  type Row,
} from "../chartData";

describe("toNumber", () => {
  it("coerces numeric strings and booleans, rejects non-numeric", () => {
    expect(toNumber(3)).toBe(3);
    expect(toNumber("4.5")).toBe(4.5);
    expect(toNumber(true)).toBe(1);
    expect(toNumber("abc")).toBeNull();
    expect(toNumber("")).toBeNull();
    expect(toNumber(null)).toBeNull();
  });
});

describe("numericColumns", () => {
  it("keeps mostly-numeric columns and drops text columns", () => {
    const rows: Row[] = [
      { a: 1, b: "x", c: "10" },
      { a: 2, b: "y", c: "20" },
      { a: 3, b: "z", c: "30" },
    ];
    expect(numericColumns(rows, ["a", "b", "c"]).sort()).toEqual(["a", "c"]);
  });
});

describe("histogram", () => {
  it("buckets values into equal-width bins, max in last bin", () => {
    const rows: Row[] = [0, 1, 2, 3, 4].map((v) => ({ x: v }));
    const bins = histogram(rows, "x", 2);
    expect(bins).toHaveLength(2);
    // counts must sum to the number of finite values
    expect(bins.reduce((s, b) => s + b.count, 0)).toBe(5);
    // the maximum (4) lands in the final bin
    expect(bins[bins.length - 1].count).toBeGreaterThan(0);
  });

  it("collapses a constant column to one bucket", () => {
    const rows: Row[] = [{ x: 7 }, { x: 7 }];
    const bins = histogram(rows, "x", 5);
    expect(bins).toHaveLength(1);
    expect(bins[0].count).toBe(2);
  });
});

describe("pearson / correlationMatrix", () => {
  it("returns +1 for a perfectly positive linear relationship", () => {
    expect(pearson([1, 2, 3], [2, 4, 6])).toBeCloseTo(1, 5);
  });

  it("returns -1 for a perfectly negative relationship", () => {
    expect(pearson([1, 2, 3], [6, 4, 2])).toBeCloseTo(-1, 5);
  });

  it("ignores rows where either value is null", () => {
    expect(pearson([1, null, 3], [2, 9, 6])).toBeCloseTo(1, 5);
  });

  it("produces a symmetric matrix with a unit diagonal", () => {
    const rows: Row[] = [
      { a: 1, b: 2 },
      { a: 2, b: 4 },
      { a: 3, b: 6 },
    ];
    const { columns, matrix } = correlationMatrix(rows, ["a", "b"]);
    expect(columns).toEqual(["a", "b"]);
    expect(matrix[0][0]).toBeCloseTo(1, 5);
    expect(matrix[1][1]).toBeCloseTo(1, 5);
    expect(matrix[0][1]).toBeCloseTo(matrix[1][0], 5);
    expect(matrix[0][1]).toBeCloseTo(1, 5);
  });
});

describe("barData", () => {
  it("rolls a value column up by category", () => {
    const rows: Row[] = [
      { cat: "a", v: 1 },
      { cat: "a", v: 3 },
      { cat: "b", v: 10 },
    ];
    const sum = barData(rows, "cat", "v", "sum");
    expect(sum).toEqual([
      { category: "a", value: 4 },
      { category: "b", value: 10 },
    ]);
    const mean = barData(rows, "cat", "v", "mean");
    expect(mean.find((d) => d.category === "a")?.value).toBe(2);
    const count = barData(rows, "cat", "v", "count");
    expect(count.find((d) => d.category === "a")?.value).toBe(2);
  });
});

describe("valueCounts", () => {
  it("counts occurrences per distinct value and labels blanks", () => {
    const rows: Row[] = [
      { status: "ok" },
      { status: "ok" },
      { status: "bad" },
      { status: null },
      { status: "" },
    ];
    const counts = valueCounts(rows, "status");
    expect(counts.find((d) => d.category === "ok")?.value).toBe(2);
    expect(counts.find((d) => d.category === "bad")?.value).toBe(1);
    expect(counts.find((d) => d.category === "(blank)")?.value).toBe(2);
  });
});
