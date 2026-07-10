// Render tests for the run-screen chart artifacts. The recharts-based views
// need a real layout box (jsdom has none), so these focus on the custom SVG
// renderers (box plot, heatmap), the artifact fallbacks, and the pure helpers
// that drive the exported PNG's legend.
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { exportLegendEntries, RunChartView } from "../RunChart";
import { getChartTheme } from "@/lib/chartTheme";
import type { ChartArtifact } from "@/features/runs/types";

const t = getChartTheme("light");

function boxArtifact(): ChartArtifact {
  return {
    kind: "boxplot",
    column: "amount",
    group_by: "region",
    groups: [
      { label: "North", min: 1, q1: 2, median: 3, q3: 4, max: 5, outliers: 1, count: 20 },
      { label: "South", min: 0, q1: 1, median: 2, q3: 3, max: 4, outliers: 0, count: 10 },
    ],
    total_groups: 2,
  };
}

describe("RunChartView (custom SVG renderers)", () => {
  it("renders one box per group with its five-number tooltip", () => {
    const { container } = render(<RunChartView art={boxArtifact()} />);
    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(container.querySelectorAll("rect")).toHaveLength(2);
    const titles = [...container.querySelectorAll("title")].map((el) => el.textContent ?? "");
    expect(titles.some((s) => s.includes("North") && s.includes("median: 3"))).toBe(true);
    expect(titles.some((s) => s.includes("1 outlier not drawn"))).toBe(true);
    expect(screen.getByText("South")).toBeTruthy();
  });

  it("skips box groups whose stats were nulled by the backend (NaN/inf)", () => {
    const art = boxArtifact();
    art.groups!.push({
      label: "broken",
      min: null as unknown as number,
      q1: 1,
      median: 2,
      q3: 3,
      max: 4,
      outliers: 0,
      count: 5,
    });
    const { container } = render(<RunChartView art={art} />);
    expect(container.querySelectorAll("rect")).toHaveLength(2); // broken group dropped
  });

  it("renders a heatmap cell per column pair with correlation values", () => {
    const art: ChartArtifact = {
      kind: "heatmap",
      columns: ["a", "b"],
      matrix: [
        [1, -0.5],
        [-0.5, 1],
      ],
      total_columns: 2,
    };
    const { container } = render(<RunChartView art={art} />);
    expect(container.querySelectorAll("rect")).toHaveLength(4);
    const titles = [...container.querySelectorAll("title")].map((el) => el.textContent ?? "");
    expect(titles).toContain("a × b: -0.50");
  });

  it("shows a placeholder for an empty or unknown artifact", () => {
    render(<RunChartView art={{ kind: "boxplot", groups: [] }} />);
    expect(screen.getByText(/No numeric values/)).toBeTruthy();
    render(<RunChartView art={{ kind: "nope" } as unknown as ChartArtifact} />);
    expect(screen.getByText(/Unsupported chart artifact/)).toBeTruthy();
  });
});

describe("exportLegendEntries", () => {
  it("lists pie slices, giving Other the neutral colour", () => {
    const art: ChartArtifact = {
      kind: "pie",
      data: [
        { label: "A", value: 3 },
        { label: "Other", value: 1 },
      ],
    };
    const entries = exportLegendEntries(art, t);
    expect(entries.map((e) => e.label)).toEqual(["A", "Other"]);
    expect(entries[0].color).toBe(t.series[0]);
    expect(entries[1].color).toBe(t.neutral);
  });

  it("skips null-valued pie slices so legend colours match the drawn chart", () => {
    // The Donut renderer filters null values before assigning colour slots; a
    // null slice ahead of the rest must not shift the exported legend.
    const art: ChartArtifact = {
      kind: "pie",
      data: [
        { label: "empty", value: null },
        { label: "A", value: 3 },
        { label: "B", value: 2 },
      ],
    };
    const entries = exportLegendEntries(art, t);
    expect(entries.map((e) => e.label)).toEqual(["A", "B"]);
    expect(entries[0].color).toBe(t.series[0]);
    expect(entries[1].color).toBe(t.series[1]);
  });

  it("lists stacked-bar series but skips single-series charts", () => {
    const stacked: ChartArtifact = {
      kind: "bar",
      group_by: "product",
      series: ["x", "y"],
      rows: [],
    };
    expect(exportLegendEntries(stacked, t).map((e) => e.label)).toEqual(["x", "y"]);
    const plain: ChartArtifact = { kind: "bar", data: [] };
    expect(exportLegendEntries(plain, t)).toEqual([]);
    const singleLine: ChartArtifact = { kind: "line", series: ["amount"], rows: [] };
    expect(exportLegendEntries(singleLine, t)).toEqual([]);
    const multiLine: ChartArtifact = { kind: "line", series: ["a", "b"], rows: [] };
    expect(exportLegendEntries(multiLine, t).map((e) => e.label)).toEqual(["a", "b"]);
  });
});
