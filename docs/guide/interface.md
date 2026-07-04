---
title: Interface Tour
description: A tour of the Ciaren visual editor
search: interface ui tour navigation editor canvas
---

# Interface Tour

The Ciaren editor follows the [design system](/guide/design-system) — a
purple-based, minimalist layout. This page walks through the main screens.

## Top-level pages

Ciaren is organized around a few pages, reachable from the navigation bar at the top:

![Datasets page — card grid showing uploaded CSV/Parquet files with column counts and version labels](/screenshots/datasets.png)

- **Landing** (`/`) — the marketing/start page.
- **Projects** (`/projects`) — lightweight workspaces that group related datasets
  and flows. A `Default` project always exists. See
  [Projects & Runs](/guide/projects-and-runs).
- **Datasets** (`/datasets`) — upload and inspect source files (CSV, TSV, Excel,
  Parquet, JSON/JSONL, and text), with versioning. Each dataset has a **Profile** tab with per-column
  statistics (nulls, distinct counts, ranges, top values), computed at upload
  time.
- **Connections** (`/connections`) — reusable database connections for the SQL
  Input/Output nodes (PostgreSQL, MySQL, SQLite, SQL Server, MongoDB). Passwords
  are read from environment variables, never stored. See
  [Database Connections](/guide/connections).
- **Flows** (`/flows`) — your saved pipelines; open one to edit it on the canvas.
- **Models** (`/models`) — MLflow-tracked model registry: registered models with
  metrics, aliases (`@production`, `@staging`), and lineage back to the flow and
  run that produced each version. Only visible when ML is enabled (on by default).
- **Runs** (`/runs`) — execution history; open a run for status, logs, and
  per-node results.
- **Schedules** (`/schedules`) — automated flows; see [Scheduling](/guide/scheduling).
- **Plugins** (`/plugins`) — install, approve, and manage plugin extensions
  (custom nodes, connectors, and more); see [Plugins Overview](/plugins/overview)
  and [Managing Plugins](/plugins/managing-plugins).

## The flow editor

Opening a flow (`/flows/:flowId`) shows the node-based editor, built on
[React Flow](https://reactflow.dev/). The layout has three main regions:

![Ciaren flow editor — node palette on the left, canvas in the center, config panel on the right](/screenshots/editor-full.png)

- **Canvas** — where you place and connect nodes. Each node maps to exactly one
  dataframe operation. Drag from a node's output handle to another node's input
  handle to create an edge.
- **Node palette** — 58 nodes grouped into 8 categories, each with its own
  color: **Inputs** (3, emerald), **Cleaning** (9, sky), **Columns** (10,
  indigo), **Reshape** (6, violet), **Analytics** (11, fuchsia), **Data
  Quality** (6, orange), **Machine Learning** (16, purple), and **Outputs**
  (3, amber). See the [Transformations Reference](/transformations/overview).
- **Config panel** — per-node settings (column selection, operators, target
  types, aggregations). Forms are validated as you type for fast feedback; the
  backend re-validates on run. Click any node to open its config:

  ![Config panel — Fill Nulls node selected, showing Strategy dropdown and column chip selector](/screenshots/editor-node-config.png)
- **Live preview** — open with the **Preview** button, then click **Run preview**
  to fetch a sample of the output (whole-flow or the selected node). Backed by
  `POST /api/flows/{id}/preview` and `POST /api/transformations/preview`. Flow
  previews use the last saved version of the flow; save before previewing if the
  canvas has unsaved edits.

  ![Previewing the joined customer-order data (116 rows), then switching to per-column Profile statistics — live, on the canvas](/screenshots/live-data-preview.gif)
- **Profile** — alongside the preview, a one-click **Profile** view shows
  per-column statistics for the selected node's output: null count and
  percentage, distinct count, numeric min/mean/max, datetime range, and the top
  values for text columns. Request it by passing `profile: true` to the preview
  endpoints. Stats are computed on a bounded sample so they stay fast on large
  frames.
- **Run** — executes the whole flow and records a run.
- **Export** — generates standalone Python (polars and pandas) for the flow.

Building a pipeline is drag, configure, connect — no code required to start:

![Building a flow from scratch — dropping a File Input, two cleaning nodes, a Train/Test Split and a classifier onto the canvas, then connecting and auto-arranging them](/screenshots/build-flow-from-scratch.gif)

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
