---
title: How FlowFrame Compares
description: Where FlowFrame fits versus notebooks and scripts, heavyweight orchestrators like Airflow/dbt/Spark, and traditional visual ETL tools.
search: comparison flowframe vs notebooks jupyter airflow dbt spark alteryx knime visual etl alternative
---

# How FlowFrame Compares

FlowFrame fills a specific gap: a **visual, plugin-first, local-first** way to build
Data Engineering and ML workflows for small and medium datasets — that still exports
**clean, portable Python**. Here's how it relates to the tools you might already use.

::: tip TL;DR
- More **repeatable and reviewable** than a notebook — with the same code on export.
- Far **lighter** than Airflow/dbt/Spark — no cluster, no infra to run a flow.
- More **open and extensible** than closed visual ETL tools — and no lock-in.
:::

## vs. Notebooks & scripts (Jupyter, pandas/polars)

Notebooks are great for exploration but hard to keep repeatable: cells run out of
order, state leaks, and "rerun this monthly" turns into copy-paste.

| | Notebooks / scripts | FlowFrame |
| --- | --- | --- |
| Build experience | Write code cell by cell | Visual canvas, one node = one operation |
| Repeatability | Easy to run out of order | Topologically sorted, deterministic runs |
| Preview | Manual `df.head()` | Live preview at every step |
| Reuse | Copy-paste | Saved flows, parameters, schedules, run history |
| Output | The notebook | A saved flow **and** exported `.py` |

**Use FlowFrame when** you want a notebook's flexibility but a pipeline's
repeatability — and you still want the Python at the end.

## vs. Orchestrators (Airflow, dbt, Spark)

These solve a different problem: scheduling large DAGs across infrastructure, SQL
transformation graphs on a warehouse, or distributed compute.

| | Airflow / dbt / Spark | FlowFrame |
| --- | --- | --- |
| Scope | Cluster-scale orchestration / warehouse / big data | Single-machine ETL + ML |
| Setup | Servers, schedulers, warehouses | `pip install`, runs locally |
| Data size | Large / distributed | Small and medium |
| Transformations | SQL models / Python operators | Visual nodes → pandas/polars |
| Scheduling | Full DAG orchestration | Built-in single-flow cron scheduler |

**Use FlowFrame when** your data fits on one machine and you want to move fast
without standing up infrastructure. FlowFrame is **not** a replacement for these
tools at warehouse or cluster scale, and doesn't do distributed or streaming
execution.

## vs. Visual ETL tools

Traditional drag-and-drop ETL tools can be powerful but are often closed-source,
license-gated, and lock your logic into a proprietary format.

| | Closed visual ETL | FlowFrame |
| --- | --- | --- |
| License | Commercial / closed | Apache 2.0, open source |
| Where it runs | Vendor desktop/cloud | Your machine, local-first |
| Lock-in | Proprietary format | Exports standalone Python |
| Extensibility | Vendor plugins only | Plugin-first — add nodes, connectors, engines |
| ML | Add-on / separate | Built-in optional ML extension, MLflow-tracked |

**Use FlowFrame when** you want the approachability of a visual tool without giving
up ownership of your data, your execution, or your code.

## When *not* to use FlowFrame

Be honest about the boundaries — FlowFrame is intentionally lightweight and is
**not** designed for:

- Distributed or streaming pipelines (Spark, Flink, Kafka)
- 100GB+ datasets or warehouse-scale SQL transformation graphs
- Complex multi-flow DAG orchestration and dependencies
- Multi-user collaboration and enterprise permissions

For those, reach for the orchestrators above. For everything that fits on one
machine, FlowFrame keeps you fast and in control.

## Next steps

- [Get Started](/guide/getting-started) · [Quick Start (5 min)](/guide/quick-start)
- [Plugins Overview](/plugins/overview) — what makes it extensible
- [Engines (polars / pandas)](/guide/engines)
