---
title: Getting Started
description: Learn what Ciaren is and how to get started in minutes
search: getting started introduction what is ciaren
---

# Getting Started with Ciaren

Welcome to Ciaren! This guide will help you understand what Ciaren is and get you up and running in minutes.

:::warning Alpha software
Ciaren is in early development. APIs and generated code may change between
releases. Use it for learning, experimentation, and controlled internal
workflows before relying on it for critical production jobs.
:::

## What is Ciaren?

Ciaren is an open-core, **plugin-first, local-first platform** for building
**Data Engineering and Machine Learning workflows** visually — and turning them
into clean, portable Python. It runs on **polars** by default (or pandas, per run)
and lets you:

- **Ingest** from CSV, TSV, Excel, Parquet, JSON/JSONL, text, SQL databases, and cloud storage
- **Build** transformation pipelines visually on a drag-and-drop canvas
- **Validate** data with built-in quality/contract checks
- **Preview** results in real-time at every step
- **Train** machine-learning models on the same canvas, tracked with MLflow
- **Export** the equivalent, readable Python — pandas or polars, no lock-in
- **Schedule** flows to run automatically with a built-in cron scheduler
- **Extend** almost everything — nodes, connectors, engines, exporters, and more —
  through [plugins](/plugins/overview)

It's more than a visual data tool: every node maps to one clear dataframe operation,
so the generated code is readable and the platform stays transparent and extensible.
Approachable enough to start without writing code — and Python-native when you want
full control.

## How It Works

Upload your data, arrange nodes on a canvas, preview every step, then run the full
pipeline and export readable Python — all without writing a line of code.

<FlowPipeline :vertical="true" :nodes='[
  {"type":"input","label":"Upload Data","detail":"CSV, TSV, Excel, Parquet, JSON, or SQL"},
  {"type":"clean","label":"Build Your Pipeline","detail":"drag nodes · connect handles · configure each step"},
  {"type":"clean","label":"Live Preview","detail":"see your data transform on real rows instantly"},
  {"type":"transform","label":"Run the Full Flow","detail":"executes on polars (or pandas) · saves a run record"},
  {"type":"output","label":"Download Results + Python Code","detail":"standalone script — runs anywhere without Ciaren"}
]' />

## Who is Ciaren For?

- **Data Engineers** — Build repeatable, reviewable pipelines without orchestration overhead
- **Developers** — Prototype visually, then export and version the generated Python
- **Plugin Authors** — Extend the platform with custom nodes, connectors, and engines
- **Data Scientists** — Go from raw data to a tracked model on one canvas
- **Data Analysts** — Clean, join, and explore data visually
- **Educators & Python Learners** — See pandas/polars operations come to life

## What You'll Need

- **No Python knowledge required** — just point and click
- **A CSV or Excel file** — sample data to transform
- **A web browser** — Chrome, Firefox, Safari, or Edge
- **5 minutes** — to build your first flow

## What You Can't Do (Yet)

Ciaren is designed for **local, single-machine data transformation**. It is
**not** an Airflow/Spark/dbt replacement and doesn't support:

- Distributed computing (Spark, Dask)
- Real-time streaming pipelines
- 100GB+ datasets
- Cross-flow DAG dependencies or complex orchestration
- Multi-user collaboration and enterprise permissions

It *does* include a lightweight cron scheduler for running a single flow on a
schedule — see [Scheduling](/guide/scheduling).

## Next Steps

1. **[Install Ciaren](/guide/installation)** — get it running locally (2 minutes)
2. **[5-Minute Quick Start](/guide/quick-start)** — build your first flow
3. **[Interface Tour](/guide/interface)** — learn the UI
4. **[Transformation Reference](/transformations/overview)** — all available operations
5. **[Examples](/examples/sales-analysis)** — real-world workflows

## Quick Preview

Here's what Ciaren looks like in action — a flow with real data loaded in the preview panel:

![Ciaren editor with data preview — canvas, node palette, and 116-row preview table](/screenshots/editor-data-preview.png)

Here is what a typical sales-summary pipeline looks like in Ciaren. Each colored
card is one node; you drag them from the palette and connect them on the canvas.

<FlowPipeline :nodes='[
  {"type":"input","label":"CSV Input","detail":"sales.csv"},
  {"type":"clean","label":"Drop Columns","detail":"remove internal_id, temp_notes"},
  {"type":"clean","label":"Filter Rows","detail":"amount > 0"},
  {"type":"clean","label":"Fill Nulls","detail":"region → \"Unknown\""},
  {"type":"transform","label":"Group By + Aggregate","detail":"by region · sum amount"},
  {"type":"clean","label":"Rename Columns","detail":"sum_amount → total_sales"},
  {"type":"output","label":"File Output","detail":"sales_summary.csv"}
]' />

## FAQ

### Do I need to know Python?

No! Ciaren is designed for non-programmers. The visual editor guides you through each step.

### Can I save my flows?

Yes! Flows are saved to a database and can be run again anytime.

### Can I export as Python code?

Yes! Every flow generates readable **polars and pandas** code you can use in scripts or Jupyter notebooks.

### Is my data secure?

Ciaren runs entirely locally on your machine. No data is sent anywhere. (No SaaS, no cloud uploads.)

### Can I use my own database?

Yes! Use a **SQL Input** or **SQL Output** node with a saved [Connection](/guide/connections). PostgreSQL, MySQL, SQLite, SQL Server, and MongoDB are supported.

## Still Have Questions?

- **[Troubleshooting Guide](/guide/troubleshooting)** — Common issues and solutions
- **[FAQ](/faq)** — More frequently asked questions
- **[GitHub Discussions](https://github.com/ciaren-labs/Ciaren/discussions)** — Ask the community

---

**Ready to dive in?** [Install and get started →](/guide/installation)
