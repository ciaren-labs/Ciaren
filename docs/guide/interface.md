---
title: Interface Tour
description: "A tour of the Ciaren visual editor: the Projects, Datasets, Connections, Flows and Runs pages, plus the canvas, 72-node palette, config panel, live preview, AI assistant panel and export."
search: interface ui tour navigation editor canvas assistant panel connections api keys
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
- **Connections** (`/connections`) — two sections. **Assistant API keys** holds
  the provider keys for the [flow assistant](/guide/flow-assistant), kept in the
  OS keychain. **Data connections** holds reusable connections for the SQL,
  storage and REST API nodes (databases, S3, GCS, Azure Blob, MLflow and
  plugin connectors). A connection stores a secret reference, never the secret
  itself. See [Database Connections](/guide/connections).
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
- **Settings** (`/settings`, the gear icon on the right of the navigation bar) —
  runtime server configuration: default engine, execution mode, timeouts, upload
  and scheduler limits, and ML guardrails. Edits are
  saved server-side and survive restarts; each setting names its `CIAREN_*`
  variable and shows whether the value comes from a default, an environment
  variable, or a saved override — while an override exists, the environment
  variable is ignored until you press Reset. See
  [Advanced Setup](/guide/advanced-setup#the-settings-page).

## The flow editor

Opening a flow (`/flows/:flowId`) shows the node-based editor, built on
[React Flow](https://reactflow.dev/). The layout has three main regions, plus
the assistant panel when you open it:

![Ciaren flow editor — node palette on the left, canvas in the center, config panel on the right](/screenshots/editor-full.png)

- **Canvas** — where you place and connect nodes. Each node maps to exactly one
  dataframe operation. Drag from a node's output handle to another node's input
  handle to create an edge.
- **Node palette** — 72 nodes grouped into 9 categories, each with its own
  color: **Inputs** (3, emerald), **Cleaning** (9, sky), **Columns** (10,
  indigo), **Reshape** (6, violet), **Analytics** (11, fuchsia), **Data
  Quality** (6, orange), **Charts** (8, rose), **Machine Learning** (16,
  purple), and **Outputs** (3, amber). See the
  [Transformations Reference](/transformations/overview).
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
- **Assistant** — opens the [flow assistant](/guide/flow-assistant) panel. See
  [The assistant panel](#the-assistant-panel) below.

The toolbar above the canvas also holds the flow name, undo and redo, the
keyboard shortcuts help, the engine picker, **Parameters**, **Schedule** and
**Save**. **Save** shows a small dot while the canvas has unsaved edits.

Building a pipeline is drag, configure, connect — no code required to start:

![Building a flow from scratch — dropping a File Input, two cleaning nodes, a Train/Test Split and a classifier onto the canvas, then connecting and auto-arranging them](/screenshots/build-flow-from-scratch.gif)

### Canvas shortcuts

Open **Keyboard shortcuts** in the editor toolbar for the current controls.
Use **Backspace** to delete selected nodes or edges, **Shift + drag** to select
nodes in a box, and **Ctrl/Cmd + click** to toggle a node's selection. Hold
**Space** while dragging to pan; scroll or pinch to zoom. Arrow keys move the
selection when a selected node has keyboard focus. **Escape** closes the
shortcut help or a node's context menu.

Copy, paste, duplicate, undo and redo apply outside editable form fields.
Redo accepts **Ctrl/Cmd + Shift + Z** or **Ctrl/Cmd + Y**.

## The assistant panel

Choose **Assistant** in the toolbar, or **Ask the assistant** at the bottom of
the canvas, to open the AI flow assistant. The panel docks to the right of the
canvas, and fills the screen on a narrow window. The **Assistant** button shows
a dot when a reply arrives while the panel is closed. Close the panel with the
**X** or Escape. A request keeps running while the panel is closed.

The panel has two tabs. **Conversation** is where you ask. **Activity** lists
the changes the assistant saved to this flow and lets you preview and confirm a
reversal.

The Conversation tab works from top to bottom:

- **Conversation area.** Before the first request it shows a short prompt,
  example requests under **Try**, and the **On device** canvas tools: **Check
  canvas** and **Explain selected node**, which need no provider. After a
  request it shows your requests and the replies: a proposal to review, a
  question with choice buttons, an answer from the guides, or an explanation
  of why nothing was proposed. Without an API key, it shows **Connect a
  provider** with an **Open connections** button.
- **Task buttons.** **Build** creates or changes nodes, **Guides** answers
  questions from the bundled documentation, and **Diagnose** looks at the
  latest failed run.
- **Input dataset.** On an empty canvas, pick the dataset to start from. Build
  can also offer **Right input for Join** and, with the ML extension,
  **Second lookup for regression** and **Regression target**.
- **Request box.** Type up to 1,500 characters, then choose **Create
  proposal** (Build), **Diagnose flow** or **Ask the guides**. Ctrl+Enter sends.
  The box shows the model in use.
- **Data shared with provider.** Expand it to see what a request sends and to
  opt in to **Include column names in this request**.

A proposal lists every added or updated node and connection, with **Apply and
save**, **Regenerate**, **Edit request** and **Discard**. After you apply it,
a message offers **Undo** and **View in Activity**. See the
[flow assistant guide](/guide/flow-assistant) for what it can build, privacy
and limits.

## The Connections page

The Connections page starts with **Assistant API keys**. Each key appears as a
row with a radio button to choose the key in use, an **In use** or **Disabled**
badge, an **Enabled** switch, and edit and remove buttons. **Add API key**
opens a form for the name, provider, model, reasoning effort and the key, with
a storage notice to confirm. **Data connections** follows, with **Add
connection**, a card per connection with **Test**, edit and delete, and the
built-in **Local MLflow** and **Local Storage** connections. See
[Database Connections](/guide/connections) and
[Assistant API keys](/guide/connections#assistant-api-keys).

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
