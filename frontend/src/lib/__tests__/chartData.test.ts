import { describe, expect, it } from "vitest";
import {
  barData,
  boxplotStats,
  buildColumnMeta,
  chartDefaults,
  correlationMatrix,
  datetimeColumns,
  histogram,
  numericColumns,
  pearson,
  sortByX,
  toNumber,
  topNWithOther,
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

describe("barData count semantics", () => {
  it("counts rows even when the value column is not numeric", () => {
    const rows: Row[] = [
      { cat: "a", v: "text" },
      { cat: "a", v: "more" },
      { cat: "b", v: "text" },
    ];
    const count = barData(rows, "cat", "v", "count");
    expect(count.find((d) => d.category === "a")?.value).toBe(2);
    expect(count.find((d) => d.category === "b")?.value).toBe(1);
  });

  it("labels blank categories consistently", () => {
    const rows: Row[] = [{ cat: null, v: 1 }, { cat: "", v: 2 }];
    const data = barData(rows, "cat", "v", "sum");
    expect(data).toEqual([{ category: "(blank)", value: 3 }]);
  });
});

describe("topNWithOther", () => {
  it("folds the tail into a single Other bucket", () => {
    const data = [4, 3, 2, 1].map((v, i) => ({ category: `c${i}`, value: v }));
    const result = topNWithOther(data, 3);
    expect(result).toHaveLength(3);
    expect(result[2]).toEqual({ category: "Other", value: 3 }); // 2 + 1
  });

  it("returns everything when it already fits", () => {
    const data = [{ category: "a", value: 1 }];
    expect(topNWithOther(data, 6)).toEqual(data);
  });
});

describe("datetimeColumns", () => {
  it("detects ISO dates and slash dates, not plain numbers or text", () => {
    const rows: Row[] = [
      { iso: "2024-01-31", ts: "2024-01-31T10:00:00", eu: "31/01/2024", year: "2020", name: "x" },
      { iso: "2024-02-01", ts: "2024-02-01T11:30:00", eu: "01/02/2024", year: "2021", name: "y" },
    ];
    expect(datetimeColumns(rows, ["iso", "ts", "eu", "year", "name"]).sort()).toEqual([
      "eu",
      "iso",
      "ts",
    ]);
  });
});

describe("sortByX", () => {
  it("sorts by date strings", () => {
    const rows: Row[] = [
      { d: "2024-03-01", v: 3 },
      { d: "2024-01-01", v: 1 },
      { d: "2024-02-01", v: 2 },
    ];
    expect(sortByX(rows, "d").map((r) => r.v)).toEqual([1, 2, 3]);
  });

  it("sorts numerically and leaves text order alone", () => {
    const nums: Row[] = [{ x: 10 }, { x: 2 }];
    expect(sortByX(nums, "x").map((r) => r.x)).toEqual([2, 10]);
    const text: Row[] = [{ x: "b" }, { x: "a" }];
    expect(sortByX(text, "x").map((r) => r.x)).toEqual(["b", "a"]);
  });
});

describe("boxplotStats", () => {
  it("computes the five-number summary", () => {
    const rows: Row[] = [1, 2, 3, 4, 5, 6, 7, 8, 9].map((v) => ({ v }));
    const [box] = boxplotStats(rows, "v", null);
    expect(box.category).toBe("All rows");
    expect(box.median).toBe(5);
    expect(box.q1).toBe(3);
    expect(box.q3).toBe(7);
    expect(box.lo).toBe(1);
    expect(box.hi).toBe(9);
    expect(box.count).toBe(9);
    expect(box.outliers).toBe(0);
  });

  it("clamps whiskers to the Tukey fences and reports outliers", () => {
    const rows: Row[] = [1, 2, 3, 4, 5, 100].map((v) => ({ v }));
    const [box] = boxplotStats(rows, "v", null);
    expect(box.hi).toBeLessThan(100);
    expect(box.outliers).toBe(1);
  });

  it("groups by a category column, largest groups first", () => {
    const rows: Row[] = [
      { g: "a", v: 1 },
      { g: "a", v: 2 },
      { g: "a", v: 3 },
      { g: "b", v: 10 },
    ];
    const stats = boxplotStats(rows, "v", "g");
    expect(stats.map((s) => s.category)).toEqual(["a", "b"]);
    expect(stats[1].median).toBe(10);
  });
});

describe("buildColumnMeta / chartDefaults", () => {
  const rows: Row[] = Array.from({ length: 40 }, (_, i) => ({
    order_id: i + 1,
    date: `2024-01-${String((i % 28) + 1).padStart(2, "0")}`,
    region: ["north", "south", "east"][i % 3],
    product: `product ${i % 12}`,
    amount: 100 + i * 3,
    qty: (i % 5) + 1,
  }));
  const columns = ["order_id", "date", "region", "product", "amount", "qty"];
  const meta = buildColumnMeta(rows, columns);

  it("classifies columns into numeric, categorical, and datetime", () => {
    expect(meta.datetime).toEqual(["date"]);
    expect(meta.numeric.sort()).toEqual(["amount", "order_id", "qty"]);
    expect(meta.categorical.sort()).toEqual(["product", "region"]);
  });

  it("histogram defaults to a non-id numeric column", () => {
    expect(chartDefaults("histogramChart", meta).column).toBe("amount");
  });

  it("bar chart defaults to a fitting category and a non-id measure", () => {
    const d = chartDefaults("barChart", meta);
    expect(d.x).toBe("product"); // most informative categorical within range
    expect(d.y).toBe("amount");
  });

  it("stacked bar picks a small-cardinality group distinct from x", () => {
    const d = chartDefaults("stackedBarChart", meta);
    expect(d.x).toBe("product");
    expect(d.group).toBe("region");
    expect(d.y).toBe("amount");
  });

  it("line chart defaults its x axis to the datetime column", () => {
    const d = chartDefaults("lineChart", meta);
    expect(d.x).toBe("date");
    expect(d.y).toBe("amount");
  });

  it("scatter picks two distinct non-id numerics", () => {
    const d = chartDefaults("scatterChart", meta);
    expect([d.x, d.y].sort()).toEqual(["amount", "qty"]);
    expect(d.x).not.toBe(d.y);
  });

  it("box plot pairs a measure with a small group", () => {
    const d = chartDefaults("boxPlot", meta);
    expect(d.y).toBe("amount");
    expect(d.group).toBe("region");
  });

  it("falls back to count aggregation when there are no numeric columns", () => {
    const textRows: Row[] = [
      { a: "x", b: "p" },
      { a: "y", b: "q" },
    ];
    const textMeta = buildColumnMeta(textRows, ["a", "b"]);
    expect(chartDefaults("barChart", textMeta).aggregate).toBe("count");
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
