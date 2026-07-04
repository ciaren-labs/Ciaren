---
layout: home
title: Ciaren
description: Open-core, plugin-first platform for building data engineering and machine-learning workflows visually, running them locally, and exporting clean pandas/polars Python.
search: ciaren data engineering machine learning etl plugin platform visual polars pandas duckdb mlflow python code export local-first open source workflow builder

hero:
  name: <span class="ciaren-c">C</span>iaren
  text: Visual data and ML workflows that stay Python-native.
  tagline: Build pipelines on a canvas, preview every step on real data, run locally, and export readable pandas, polars, or lazy polars code with no proprietary runtime.
  image:
    src: /logo.svg
    alt: Ciaren
  actions:
    - theme: brand
      text: Start in 5 Minutes
      link: /guide/quick-start
    - theme: alt
      text: Install Locally
      link: /guide/installation
    - theme: alt
      text: Star on GitHub
      link: https://github.com/ciaren-labs/Ciaren

features:
  - icon: 🧩
    title: Plugin-first by design
    details: Nodes, connectors, storage, engines, exporters, validators, and AI capabilities are extension points, not afterthoughts.

  - icon: 🐍
    title: Clean Python export
    details: Every flow can become standalone pandas, polars, or lazy polars code that you can review, version, and run outside Ciaren.

  - icon: 🔒
    title: Local-first execution
    details: Run on your machine or self-hosted infrastructure. Use SQLite by default, keep data under your control, and avoid SaaS lock-in.

  - icon: ⚙️
    title: Built for data engineering and ML
    details: Ingest, clean, validate, engineer features, train, evaluate, predict, export, schedule, and automate from one workflow model.

  - icon: 👀
    title: Live preview at each node
    details: Inspect row samples, schema changes, and node results before committing to a full run.

  - icon: 🛡️
    title: Trustable extensions
    details: Package plugins as portable .ciarenplugin files, sign them, audit permissions, and install only what you trust.
---

:::warning Alpha software
Ciaren is in early development. APIs, the data model, generated code, and plugin
contracts may change between releases. It is already useful for learning,
experimentation, prototypes, and controlled internal workflows, but you should
test carefully before using it for critical production jobs.
:::

<div class="ciaren-proof-grid">
  <div class="ciaren-proof-card">
    <strong>40+ nodes</strong>
    <span>files, SQL, storage, cleaning, reshape, quality checks, ML, and outputs</span>
  </div>
  <div class="ciaren-proof-card">
    <strong>3 Python targets</strong>
    <span>pandas, eager polars, and lazy polars export from the same flow</span>
  </div>
  <div class="ciaren-proof-card">
    <strong>Open core</strong>
    <span>AGPL-3.0 core with Apache-2.0 public Plugin API/SDK</span>
  </div>
  <div class="ciaren-proof-card">
    <strong>Runs locally</strong>
    <span>SQLite by default, optional external databases and object storage</span>
  </div>
</div>

## See the Whole System

Ciaren is not only a drag-and-drop editor. It is a local workflow platform with a
transparent execution model: every canvas node maps to an understandable
dataframe operation, every run leaves inspectable results, and every flow can be
exported to ordinary Python.

<FlowPipeline
  :nodes='[
    {"type":"input","label":"Ingest","detail":"CSV · Excel · Parquet · SQL · storage"},
    {"type":"clean","label":"Clean","detail":"nulls · types · dedupe · rename"},
    {"type":"transform","label":"Transform","detail":"join · group · pivot · window"},
    {"type":"clean","label":"Validate","detail":"not-null · unique · ranges · contracts"},
    {"type":"ml","label":"ML","detail":"split · train · evaluate · predict"},
    {"type":"output","label":"Export","detail":"Python · file · SQL · storage"}
  ]'
/>

![Ciaren editor with a canvas of connected nodes and a live data preview table](/screenshots/editor-data-preview.png)

## Why People Try It

<div class="ciaren-path-grid">
  <a class="ciaren-path-card" href="/guide/quick-start">
    <span>For first-time users</span>
    <strong>Build and run a real flow in five minutes</strong>
    <p>Use the demo project or upload a small CSV, add cleaning and aggregation nodes, preview the result, run it, and export Python.</p>
  </a>
  <a class="ciaren-path-card" href="/guide/engines">
    <span>For Python engineers</span>
    <strong>Keep the generated code readable</strong>
    <p>Export pandas, polars, or lazy polars code that looks like code a person would write, with no hidden runtime dependency.</p>
  </a>
  <a class="ciaren-path-card" href="/plugins/overview">
    <span>For contributors and builders</span>
    <strong>Extend the platform instead of forking it</strong>
    <p>Add custom nodes, connectors, model providers, engines, validators, and exporters through the plugin architecture.</p>
  </a>
