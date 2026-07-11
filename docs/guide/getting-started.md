---
title: Getting Started
description: Understand what Ciaren is, who it is for, and the fastest path to try it
search: getting started introduction what is ciaren beginner technical overview
---

# Getting Started with Ciaren

Ciaren is a visual workflow builder for local data engineering and lightweight
machine-learning work. You build flows on a canvas, preview real data at each
step, run them locally, and export readable pandas, polars, or lazy polars
Python.

If you are new to the project, start here. This page gives you the mental model
before you install anything.

:::warning Alpha software
Ciaren is in early development. APIs, generated code, workflow files, and plugin
contracts may change between releases. Use it for learning, experimentation,
prototypes, and controlled internal workflows before relying on it for critical
production jobs.
:::

## The Short Version

Ciaren sits between three familiar tools:

| If you know... | Ciaren feels like... |
| --- | --- |
| **Spreadsheets** | A repeatable, inspectable flow instead of a sequence of manual edits |
| **Notebooks/scripts** | A visual way to design pipelines that still exports normal Python |
| **Orchestrators** | A lighter local tool for building and running one flow without cluster setup |

It is not trying to hide Python. It is trying to make dataframe workflows easier
to design, inspect, teach, share, and export.

## What You Can Build

<FlowPipeline :vertical="true" :nodes='[
  {"type":"input","label":"Bring data in","detail":"CSV, Excel, Parquet, JSON, SQL, storage"},
  {"type":"clean","label":"Clean and shape it","detail":"nulls · types · dedupe · rename · filter"},
  {"type":"transform","label":"Transform it","detail":"join · group · aggregate · pivot · window"},
  {"type":"clean","label":"Validate it","detail":"not-null · unique · ranges · expressions"},
  {"type":"ml","label":"Train or score models","detail":"split · train · evaluate · predict · MLflow"},
  {"type":"output","label":"Send it out","detail":"file · SQL · storage · Python export"}
]' />

Each node has configuration, preview output, and generated code. That matters:
you can explain a flow to a beginner, inspect it as an engineer, and move the
result into a regular Python workflow when you need full control.

## Why Ciaren Exists

Many data tools force an early tradeoff:

- spreadsheets are approachable, but hard to reproduce and review;
- notebooks are flexible, but can become fragile execution histories;
- orchestration systems are powerful, but heavy for local exploration;
- no-code tools can be fast, but often trap work inside a proprietary runtime.

Ciaren's answer is a local, plugin-first workflow model where the visual graph is
the product experience and Python export is the escape hatch. You can start with
the UI and still end with code.

## Who It Is For

- **Data analysts:** clean, join, validate, and export datasets without writing
  every operation by hand.
- **Python learners:** see how visual dataframe operations become pandas and
  polars code.
- **Data engineers:** prototype repeatable flows locally, review generated code,
  and use the CLI/API for automation.
- **ML practitioners:** move from raw data to tracked lightweight ML workflows on
  the same canvas.
- **Plugin authors:** add custom nodes, connectors, engines, model providers,
  exporters, and validators without changing core.
- **Contributors:** improve the editor, execution engine, transformations,
  examples, docs, tests, and plugin SDK.

## What You Need First

For the fastest evaluation:

- **Python 3.12+** for the PyPI package;
- **Docker** if you prefer an isolated container;
- **a browser** to open the visual editor;
- **five minutes** to inspect the Demo project or build a small flow.

You do not need your own dataset. Fresh installs seed a
[Demo project](/guide/demo-project) with sample datasets and working flows.

## Choose Your Path

| Goal | Start here |
| --- | --- |
| "I just want to see it running" | [Installation](/guide/installation), install from PyPI or use Docker, then open the Demo project |
| "I want to build my first flow" | [Quick Start](/guide/quick-start) |
| "I want to understand the UI" | [Interface Tour](/guide/interface) |
| "I want a realistic example" | [Sales Analysis](/examples/sales-analysis) or [Data Quality Checks](/examples/data-quality) |
| "I care about generated code" | [Engines and Python export](/guide/engines) |
| "I want to automate it" | [CLI Reference](/guide/cli), [REST API](/api/rest-api), and [Python SDK](/guide/sdk) |
| "I want to extend it" | [Plugins Overview](/plugins/overview) and [Build Your First Plugin](/plugins/first-plugin) |
| "I want to contribute" | [CONTRIBUTING.md](https://github.com/ciaren-labs/Ciaren/blob/main/CONTRIBUTING.md) and [Roadmap](/guide/roadmap) |

## What Ciaren Is Not

Ciaren is designed for local, single-machine workflows. It is not currently:

- a distributed compute engine like Spark;
- a real-time streaming platform;
- a full Airflow/dbt replacement;
- a multi-user enterprise collaboration system;
- a tool for unbounded 100GB+ local datasets.

It does include a lightweight scheduler for running individual flows on a cron
schedule. See [Scheduling](/guide/scheduling).

## Quick Preview

![Ciaren editor with data preview, node palette, canvas, and configuration panel](/screenshots/editor-data-preview.png)

Here is the kind of pipeline you will build in the
[Quick Start](/guide/quick-start):

<FlowPipeline :nodes='[
  {"type":"input","label":"File Input","detail":"sales.csv"},
  {"type":"clean","label":"Drop Nulls","detail":"remove rows missing amount"},
  {"type":"clean","label":"Remove Duplicates","detail":"dedupe repeated orders"},
  {"type":"transform","label":"Group By + Aggregate","detail":"sum amount by region"},
  {"type":"output","label":"File Output","detail":"sales_summary.csv"}
]' />

## Next Step

Install Ciaren and open the Demo project:

```bash
python -m pip install ciaren
ciaren serve
```

Then open `http://localhost:8055`.

[Continue to Installation →](/guide/installation)
