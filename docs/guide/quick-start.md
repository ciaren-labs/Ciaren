---
title: Quick Start (5 Minutes)
description: Build and run your first ETL flow in the FlowFrame editor
search: quick start tutorial first flow editor api
---

# Quick Start (5 Minutes)

This walkthrough builds your first pipeline end to end: upload a file, clean it,
run it, and export Python. We'll use the visual editor; an API-only version is at
the bottom.

## Prerequisites

- The backend and frontend running locally (see [Installation](/guide/installation)).
  In short: `flowframe serve` in `backend/`, and `npm run dev` in `frontend/`.
- A small CSV to upload. Any file with a header row works — for example
  `sales.csv`:

  ```csv
  order_id,region,amount,notes
  1,North,120.5,
  2,South,,first order
  2,South,,first order
  3,,80,
  ```

## 1. Upload a dataset

1. Open `http://localhost:5173` and go to **Datasets**.
2. Click **Upload**, choose your file, and confirm.

FlowFrame infers the column schema and stores a sample. Datasets are
**versioned** — re-uploading a file with the same name adds a new version rather
than overwriting the old one, so existing flows stay reproducible.

## 2. Create a flow

1. Go to **Flows → New flow**. The canvas opens with an empty graph.
2. Drag a **CSV Input** node from the palette and select the dataset you uploaded.
3. Add a few transformation nodes and connect them in order:
   - **Drop Nulls** — remove rows missing an `amount`.
   - **Remove Duplicates** — drop repeated rows.
   - **Group by & Aggregate** — group by `region`, sum `amount`.
4. Add a **CSV Output** node at the end and connect it.

Each node has a config panel on the side. As you edit a node, the **live
preview** updates on a sample of your data, so you can confirm each step before
running anything. See the [Interface Tour](/guide/interface) for the full layout
and the [Transformations Reference](/transformations/overview) for every node.

## 3. Run the flow

Click **Run**. FlowFrame executes the whole pipeline on the
[default engine](/guide/engines) (polars), writes the output file, and records a
**run** with status, logs, and per-node results (row/column counts and a sample).

Open the run from the **Runs** page to inspect each node and download the output.

## 4. Export Python

Click **Export → Python**. FlowFrame returns standalone, readable code for your
flow — both the **polars** and the **pandas** version. Paste it into a script or
a Jupyter notebook and it runs on its own, no FlowFrame required.

## 5. (Optional) Schedule it

To run the flow automatically, open it and add a **Schedule** with a cron
expression and timezone. The built-in scheduler handles retries, catch-up, and
overlap protection. See [Scheduling](/guide/scheduling).

## Prefer the API?

Everything above is also available over REST. The fastest way to explore it is
the interactive docs at `http://localhost:8000/docs`.

```bash
# 1. Upload a dataset (note the returned id)
curl -F "file=@sales.csv" http://localhost:8000/api/datasets/upload

# 2. Inspect it
curl http://localhost:8000/api/datasets/{dataset_id}/schema
curl http://localhost:8000/api/datasets/{dataset_id}/sample

# 3. Create a flow (a React Flow-compatible graph of nodes + edges)
curl -X POST http://localhost:8000/api/flows \
  -H "Content-Type: application/json" -d @flow.json

# 4. Preview, then run (optionally choose an engine)
curl -X POST http://localhost:8000/api/flows/{flow_id}/preview
curl -X POST http://localhost:8000/api/flows/{flow_id}/runs \
  -H "Content-Type: application/json" -d '{"engine": "polars"}'
curl http://localhost:8000/api/runs/{run_id}

# 5. Export Python (returns both pandas and polars code)
curl -X POST http://localhost:8000/api/flows/{flow_id}/export/python
```

The flow graph format (node `type`s, `data.config`, and edges) is described in
the [Transformations Reference](/transformations/overview) and the
[REST API Reference](/api/rest-api).

## Next Steps

- [Interface Tour](/guide/interface) — learn the editor
- [Transformations Reference](/transformations/overview) — all node types
- [Examples](/examples/sales-analysis) — real-world, end-to-end walkthroughs
- [REST API Reference](/api/rest-api) — every endpoint
