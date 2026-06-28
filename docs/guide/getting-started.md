---
title: Getting Started
description: Learn what FlowFrame is and how to get started in minutes
search: getting started introduction what is flowframe
---

# Getting Started with FlowFrame

Welcome to FlowFrame! This guide will help you understand what FlowFrame is and get you up and running in minutes.

:::warning Alpha software
FlowFrame is in early development. APIs and generated code may change between
releases. Use it for learning and experimentation — not production pipelines.
:::

## What is FlowFrame?

FlowFrame is a **local-first visual ETL builder**. It runs on **polars** by
default (or pandas, per run) and lets you:

- **Upload** CSV, Excel, or Parquet files
- **Build** data transformation pipelines visually (no coding required)
- **Preview** results in real-time
- **Execute** full flows with a single click
- **Export** equivalent Python code (both polars and pandas)
- **Schedule** flows to run automatically with a built-in cron scheduler

A drag-and-drop tool for building repeatable data cleaning and transformation workflows.

## How It Works

Upload your data, arrange nodes on a canvas, preview every step, then run the full
pipeline and export readable Python — all without writing a line of code.

<FlowPipeline :vertical="true" :nodes='[
  {"type":"input","label":"Upload Data","detail":"CSV, Excel, Parquet, or SQL"},
  {"type":"clean","label":"Build Your Pipeline","detail":"drag nodes · connect handles · configure each step"},
  {"type":"clean","label":"Live Preview","detail":"see your data transform on real rows instantly"},
  {"type":"transform","label":"Run the Full Flow","detail":"executes on polars (or pandas) · saves a run record"},
  {"type":"output","label":"Download Results + Python Code","detail":"standalone script — runs anywhere without FlowFrame"}
]' />

## Who is FlowFrame For?

- **Data Analysts** — Clean and explore data without SQL
- **Business Users** — Build repeatable workflows (no Python knowledge needed)
- **Python Learners** — See pandas operations visually
- **Educators** — Teach data cleaning interactively
- **Developers** — Quick-start Python ETL scripts

## What You'll Need

- **No Python knowledge required** — just point and click
- **A CSV or Excel file** — sample data to transform
- **A web browser** — Chrome, Firefox, Safari, or Edge
- **5 minutes** — to build your first flow

## What You Can't Do (Yet)

FlowFrame is designed for **local, single-machine data transformation**. It is
**not** an Airflow/Spark/dbt replacement and doesn't support:

- Distributed computing (Spark, Dask)
- Real-time streaming pipelines
- 100GB+ datasets
- Cross-flow DAG dependencies or complex orchestration
- Multi-user collaboration and enterprise permissions

It *does* include a lightweight cron scheduler for running a single flow on a
schedule — see [Scheduling](/guide/scheduling).

## Next Steps

1. **[Install FlowFrame](/guide/installation)** — get it running locally (2 minutes)
2. **[5-Minute Quick Start](/guide/quick-start)** — build your first flow
3. **[Interface Tour](/guide/interface)** — learn the UI
4. **[Transformation Reference](/transformations/overview)** — all available operations
5. **[Examples](/examples/sales-analysis)** — real-world workflows

## Quick Preview

Here's what FlowFrame looks like in action — a flow with real data loaded in the preview panel:

![FlowFrame editor with data preview — canvas, node palette, and 116-row preview table](/screenshots/editor-data-preview.png)

Here is what a typical sales-summary pipeline looks like in FlowFrame. Each colored
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

No! FlowFrame is designed for non-programmers. The visual editor guides you through each step.

### Can I save my flows?

Yes! Flows are saved to a database and can be run again anytime.

### Can I export as Python code?

Yes! Every flow generates readable **polars and pandas** code you can use in scripts or Jupyter notebooks.

### Is my data secure?

FlowFrame runs entirely locally on your machine. No data is sent anywhere. (No SaaS, no cloud uploads.)

### Can I use my own database?

Yes! Use a **SQL Input** or **SQL Output** node with a saved [Connection](/guide/connections). PostgreSQL, MySQL, SQLite, SQL Server, and MongoDB are supported.

## Still Have Questions?

- **[Troubleshooting Guide](/guide/troubleshooting)** — Common issues and solutions
- **[FAQ](/faq)** — More frequently asked questions
- **[GitHub Discussions](https://github.com/rodrigo-arenas/FlowFrame/discussions)** — Ask the community

---

**Ready to dive in?** [Install and get started →](/guide/installation)
