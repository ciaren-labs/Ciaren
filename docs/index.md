---
layout: home
title: Ciaren
description: Open-core, plugin-first platform for building data engineering and machine-learning workflows visually — and exporting clean, portable pandas/polars Python. Local-first, no lock-in.
search: ciaren data engineering machine learning etl plugin platform visual polars pandas duckdb mlflow python code export local-first

hero:
  name: <span class="ciaren-c">C</span>iaren
  text: Build data & ML workflows visually. Ship clean Python.
  tagline: An open-core, plugin-first, local-first platform for data engineering and machine learning — design workflows on a canvas, run them on polars or pandas, and export portable Python with no lock-in.
  image:
    src: /logo.svg
    alt: Ciaren
  actions:
    - theme: brand
      text: Get Started
      link: /guide/getting-started
    - theme: alt
      text: ⭐ Star on GitHub
      link: https://github.com/ciaren-labs/Ciaren
    - theme: alt
      text: Explore Plugins
      link: /plugins/overview

features:
  - icon: 🧩
    title: Plugin-First Platform
    details: Nodes, connectors, storage, execution engines, exporters, validators, and AI capabilities are all extension points. Build, package, sign, and share plugins.

  - icon: 🐍
    title: Python-Native, No Lock-In
    details: Every flow exports to readable, standalone pandas or polars code. No black box, no proprietary runtime — copy the script and run it anywhere.

  - icon: 🤖
    title: Data Engineering + ML
    details: One canvas for the whole lifecycle — ingest, clean, validate, engineer features, train, evaluate, and predict. ML is built in and tracked with MLflow.

  - icon: ⚙️
    title: Multi-Engine
    details: Runs on polars by default, switch to pandas per run — behind a pluggable engine contract designed to grow.

  - icon: 🔒
    title: Local-First
    details: Runs entirely on your machine. You own your data and execution — no SaaS, no cloud upload, no subscriptions.

  - icon: 👀
    title: Live Preview & Scheduling
    details: See your data transform on real rows before running the full pipeline, then schedule flows with a built-in cron scheduler.
---

:::warning Alpha software
Ciaren is in early development. APIs, the data model, and generated code may
change between releases. Use it for experimentation, prototypes, and controlled
internal workflows before relying on it for critical production jobs.
:::

## More Than a Visual Data Tool

Ciaren covers the **whole workflow lifecycle** on one canvas — and turns it into
portable Python. It's built on a few principles:

- **🧩 Plugin-first** — almost every capability is an extension point you can build on
- **🐍 Python-native** — export readable pandas/polars code anytime, no lock-in
- **🔒 Local-first** — your data and execution stay on your machine
- **⚙️ Multi-engine** — polars or pandas today, behind a pluggable engine contract

<FlowPipeline
  :nodes='[
    {"type":"input","label":"Ingest","detail":"CSV · Excel · Parquet · SQL · storage"},
    {"type":"clean","label":"Clean","detail":"nulls · types · dedupe · rename"},
    {"type":"transform","label":"Transform","detail":"join · group · pivot · window"},
    {"type":"clean","label":"Validate","detail":"not-null · unique · ranges · contracts"},
    {"type":"ml","label":"ML","detail":"split · train · evaluate · predict"},
    {"type":"output","label":"Export","detail":"Python code · file · SQL · storage"}
  ]'
/>

## What It Looks Like

![Ciaren editor — canvas with connected nodes, data preview panel showing 116 rows of joined customer-order data](/screenshots/editor-data-preview.png)

Cleaning and machine learning aren't separate tools — they're nodes on the same
canvas. Here a flow drops nulls and duplicates, then feeds straight into a
train/test split, a Random Forest regressor, prediction, and evaluation:

![Ciaren editor — one flow combining Drop Nulls and Remove Duplicates with Train/Test Split, Train Regressor, Predict, and Evaluate ML nodes](/screenshots/editor-clean-and-ml.png)

## Export to Clean, Portable Python

There's no black box. Every flow generates a readable, standalone script — copy it
and run it anywhere Python runs. Steps on a straight chain reuse one variable, the
way a person would write it. A read → drop-nulls → group-and-sum flow exports to:

```python
import polars as pl

df_1 = pl.read_csv("sales.csv")
df_1 = df_1.drop_nulls(subset=["amount"])
df_1 = df_1.group_by(["region"]).agg([pl.col("amount").sum().alias("amount")])
df_1.write_csv("summary.csv")
```

Need scale? Export the **lazy polars** variant (`scan_*` → `collect()`) for pushdown
and join optimization on large files. [Learn about engines →](/guide/engines)

## Extend Everything: the Plugin Platform

Ciaren is designed as an ecosystem. Its plugin API defines stable **provider
contracts** so nearly every capability can be added by a small Python package:

| Extend | Add |
| --- | --- |
| **Nodes** | New canvas operations that run end-to-end |
| **Connectors & storage** | New databases, APIs, and object stores |
| **Execution engines** | New dataframe engines beyond polars/pandas |
| **Exporters & validators** | New code targets and data-quality checks |
| **AI capabilities** | Pipeline builders, debuggers, optimizers |

Plugins can be packaged as portable `.ciarenplugin` files and **cryptographically
signed** — install only what you trust.

