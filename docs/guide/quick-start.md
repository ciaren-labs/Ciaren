---
title: Quick Start (5 Minutes)
description: "Build and run your first Ciaren flow in five minutes: pick or upload a CSV dataset, add cleaning nodes, run it, export Python code, and optionally schedule it."
search: quick start tutorial first flow editor api
---

# Quick Start (5 Minutes)

**For:** first-time users who have Ciaren running. **You get:** your first flow,
built, run, and exported as Python in about five minutes.

In Ciaren, a saved pipeline is called a **flow** — you'll see that word
everywhere in the editor and the API. This walkthrough uses the visual editor;
an API-only version is at the bottom for developers who want to inspect the
REST surface.

## Before You Start

- Ciaren running locally ([Installation](/guide/installation)). If you
  installed from PyPI or used Docker, open `http://localhost:8055`. If you run
  from source in development mode, open `http://localhost:5173`.
- Either the built-in Demo project or a small CSV. Any file with a header row
  works — for example `sales.csv`:

  ```csv
  order_id,region,amount,notes
  1,North,120.5,
  2,South,,first order
  2,South,,first order
  3,,80,
  ```

:::tip No CSV at hand? Use the Demo project
Every fresh install seeds a **Demo** project with sample datasets, so you can
follow this walkthrough without uploading anything. What it contains, and how to
start without it, is on [Demo Project & Tutorials](/guide/demo-project).
:::

## What you'll build

By the end of this walkthrough you will have a running pipeline that cleans,
aggregates, and outputs a summary CSV — plus the equivalent Python script.

<FlowPipeline :nodes='[
  {"type":"input","label":"File Input","detail":"upload sales.csv"},
  {"type":"clean","label":"Drop Nulls","detail":"remove rows missing amount"},
  {"type":"clean","label":"Remove Duplicates","detail":"deduplicate rows"},
  {"type":"transform","label":"Group By + Aggregate","detail":"sum amount by region"},
  {"type":"output","label":"File Output","detail":"sales_summary.csv"}
]' />

## 1. Pick or Upload a Dataset

If you are using the Demo project, you can skip the upload and use an existing
sample dataset.

To upload your own file:

1. Open the app and go to **Datasets**. The drop zone is visible immediately,
   with the **Upload to project** dropdown defaulted to your first project
   (e.g. "Default") — change it if you want the file to land somewhere else.
2. Drag your file onto the drop zone, or click it to browse and select one. It
   accepts CSV, TSV, Excel, Parquet, JSON, JSON Lines, or plain text.

Ciaren infers the column schema and stores a sample. Datasets are
**versioned** — re-uploading a file with the same name adds a new version rather
than overwriting the old one, so existing flows stay reproducible.

## 2. Create a flow

1. Go to **Flows → New flow**. This opens a modal with Name/Description/Project
   fields and starter templates such as **Blank flow**, **Clean & Deduplicate**,
   **Filter & Aggregate**, **Data Quality Checks**, and **Tidy Columns**. Pick
   **Blank flow** for an empty canvas, as this walkthrough assumes.
2. Drag a **File Input** node from the palette, select the dataset you
   uploaded, and set its **File type** to CSV.
3. Add a few transformation nodes and connect them in order:
   - **Drop Nulls** — remove rows missing an `amount`.
   - **Remove Duplicates** — drop repeated rows.
   - **Group by & Aggregate** — group by `region`, sum `amount`.
4. Add a **File Output** node at the end and connect it.

![Building the flow on the canvas — drag nodes from the palette, connect them in order, and auto-arrange the pipeline](/screenshots/build-flow-from-scratch.gif)

Each node has a config panel on the side. As you edit a node, the **live
preview** updates on a sample of your data, so you can confirm each step before
running anything. See the [Interface Tour](/guide/interface) for the full layout
and the [Transformations Reference](/transformations/overview) for every node.

## 3. Run the flow

Click **Run**. Ciaren executes the whole pipeline on the
[default engine](/guide/engines) (polars), writes the output file, and records a
**run** with status, logs, and per-node results (row/column counts and a sample).

Open the run from the **Runs** page to inspect each node and download the output.

## 4. Export Python

Click **Export → Python**. Ciaren returns standalone, readable code for your
flow, including **polars**, **pandas**, and **lazy polars** variants where
available. Paste it into a script or a Jupyter notebook and it runs on its own,
no Ciaren required.

## 5. (Optional) Schedule it

To run the flow automatically, open it and add a **Schedule** with a cron
expression and timezone. The built-in scheduler handles retries, catch-up, and
overlap protection. See [Scheduling](/guide/scheduling).

## Prefer the API?

Everything above is also available over REST. The fastest way to explore it is
the interactive docs at `http://localhost:8055/docs`.

```bash
# 1. Upload a dataset (note the returned id)
curl -F "file=@sales.csv" http://localhost:8055/api/datasets/upload

# 2. Inspect it
curl http://localhost:8055/api/datasets/{dataset_id}/schema
curl http://localhost:8055/api/datasets/{dataset_id}/sample

# 3. Create a flow (a React Flow-compatible graph of nodes + edges)
curl -X POST http://localhost:8055/api/flows \
  -H "Content-Type: application/json" -d @flow.json

# 4. Preview, then run (optionally choose an engine)
curl -X POST http://localhost:8055/api/flows/{flow_id}/preview \
  -H "Content-Type: application/json" -d '{"limit": 50}'
curl -X POST http://localhost:8055/api/flows/{flow_id}/runs \
  -H "Content-Type: application/json" -d '{"engine": "polars"}'
curl http://localhost:8055/api/runs/{run_id}

# 5. Export Python (returns pandas, polars, lazy polars, and a portable .flow document)
curl -X POST http://localhost:8055/api/flows/{flow_id}/export/python
```

The flow graph format (node `type`s, `data.config`, and edges) is described in
the [Transformations Reference](/transformations/overview) and the
[REST API Reference](/api/rest-api).

## Next Step

Continue to **[Demo Project & Tutorials](/guide/demo-project)** to follow four
ready-made flows step by step, from a linear cleanup to a three-input join.

Other places to go from here:

- [Interface Tour](/guide/interface) — learn the editor
- [Transformations Reference](/transformations/overview) — all node types
- [Examples](/examples/sales-analysis) — real-world, end-to-end walkthroughs
- [REST API Reference](/api/rest-api) — every endpoint
