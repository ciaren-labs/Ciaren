---
title: Interface Tour
description: A tour of the FlowFrame visual editor
search: interface ui tour navigation editor canvas
---

# Interface Tour

The FlowFrame editor follows the [design system](/guide/design-system) — a
purple-based, minimalist layout. This page walks through the main screens.

## Top-level pages

FlowFrame is organized around a few pages, reachable from the navigation bar at the top:

![Datasets page — card grid showing uploaded CSV/Parquet files with column counts and version labels](/screenshots/datasets.png)

- **Landing** (`/`) — the marketing/start page.
- **Projects** (`/projects`) — lightweight workspaces that group related datasets
  and flows. A `Default` project always exists. See
  [Projects & Runs](/guide/projects-and-runs).
- **Datasets** (`/datasets`) — upload and inspect source files (CSV, Excel,
  Parquet), with versioning. Each dataset has a **Profile** tab with per-column
  statistics (nulls, distinct counts, ranges, top values), computed at upload
  time.
- **Connections** (`/connections`) — reusable database connections for the SQL
  Input/Output nodes (PostgreSQL, MySQL, SQLite, SQL Server, MongoDB). Passwords
  are read from environment variables, never stored. See
  [Database Connections](/guide/connections).
- **Flows** (`/flows`) — your saved pipelines; open one to edit it on the canvas.
- **Models** (`/models`) — MLflow-tracked model registry: registered models with
  metrics, aliases (`@production`, `@staging`), and lineage back to the flow and
  run that produced each version. Only visible when the `[ml]` extra is installed.
- **Runs** (`/runs`) — execution history; open a run for status, logs, and
  per-node results.
- **Schedules** (`/schedules`) — automated flows; see [Scheduling](/guide/scheduling).

## The flow editor

Opening a flow (`/flows/:flowId`) shows the node-based editor, built on
[React Flow](https://reactflow.dev/). The layout has three main regions:

![FlowFrame flow editor — node palette on the left, canvas in the center, config panel on the right](/screenshots/editor-full.png)

- **Canvas** — where you place and connect nodes. Each node maps to exactly one
  dataframe operation. Drag from a node's output handle to another node's input
  handle to create an edge.
- **Node palette** — input, cleaning, transform/reshape, and output nodes, grouped
  by category and color-coded (input = emerald, clean = sky, transform = violet,
  output = amber). See the [Transformations Reference](/transformations/overview).
- **Config panel** — per-node settings (column selection, operators, target
  types, aggregations). Forms are validated as you type for fast feedback; the
  backend re-validates on run. Click any node to open its config:

  ![Config panel — Fill Nulls node selected, showing Strategy dropdown and column chip selector](/screenshots/editor-node-config.png)
- **Live preview** — open with the **Preview** button, then click **Run preview**
  to fetch a sample of the output (whole-flow or the selected node). Backed by
  `POST /api/flows/{id}/preview` and `POST /api/transformations/preview`.

  ![Data Preview panel showing 116 rows of joined customer-order data](/screenshots/editor-data-preview.png)
- **Profile** — alongside the preview, a one-click **Profile** view shows
  per-column statistics for the selected node's output: null count and
  percentage, distinct count, numeric min/mean/max, datetime range, and the top
  values for text columns. Request it by passing `profile: true` to the preview
  endpoints. Stats are computed on a bounded sample so they stay fast on large
  frames.
- **Run** — executes the whole flow and records a run.
- **Export** — generates standalone Python (polars and pandas) for the flow.

## Node handles

Most nodes have a single input handle (`in`) and a single output handle (`out`).
Two nodes are different:

- **Join** has two input handles, `left` and `right`.
- **Union / Concat** accepts multiple inputs (connect as many upstream nodes as
  you need to stack).

## Runs view

A run's detail page (`/runs/:runId`) shows the flow as a read-only DAG.

![Run detail page — DAG with per-node success status and row counts, summary panel on the right](/screenshots/run-detail.png)
 Each node
reports its status (`success` / `failed` / `skipped`), row and column counts, a
small sample of its output, and a `duration_ms` for performance insight. The run
also records which engine it used and the resolved dataset versions, so it is
fully reproducible.

## Next steps

- [Quick Start](/guide/quick-start) — build your first flow
- [Transformations Reference](/transformations/overview) — every node and its config
- [Projects & Runs](/guide/projects-and-runs) — organizing and monitoring work
