---
title: Visualizations
description: Chart any node's output right in the editor — histograms, correlations, line, scatter, and bar charts
search: visualization chart histogram correlation heatmap scatter bar line plot preview sample
---

# Visualizations

While you build a flow, you can **chart the output of any node** without leaving
the editor. Visualizations are for *inspection* — spotting distributions,
outliers, trends, and relationships as you clean — not a pipeline output. They
add nothing to the graph and are never written to a file.

## How to chart a node

1. Open a flow in the editor and **select a node** on the canvas.
2. Open the **Data Preview** panel at the bottom and click **Chart**.
3. Pick a **chart type** and the **column(s)** to plot.

![Editor chart panel — histogram of pc_1 PCA column with 150 rows, showing bimodal distribution](/screenshots/editor-chart.png)

The chart renders instantly. Switching chart type or columns is immediate —
it re-draws from the data already loaded, so there's no waiting.

## Chart types

| Type | What it shows | Inputs |
| ------ | --------------- | -------- |
| **Histogram** | Distribution of a numeric column | column, bin count |
| **Value counts** | Frequency of each distinct value | column |
| **Bar** | A value aggregated by category | category (x), value (y), aggregate |
| **Pie** | A category's share of a total | category (x), value (y), aggregate |
| **Line / time series** | A value over an ordered axis | x axis, y value |
| **Area** | A value over an ordered axis, filled | x axis, y value |
| **Scatter** | Relationship between two numeric columns | x, y |
| **Correlation heatmap** | Pairwise Pearson correlation | all numeric columns in the sample |

## Charts are based on a sample

:::warning Sample, not the full dataset
Charts are computed in your browser from the node's **preview sample** — a
capped number of rows, not the entire dataset. Every chart shows a caption like
*"Based on a sample of N rows — not the full dataset."*

This matters most for the **correlation heatmap**: a Pearson value on a sample
can differ from the correlation over all the data. Treat the charts as a quick
look for exploration, then run the flow to compute final results.
:::

The sample is the same one the **Data** preview shows, just drawn as a chart, so
what you see lines up with the table view.

## Want the chart over ALL the data? Use a chart node

Preview charts are for exploring. When a chart should be part of the *result*,
add a **[chart node](../transformations/charts.md)** from the **Charts**
palette category instead: it computes the chart over the **full data** when the
flow runs, stores it on the run, and lets you **export it as a PNG** from the
run page.

![Run detail — a Bar Chart node selected, showing the stored chart computed over the full run data with an Export PNG button](/screenshots/run-chart-detail.png)

| | Preview charts (this page) | [Chart nodes](../transformations/charts.md) |
| --- | --- | --- |
| **Data** | Capped preview sample | Every row of the run |
| **When** | Live, while you edit | At run time |
| **Lives** | In the editor only | Stored on each run |
| **Export** | — | PNG with title + legend |
| **In the graph** | No | Yes — a pass-through node |

## Tips

- **No chart? Run a preview first.** Charts read the node's preview sample, so
  save the flow and let the preview load.
- **Histogram / scatter / correlation need numbers.** Non-numeric columns are
  ignored; cast a text column with **Change Types** upstream if needed.
- **Inspect mid-pipeline.** Select an *intermediate* node (e.g. right after
  **Remove Outliers**) to see the effect of a step, not just the final output.

## See Also

- [Chart nodes](../transformations/charts.md) — full-data charts stored on runs
- [Interface Tour](./interface.md)
- [Engines (polars / pandas)](./engines.md)
- [All Transformations](../transformations/overview.md)
