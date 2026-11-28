---
layout: home
title: Ciaren — AI-native visual ETL with pandas and Polars export
titleTemplate: false
description: Describe a data or ML pipeline in plain language, review the flow Ciaren proposes, edit it on the canvas, run locally and export pandas or Polars code.
search: ciaren data engineering machine learning etl plugin platform visual polars pandas duckdb mlflow python code export local-first open source workflow builder
head:
  - - script
    - type: application/ld+json
    - |
      {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "Ciaren",
        "description": "Open-source visual ETL and ML workflow builder with an AI flow assistant that exports clean pandas and Polars Python code.",
        "applicationCategory": "DeveloperApplication",
        "operatingSystem": "Windows, macOS, Linux",
        "url": "https://ciaren.com",
        "license": "https://spdx.org/licenses/AGPL-3.0-only.html",
        "offers": {
          "@type": "Offer",
          "price": "0",
          "priceCurrency": "USD"
        },
        "sameAs": [
          "https://github.com/ciaren-labs/Ciaren",
          "https://pypi.org/project/ciaren/"
        ]
      }

hero:
  name: <span class="ciaren-c">C</span>iaren
  text: Describe the pipeline. Review it. Keep the pandas or Polars code.
  tagline: Ciaren is an open-source, local-first visual ETL and ML workflow builder. Bring your own provider API key and the AI flow assistant drafts complete flows from plain language, from cleaning and joins to charts and model training. You approve every proposal and can edit every node by hand. Building manually needs no API key.
  image:
    src: /logo.svg
    alt: Ciaren logo
  actions:
    - theme: brand
      text: AI quick start
      link: /guide/flow-assistant-quick-start
    - theme: alt
      text: Install Ciaren
      link: /guide/installation
    - theme: alt
      text: Manual quick start
      link: /guide/quick-start

features:
  - icon: ✨
    title: Prompt-to-flow assistant
    details: Describe the result you want. The assistant proposes inputs, cleaning, joins, reshaping, charts and ML training, cross-validation and evaluation. Nothing is saved until you approve it.

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

:::info The assistant is newer than the 0.3.1 release
The AI flow assistant is in the source tree but not in the published 0.3.1
package. `pip install ciaren` gives you the full manual editor. To use the
assistant today, run a source checkout or the Docker build. See the
[AI quick start](/guide/flow-assistant-quick-start).
:::

<div class="ciaren-proof-grid">
  <div class="ciaren-proof-card">
    <strong>80 nodes</strong>
    <span>files, SQL, storage, cleaning, reshape, quality checks, charts, ML, and outputs</span>
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

## From a Prompt to a Running Pipeline

1. **Describe.** In a flow, open **Assistant → Build** and write the result you
   want, for example "join orders with customers, compute revenue per country and
   chart it" or "train a random forest with 5-fold cross validation and show
   feature importance".
2. **Review.** The assistant checks its draft against the installed node catalog
   and your column types, then shows the nodes, every changed setting and the
   connections.
3. **Apply and save.** Nothing changes until you approve. **Activity** can preview
   and reverse a saved assistant change.
4. **Edit.** The proposal is ordinary nodes on the canvas. Change anything by
   hand, whenever you want.
5. **Run and export.** **Run** executes locally. The assistant never runs a flow.
   Export standalone pandas, Polars or lazy Polars Python.

It can propose file inputs and outputs, cleaning, joins, reshaping, data-quality
checks, charts, and machine learning (split, preprocessing, classifiers and
regressors, training, predict, evaluate, cross-validate, feature importance). It
does not write Python Transform nodes, SQL or cloud-storage connectors, or plugin
nodes. It works with OpenAI, Anthropic, DeepSeek or OpenCode Console keys saved
under **Connections → Assistant API keys**, and dataset rows are never sent to
the provider. [Set up the assistant →](/guide/flow-assistant-quick-start) ·
[What it can build, and what leaves your machine →](/guide/flow-assistant)

## Or Build It by Hand: Two Sources to a Model on One Canvas

Join a CSV file and a SQL table, clean each side, train a classifier, preview the
result on real data, and export it as clean Polars — without leaving the editor.

<div style="margin: 1.5rem 0 2.5rem; border-radius: 14px; overflow: hidden; box-shadow: 0 16px 48px -16px rgba(109,40,217,0.4); border: 1px solid var(--vp-c-divider);">
  <video autoplay loop muted playsinline aria-label="Demo of the Ciaren editor: a CSV file and a SQL table are joined, cleaned, and used to train a Random Forest classifier, previewed on real data, exported to Polars code, and run end to end" poster="/screenshots/hero-ml-pipeline-poster.jpg" style="display:block; width:100%; height:auto;">
    <source src="/hero-ml-pipeline.mp4" type="video/mp4" />
    <img src="/screenshots/hero-ml-pipeline.gif" alt="Ciaren editor: a File Input (CSV) and a SQL Input joined, cleaned, and fed through Scale Features, Train/Test Split, a Random Forest classifier and Predict — previewed on real data, exported to clean Polars code, run end to end, and inspected through a Bar Chart node rendering the predicted-status distribution" style="width:100%" />
  </video>
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
  <a class="ciaren-path-card" href="/guide/flow-assistant-quick-start">
    <span>For a fast first draft</span>
    <strong>Describe a flow and review the proposal</strong>
    <p>Add a provider API key, ask for a pipeline in plain language, inspect the nodes it proposes, then apply, edit and run them.</p>
  </a>
  <a class="ciaren-path-card" href="/guide/quick-start">
    <span>For first-time users</span>
    <strong>Build and run a real flow by hand in five minutes</strong>
    <p>Use the demo project or upload a small CSV, add cleaning and aggregation nodes, preview the result, run it, and export Python.</p>
  </a>
  <a class="ciaren-path-card" href="/guide/engines">
    <span>For Python engineers</span>
    <strong>Keep the generated code readable</strong>
    <p>Export pandas, polars, or lazy polars code that looks like code a person would write, with no hidden runtime dependency.</p>
  </a>
</div>

## Install and Open the Demo

For the PyPI package, the fastest way to evaluate Ciaren is a normal
Python install. The wheel bundles the web UI, so `ciaren serve` can start the
API, scheduler, and visual editor at one URL.

```bash
python -m pip install ciaren
ciaren serve
```

Open `http://localhost:8055`, then open **Projects → Demo**. You can inspect,
preview, run, and export working flows before uploading your own data. This
package is release 0.3.1, so it does not include the AI assistant yet; for the
assistant, follow the [AI quick start](/guide/flow-assistant-quick-start).

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

df_sales = pl.read_csv('sales.csv')

df_sales = (
    df_sales.drop_nulls(subset='amount')
    .group_by('region')
    .agg(pl.col('amount').sum())
)

df_sales.write_csv('summary.csv')
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
  <a href="/guide/flow-assistant-quick-start">Build a flow with the AI assistant</a>
  <a href="/guide/getting-started">Understand the project</a>
  <a href="/guide/installation">Install Ciaren</a>
  <a href="/guide/quick-start">Build your first flow by hand</a>
  <a href="/guide/demo-project">Explore the demo project</a>
  <a href="/examples/sales-analysis">Read an end-to-end example</a>
  <a href="/plugins/first-plugin">Build your first plugin</a>
  <a href="https://github.com/ciaren-labs/Ciaren/blob/main/CONTRIBUTING.md">Contribute</a>
</div>

## License

Ciaren Core is AGPL-3.0-only. The public Plugin API/SDK is Apache-2.0, and
plugins may use the license selected by their authors.
