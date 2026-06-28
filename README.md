<div align="center">

<img src="docs/public/FlowFrame.png" alt="FlowFrame" width="520" />

### Build, run, and schedule data pipelines — and train ML models — visually, no boilerplate required.

Upload a file, clean and reshape it on a drag-and-drop canvas, train and track
machine-learning models, preview every step, execute with one click, schedule
recurring runs, and export the equivalent pandas **or** polars code whenever you
need it.

[![Apache 2.0 License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue)](backend/pyproject.toml)
![React](https://img.shields.io/badge/React-18-blue)
![Status](https://img.shields.io/badge/Status-Alpha-orange)
[![Docs](https://img.shields.io/badge/docs-online-success)](https://rodrigo-arenas.github.io/FlowFrame)

[**Documentation**](https://rodrigo-arenas.github.io/FlowFrame) ·
[**Quick Start**](#-quick-start) ·
[**Transformations**](#%EF%B8%8F-transformation-nodes) ·
[**Plugins**](#-plugins--extensibility) ·
[**Contributing**](#-contributing)

</div>

---

> ⚠️ **Alpha software.** FlowFrame is in early development. APIs, the data model,
> and generated code may change without notice between releases, and there is no
> stability guarantee yet. Use it for experimentation — not production pipelines.

---

## What is FlowFrame?

FlowFrame is an open-source, **local-first** visual ETL (Extract, Transform, Load)
builder — with an optional **machine-learning** extension — for **small and medium
datasets**. It lets you:

- **Connect** CSV, Excel, or Parquet files — or read straight from a SQL database
- **Build** transformation pipelines on a drag-and-drop canvas
- **Preview** intermediate results before running the full flow
- **Execute** flows with a single click — on **polars** (default) or **pandas**
- **Export** the equivalent, readable Python — pandas, polars, or optimized lazy polars
- **Schedule** flows to run automatically with a built-in cron scheduler
- **Extend** the node palette with **plugins** — installable, signed packages that add
  your own nodes without touching FlowFrame's internals
- **Train** machine-learning models visually and track them with MLflow — an
  optional extension (`pip install "flowframe[ml]"`)

Each visual node maps to **one clear dataframe operation** — so the generated
code is readable whenever you export it, and execution is transparent. FlowFrame
is intentionally lightweight — it is **not** an Airflow/dbt/Spark replacement,
and does not do distributed or streaming execution.

Built for **data analysts, data engineers, and developers** who want repeatable
ETL pipelines without the infrastructure overhead — and accessible enough for
business analysts and Python beginners who are just getting started.

<div align="center">
  <img src="docs/public/screenshots/editor-full.png" alt="FlowFrame visual editor — building a join pipeline on the canvas" width="850" />
  <br />
  <em>The visual editor: drag nodes onto the canvas, wire them together, preview, run, and export.</em>
</div>

---

## 🤔 Why FlowFrame?

Most data cleaning lives in throwaway notebooks and one-off scripts that are hard
to re-run, share, or trust. Heavyweight orchestrators (Airflow, dbt, Spark) solve
a *different* problem and bring infrastructure you don't want for a 50 MB CSV.

FlowFrame sits in the gap:

- **No black box.** Every node maps to one dataframe operation, and you can export
  the exact pandas/polars code at any time — copy it and run it anywhere Python runs.
- **Local-first.** It runs entirely on your machine. No SaaS account, no cloud
  upload, no vendor lock-in.
- **Reproducible by default.** Versioned datasets, run history, and a built-in
  scheduler mean a flow you build today runs the same way next month.
- **Approachable.** A visual canvas lowers the barrier for analysts and Python
  beginners, while the code export keeps power users in control.

### See it: build visually, run instantly, export when you need to

A three-step flow (read → drop nulls → group & sum) runs with one click and
produces clean Python you can take anywhere:

```python
import polars as pl

df_1 = pl.read_csv("sales.csv")
df_2 = df_1.drop_nulls(subset=["amount"])
df_3 = df_2.group_by(["region"]).agg([pl.col("amount").sum().alias("amount")])
df_3.write_csv("summary.csv")
```

No proprietary runtime — copy the script and run it anywhere Python runs. Need it
to scale? Export the **lazy polars** variant (`scan_*` → `collect()`) for pushdown
and join optimization on large files.

---

## ✨ Key Features

| Feature | Details |
|---------|---------|
| **Visual Builder** | Drag-and-drop nodes for cleaning, reshaping, joining, and aggregating data |
| **28 Transformation Nodes** | From drop-nulls to window functions, joins, pivots, and conditional columns |
| **Live Preview** | See data changes at each step before running the full pipeline |
| **Code Export** | Download readable, standalone Python — pandas, polars, or optimized **lazy** polars |
| **polars or pandas** | Runs on polars by default; switch engines per run |
| **SQL Databases** | Read from and write to SQL databases via saved connections, alongside files |
| **Plugins** | Extend the node palette with installable, optionally **signed** plugin packages |
| **Local-First** | Runs entirely on your machine — no SaaS, no cloud lock-in |
| **Versioned Datasets** | Re-uploading a file keeps every version, so flows stay reproducible |
| **Scheduling** | Built-in cron scheduler with retries, catch-up, and auto-disable |
| **Projects & Runs** | Group work into projects; browse run history and per-node results |
| **Machine Learning** *(optional)* | Split, train, predict, and evaluate models on the canvas; tracked with MLflow |

---

## ⚡ Quick Start

### Requirements

- **Python 3.12+**
- **Node.js 18+** (only for the visual editor / frontend)
- **SQLite** is the zero-setup default. PostgreSQL / MySQL are optional, via
  `FLOWFRAME_DATABASE_URL` (async driver required).

### 1. Clone and start the backend

```bash
git clone https://github.com/rodrigo-arenas/FlowFrame.git
cd FlowFrame/backend

# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install FlowFrame (add the optional ML extension with: pip install -e ".[ml]")
pip install -e .

# Run the API + background scheduler in one process
flowframe serve
```

The backend starts on `http://localhost:8055` and **creates its database
automatically** on first start — there is no migration step to run. Open the
interactive API docs at `http://localhost:8055/docs`.

> `flowframe serve` is the recommended entry point. It also accepts flags such as
> `--port`, `--db-url`, `--engine`, and `--no-scheduler`. See `flowframe --help`,
> or use `flowframe init` / `info` / `check` to scaffold and validate config.

### 2. Start the frontend (visual editor)

```bash
cd ../frontend

npm install
npm run dev
```

The editor runs on `http://localhost:5173` and proxies API calls to the backend
on port `8055`.

### 3. Try it out

1. Open `http://localhost:5173`
2. Upload a CSV, Excel, or Parquet file
3. Build a flow (e.g. drop nulls → rename columns → filter rows → group & aggregate)
4. Preview results as you go
5. Run the flow, then export the generated Python code

Prefer the API? Everything above is also available over REST — see the
[Quick Start guide](https://rodrigo-arenas.github.io/FlowFrame/guide/quick-start).

---

## 🧪 Real-World Examples

Full, end-to-end walkthroughs with sample data live in the
[examples section of the docs](https://rodrigo-arenas.github.io/FlowFrame/examples/sales-analysis):

- **[Sales analysis](https://rodrigo-arenas.github.io/FlowFrame/examples/sales-analysis)** —
  clean raw sales data, derive metrics, and aggregate by region.
- **[Customer segmentation](https://rodrigo-arenas.github.io/FlowFrame/examples/customer-segmentation)** —
  join, bucket, and label customers for downstream analysis.
- **[Time-series prep](https://rodrigo-arenas.github.io/FlowFrame/examples/time-series)** —
  parse dates, extract parts, and roll up with window functions.
- **[Data quality checks](https://rodrigo-arenas.github.io/FlowFrame/examples/data-quality)** —
  enforce contracts (not-null, unique, value ranges) as part of a flow.

Every flow can be exported to standalone Python. For example, a join + calculated
column flow exports to readable polars:

```python
import polars as pl

customers = pl.read_csv("customers.csv")
orders = pl.read_csv("orders.csv")

joined = customers.join(orders, on="customer_id", how="left")
result = joined.with_columns(
    (pl.col("quantity") * pl.col("unit_price")).alias("line_total")
)
result.write_parquet("orders_enriched.parquet")
```

---

## 📚 Documentation

Full docs (guides, transformation reference, examples, API) are published at
**<https://rodrigo-arenas.github.io/FlowFrame>**.

| Resource | Link |
|----------|------|
| Getting started & concepts | [Guide](https://rodrigo-arenas.github.io/FlowFrame/guide/getting-started) |
| First flow in 5 minutes | [Quick Start](https://rodrigo-arenas.github.io/FlowFrame/guide/quick-start) |
| Every node, documented | [Transformations](https://rodrigo-arenas.github.io/FlowFrame/transformations/overview) |
| REST API reference | [API](https://rodrigo-arenas.github.io/FlowFrame/api/rest-api) |
| Writing a plugin | [Plugins](docs/plugins/writing-a-plugin.md) |
| FAQ | [FAQ](https://rodrigo-arenas.github.io/FlowFrame/faq) |
| Architecture & design | [architecture.md](architecture.md) |
| Contributing | [CONTRIBUTING.md](CONTRIBUTING.md) |

---

## 🛠️ Transformation Nodes

FlowFrame ships with file & SQL input/output plus **28 transformation nodes**. The
authoritative list lives in [`backend/app/engine/registry.py`](backend/app/engine/registry.py).

### Input / Output

- CSV, Excel, Parquet (read and write)
- SQL databases (read and write) via saved connections

### Cleaning & columns

- Drop / rename / select columns
- Change data types (cast)
- Drop nulls / fill nulls
- Remove duplicates
- Replace values, string operations, split a column, map values
- Round numbers, remove outliers

### Rows

- Filter rows, sort, limit, sample

### Reshape & combine

- Calculated column, conditional column, group by + aggregate
- Join / merge, union / concat
- Pivot, unpivot, window functions
- Parse dates, extract date parts, bin a column

### Data quality

- Assert not-null, unique, value range, expression, and row count — pass-through
  contract nodes that either fail the run or log a warning when violated

---

## 🧩 Plugins & Extensibility

Need a node FlowFrame doesn't ship? Write a **plugin**. A plugin is a small Python
package that contributes catalog nodes (and can ship **executable** runtimes that
run in previews, runs, and code export — exactly like a built-in node). Plugins
depend only on the public plugin API (`app.plugin_api`), never on FlowFrame's
private internals.

```bash
# Discover plugins from a local directory (no install needed)
export FLOWFRAME_PLUGINS_DIR=/path/to/your/plugins
flowframe serve

# Or install a packaged plugin
flowframe plugin install ./my-plugin.ffplugin

# Inspect, enable, disable, and verify plugins
flowframe plugin list
flowframe plugin enable  <plugin_id>
flowframe plugin disable <plugin_id>
flowframe plugin verify  ./my-plugin.ffplugin
```

Plugins can be packaged as portable `.ffplugin` files and **cryptographically
signed** (Ed25519). When you install with `--trusted`, FlowFrame refuses any
package that isn't signed by a key you trust:

```bash
# Publishers: generate a keypair, package, and sign
flowframe plugin keygen
flowframe plugin pack ./my-plugin ./my-plugin.ffplugin
flowframe plugin sign ./my-plugin.ffplugin

# Consumers: install only trusted, signed packages
flowframe plugin install ./my-plugin.ffplugin --trusted
```

A complete, runnable example — the smallest possible plugin that adds one node —
lives in [`examples/plugins/hello-node-plugin/`](examples/plugins/hello-node-plugin/),
with a pre-built signed package in [`examples/plugins/dist/`](examples/plugins/dist/).

**Learn more:**
[Writing a plugin](docs/plugins/writing-a-plugin.md) ·
[Packaging & distribution](docs/plugins/packaging-and-distribution.md)

---

## 🤖 Machine Learning (optional extension)

FlowFrame includes an optional, **high-guardrail** ML extension so you can go
from raw data to a tracked model without leaving the canvas. It is off by default
and ships as an extra:

```bash
pip install "flowframe[ml]"      # adds scikit-learn, XGBoost, LightGBM, MLflow
```

Once installed and enabled (`FLOWFRAME_ML_ENABLED=true`, the default), a
**Machine Learning** category appears in the node palette:

- **Train / Test Split** — one node, two clearly-labelled `train` / `test` outputs
- **Feature engineering** — Scale Features, Encode Categories, Select Features,
  Reduce Dimensions (PCA). *(Fill missing values with the standard Fill Nulls node.)*
- **Train Model** — pick a classifier, regressor, or clustering model; tune the
  common hyperparameters inline or open **Advanced options** for the full set,
  cross-validation, and in-pipeline preprocessing. The chosen model shows on the
  canvas node.
- **Predict** — score new data using a wired model or a registered MLflow model URI
- **Evaluate** & **Feature Importance** — metrics, confusion matrix, and rankings

Every trained model is logged to **MLflow**. A built-in **Local MLflow**
connection (in the Connections page) points at `./mlruns` by default and is the
single source of truth for the tracking URI — edit and test it to use any
tracking server, no restart needed. A dedicated **Models** page shows your
registered models (versions, aliases, metrics, and lineage back to the flow/run
that produced them) and an experiment leaderboard. Model loading is sandboxed to
a validated artifact directory.

The demo project ships ML example flows too (classification, train/validate,
regression, PCA); `flowframe serve --run-seed-flows` runs every demo flow once
on first boot so the Runs and Models views aren't empty. See the
[ML Quick Start](https://rodrigo-arenas.github.io/FlowFrame/guide/ml-quickstart).

---

## 🏗️ Tech Stack

**Backend:** Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2.x (async), pandas,
polars. Default dataframe engine is **polars**; pandas is fully supported and
selectable per run.

**Frontend:** React 18, TypeScript (strict), Vite, @xyflow/react, TanStack Query,
Zustand, shadcn/ui, Tailwind CSS.

**Database:** SQLite by default (file or in-memory). PostgreSQL / MySQL supported
via `DATABASE_URL` — **always use an async driver** (`sqlite+aiosqlite://`,
`postgresql+asyncpg://`, `mysql+aiomysql://`).

For the full picture, see [architecture.md](architecture.md).

---

## 🚦 Project Status

FlowFrame is **alpha** software under active development. The core engine,
transformations, scheduler, code export, and plugin system work today, but:

- The public API, data model, and generated code **may change between releases**.
- There is **no backward-compatibility guarantee** yet.
- It is meant for experimentation and local workflows — **not** mission-critical
  production pipelines.

Feedback at this stage is especially valuable — bug reports, rough edges, and
feature ideas all help shape what stabilizes first.

---

## 📋 Important Disclaimers

### ⚠️ AI-Generated Code

This project includes code generated or heavily assisted by AI tools. While every
effort is made to ensure correctness and quality, **we cannot guarantee**:

- **Security** — Code may contain vulnerabilities. Review before use in production.
- **Performance** — Generated code may not be optimal for large or complex transformations.
- **Reliability** — Bugs may exist despite testing. Always verify output first.

**Best practices:**

- Test flows thoroughly before running on important data
- Review exported Python code before deploying
- Report bugs and security issues responsibly (see [SECURITY.md](SECURITY.md))
- Do not use for mission-critical pipelines without additional validation

---

## 🤝 Contributing

Contributions are welcome and genuinely appreciated — whether you're fixing a bug,
adding a transformation, writing a plugin, or improving the docs. **New
contributors are welcome**: look for issues labelled
[`good first issue`](https://github.com/rodrigo-arenas/FlowFrame/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22)
to get started.

A typical contribution loop:

```bash
# 1. Fork the repo on GitHub, then clone your fork
git clone https://github.com/<your-username>/FlowFrame.git
cd FlowFrame/backend

# 2. Create an isolated environment and install dev dependencies
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 3. Make your change on a feature branch
git checkout -b my-feature

# 4. Run the test suite (uses in-memory SQLite)
pytest

# 5. Push and open a Pull Request
git push origin my-feature
```

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for environment setup, coding
standards, testing expectations, and the PR process. **Every new transformation
must include tests.** By participating you agree to our
[Code of Conduct](CODE_OF_CONDUCT.md).

---

## 💬 Community & Support

- **Questions or ideas?** Start a [GitHub Discussion](https://github.com/rodrigo-arenas/FlowFrame/discussions)
- **Found a bug or want a feature?** [Open an Issue](https://github.com/rodrigo-arenas/FlowFrame/issues)
- **Security concern?** Please follow [SECURITY.md](SECURITY.md) for responsible disclosure

---

## ⭐ Support the Project

If FlowFrame is useful to you, please consider
**[starring the repository](https://github.com/rodrigo-arenas/FlowFrame)** — it
helps others discover the project and motivates continued development. Sharing it
or contributing back means a lot too.

---

## 📜 License

FlowFrame is licensed under the **Apache License 2.0**. You are free to use,
modify, distribute, and commercialize this software, provided you include the
required copyright notices and license text. See [LICENSE](LICENSE) for details.

## 📝 Citation

If you use FlowFrame in academic work, you can cite it as:

```bibtex
@software{flowframe,
  author  = {Arenas, Rodrigo},
  title   = {FlowFrame: A local-first visual ETL builder},
  url     = {https://github.com/rodrigo-arenas/FlowFrame},
  year    = {2026}
}
```

---

## 🙏 Acknowledgments

- Created and maintained by **Rodrigo Arenas** — [rodrigo-arenas.com](https://www.rodrigo-arenas.com/) · [GitHub](https://github.com/rodrigo-arenas)
- Built with [FastAPI](https://fastapi.tiangolo.com/), [React Flow](https://reactflow.dev/),
  [pandas](https://pandas.pydata.org/), [polars](https://pola.rs/), and [shadcn/ui](https://ui.shadcn.com/)
- Inspired by the simplicity of pandas and the visual design of node-based editors

---

<div align="center">

**Made with ❤️ for data practitioners who value simplicity and reproducibility.**

</div>
