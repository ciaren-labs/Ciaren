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

```
Your Data
   ↓
[Upload CSV/Excel]
   ↓
[Visual Pipeline Editor]
   ├─ Filter rows
   ├─ Rename columns
   ├─ Drop nulls
   ├─ Group & aggregate
   ├─ Join with other data
   └─ ...
   ↓
[Live Preview]
   ↓
[Run Pipeline]
   ↓
[Download Results + Python Code]
```

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
- Reading/writing directly to databases (it works with files)
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

Here's what a typical flow looks like:

```
[CSV Input: sales.csv]
          ↓
[Drop columns: "internal_id", "temp_notes"]
          ↓
[Filter rows: amount > 0]
          ↓
[Fill nulls: region = "Unknown"]
          ↓
[Group by region, Sum amount]
          ↓
[Rename columns: sum_amount → total_sales]
          ↓
[CSV Output: sales_summary.csv]
```

You build this in the visual editor by dragging nodes and clicking to configure them.

## FAQ

### Do I need to know Python?

No! FlowFrame is designed for non-programmers. The visual editor guides you through each step.

### Can I save my flows?

Yes! Flows are saved to a database and can be run again anytime.

### Can I export as Python code?

Yes! Every flow generates readable pandas code you can use in scripts or Jupyter notebooks.

### Is my data secure?

FlowFrame runs entirely locally on your machine. No data is sent anywhere. (No SaaS, no cloud uploads.)

### Can I use my own database?

Not currently. FlowFrame works with files (CSV, Excel, Parquet).

## Still Have Questions?

- **[Troubleshooting Guide](/guide/troubleshooting)** — Common issues and solutions
- **[FAQ](/faq)** — More frequently asked questions
- **[GitHub Discussions](https://github.com/rodrigo-arenas/FlowFrame/discussions)** — Ask the community

---

**Ready to dive in?** [Install and get started →](/guide/installation)