[Explore the plugin platform →](/plugins/overview)

## The Built-In Toolbox

42 transformation nodes plus file, SQL, and cloud-storage input/output out of the box:

- **Cleaning:** Drop/fill nulls, remove duplicates, rename/select columns, cast types
- **Transform:** Filter, aggregate, join, calculated columns, replace/round values
- **Reshape:** Group by, union, pivot, unpivot, bin, extract date parts, sort, sample
- **Data quality:** Assert not-null, unique, value range, expression, row count
- **I/O:** CSV, Excel, Parquet, SQL databases, and cloud storage (S3/GCS/Azure)

[See all transformations →](/transformations/overview)

## Who Uses Ciaren?

- **Data Engineers** — Build repeatable, reviewable pipelines without orchestration overhead
- **Developers** — Prototype visually, then export and version the generated Python
- **Plugin Authors** — Extend the platform with custom nodes, connectors, and engines
- **Data Scientists** — Go from raw data to a tracked model on one canvas
- **Data Analysts** — Clean, join, and explore data visually
- **Educators & Python Learners** — See pandas/polars operations come to life

## Get Started Now

<div class="grid grid-cols-1 md:grid-cols-2 gap-4 my-8">

### Installation (2 minutes)

```bash
git clone https://github.com/ciaren-labs/Ciaren
cd Ciaren/backend
pip install -e .
ciaren serve
```

The backend starts on `http://localhost:8055` and creates its database
automatically — including a seeded **Demo project** with sample datasets and
example flows to explore right away. To use the visual editor, also run the
frontend (`cd frontend && npm install && npm run dev`), or use
`docker compose up --build` to get both in one container.

[Full installation guide →](/guide/installation) ·
[Demo project tutorials →](/guide/demo-project)

### Explore the API (5 minutes)

1. Open the interactive docs at <http://localhost:8055/docs>
2. Upload a CSV with `POST /api/datasets/upload`
3. Create a flow with `POST /api/flows`
4. Export Python with `POST /api/flows/{id}/export/python`

[API reference →](/api/rest-api)

</div>

## Real-World Examples

### Data Engineering

- [Sales Data Analysis](/examples/sales-analysis) — Clean sales data, aggregate by region
- [Customer Segmentation](/examples/customer-segmentation) — Group customers by behavior
- [Time Series](/examples/time-series) — Resample and smooth time-based data
- [Data Quality](/examples/data-quality) — Validate and clean messy datasets
- [DuckDB Analytics](/examples/duckdb-analytics) — Query and write back a DuckDB database

### Machine Learning

- [Customer Churn Classification](/examples/ml-classification) — Split, train, evaluate, export
- [Feature Engineering](/examples/feature-engineering) — Scale, encode, select, reduce

In a hurry? Browse short [Recipes](/recipes/overview) for common tasks, or see
[how Ciaren compares](/guide/comparison) to notebooks and orchestrators.

## Why Ciaren?

| Capability | Details |
| --------- | --------- |
| **Plugin-First** | Nodes, connectors, engines, exporters, validators, and AI are all extensible |
| **Python-Native** | Every flow generates readable, standalone pandas/polars code — no lock-in |
| **Local-First** | Runs entirely on your machine — no accounts, no cloud upload |
| **Data Engineering + ML** | One canvas for ingest → transform → validate → train → predict |
| **Multi-Engine** | polars by default, pandas per run, pluggable engine contract for more |
| **Live Preview** | See data changes at each step before executing the full flow |
| **Open Core** | Core is AGPL-3.0; the public Plugin API/SDK is Apache-2.0 |

## How Ciaren Compares

Ciaren fills the gap between throwaway notebooks and heavyweight orchestrators:

- **vs. notebooks/scripts** — repeatable, reviewable, and visual, with the same code on export
- **vs. Airflow / dbt / Spark** — local-first and lightweight; no cluster or infra to run a flow
- **Not** a distributed/streaming engine — built for small and medium datasets on one machine

## Join the Community

Ciaren is an open, community-driven project. The best ways to get involved:

- ⭐ **[Star us on GitHub](https://github.com/ciaren-labs/Ciaren)** — it helps others discover the project
- 💬 **[Ask in Discussions](https://github.com/ciaren-labs/Ciaren/discussions)** — questions and ideas welcome
- 🐛 **[Report a bug](https://github.com/ciaren-labs/Ciaren/issues)** — or request a feature
- 🧩 **[Build a plugin](/plugins/overview)** — extend the platform and share it
- 🤝 **[Contribute](https://github.com/ciaren-labs/Ciaren/blob/main/CONTRIBUTING.md)** — good first issues are labelled

Created and maintained by [Rodrigo Arenas](https://www.rodrigo-arenas.com/), machine-learning engineer and open-source creator ([GitHub](https://github.com/rodrigo-arenas), [LinkedIn](https://www.linkedin.com/in/rodrigo-arenas-gomez/)).

## License

Ciaren Core is AGPL-3.0-only. The public Plugin API/SDK is Apache-2.0, and plugins may use the license selected by their authors.

---

**Ready to build your first data or ML workflow?** [Get Started →](/guide/getting-started) · [Explore Plugins →](/plugins/overview)