</div>

## Install and Open the Demo

For the alpha package on PyPI, the fastest way to evaluate Ciaren is a normal
Python install. The wheel bundles the web UI, so `ciaren serve` can start the
API, scheduler, and visual editor at one URL.

```bash
python -m pip install --pre ciaren
ciaren serve
```

Open `http://localhost:8055`, then open **Projects → Demo**. You can inspect,
preview, run, and export working flows before uploading your own data.

Prefer an isolated container instead?

```bash
git clone https://github.com/ciaren-labs/Ciaren.git
cd Ciaren
docker compose up --build
```

Use the [Installation guide](/guide/installation) for PyPI alpha installs,
Docker, source installs, optional ML extras, database drivers, and development
setup.

## What Makes It Different

| Decision | What it means in practice |
| --- | --- |
| **Local-first** | Your data does not need to leave your machine. SQLite works out of the box, and external services are opt-in. |
| **Python-native** | Visual work stays portable because flows export to readable dataframe code. |
| **Plugin-first** | Niche connectors, internal APIs, custom model providers, and specialized nodes can live outside core. |
| **Multi-engine** | polars is the default engine, pandas is available per run, and the engine contract is designed to grow. |
| **Data quality included** | Assertions for not-null, uniqueness, value ranges, expressions, row counts, and allowed values are first-class nodes. |
| **Automation-ready** | Use the CLI, REST API, webhook trigger, scheduler, and Python SDK for controlled local or self-hosted workflows. |

## Export to Portable Python

There is no black box. A simple read → clean → aggregate → write flow can export
to code like this:

```python
import polars as pl

df_1 = pl.read_csv("sales.csv")
df_1 = df_1.drop_nulls(subset=["amount"])
df_1 = df_1.group_by(["region"]).agg([pl.col("amount").sum().alias("amount")])
df_1.write_csv("summary.csv")
```

For larger files, export the lazy polars variant (`scan_*` → `collect()`) to use
pushdown and query optimization where the engine supports it.
[Learn about engines →](/guide/engines)

## From Cleaning to Machine Learning

Cleaning, validation, feature engineering, training, prediction, and evaluation
are all workflow nodes. You can move from raw data to a tracked model without
switching tools, and still export or inspect the underlying Python.

![Ciaren editor showing cleaning nodes feeding Train/Test Split, Train Regressor, Predict, and Evaluate nodes](/screenshots/editor-clean-and-ml.png)

## The Built-In Toolbox

- **Input and output:** CSV, TSV, Excel, Parquet, JSON/JSONL, text, SQL databases, S3, GCS, and Azure Blob
- **Cleaning:** drop/fill nulls, remove duplicates, rename/select/drop columns, cast types
- **Transformation:** filters, joins, group by, aggregate, calculated columns, maps, pivots, windows
- **Data quality:** assert not-null, unique, value ranges, row count, expressions, allowed values
- **Machine learning:** split, train, cross-validate, predict, evaluate, feature engineering, importance
- **Operations:** run history, scheduling, REST API, CLI, webhook trigger, Python SDK

[Browse all transformations →](/transformations/overview)

## Built for Extension

Ciaren's plugin API defines provider contracts for capabilities that should not
be hard-coded into core:

| Extend | Examples |
| --- | --- |
| **Nodes** | Custom transforms, validators, AI-assisted steps, domain-specific operations |
| **Connectors and storage** | Internal APIs, SaaS tools, warehouses, object stores, document databases |
| **Model providers** | Local models, scikit-learn estimators, organization-specific training logic |
| **Execution engines** | Alternative dataframe engines and future runtime targets |
| **Exporters** | New code targets, deployment bundles, validation reports |

The open core stays focused on the shared platform. When you need a niche
integration, the preferred path is a plugin that can be packaged, signed, shared,
and versioned independently.

[Explore the plugin platform →](/plugins/overview)

## Pick Your Next Step

<div class="ciaren-next-grid">
  <a href="/guide/getting-started">Understand the project</a>
  <a href="/guide/installation">Install Ciaren</a>
  <a href="/guide/quick-start">Build your first flow</a>
  <a href="/guide/demo-project">Explore the demo project</a>
  <a href="/examples/sales-analysis">Read an end-to-end example</a>
  <a href="/plugins/first-plugin">Build your first plugin</a>
  <a href="https://github.com/ciaren-labs/Ciaren">Star on GitHub</a>
  <a href="https://github.com/ciaren-labs/Ciaren/blob/main/CONTRIBUTING.md">Contribute</a>
</div>

## License

Ciaren Core is AGPL-3.0-only. The public Plugin API/SDK is Apache-2.0, and
plugins may use the license selected by their authors.
