# FlowFrame

> **Visual ETL builder for analysts and developers** — Upload data, build a transformation pipeline visually, preview results, run it, and export readable Python.

[![Apache 2.0 License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.12%2B-blue)
![React](https://img.shields.io/badge/React-18-blue)
![Status](https://img.shields.io/badge/Status-Alpha-orange)

---

> ⚠️ **Alpha software.** FlowFrame is in early development. APIs, the data model,
> and generated code may change without notice between releases, and there is no
> stability guarantee yet. Use it for experimentation — not production pipelines.

---

## What is FlowFrame?

FlowFrame is an open-source, **local-first** visual ETL (Extract, Transform, Load)
builder for **small and medium datasets**. It lets you:

- **Upload** CSV, Excel, or Parquet files
- **Build** transformation pipelines on a drag-and-drop canvas
- **Preview** intermediate results before running the full flow
- **Execute** flows with a single click — on **polars** (default) or **pandas**
- **Export** the equivalent, readable Python code (both polars and pandas)
- **Schedule** flows to run automatically with a built-in cron scheduler

It maps each visual node to one clear dataframe operation, so the generated code
stays educational and easy to read. FlowFrame is intentionally lightweight — it is
**not** an Airflow/dbt/Spark replacement, and does not do distributed or streaming
execution.

Built for analysts, data-curious business users, Python learners, developers who
want quick repeatable pipelines, and educators.

---

## ✨ Key Features

| Feature | Details |
|---------|---------|
| **Visual Builder** | Drag-and-drop nodes for cleaning, reshaping, joining, and aggregating data |
| **Live Preview** | See data changes at each step before running the full pipeline |
| **Code Export** | Download readable, standalone Python — both polars and pandas |
| **polars or pandas** | Runs on polars by default; switch engines per run |
| **Local-First** | Runs entirely on your machine — no SaaS, no cloud lock-in |
| **Versioned Datasets** | Re-uploading a file keeps every version, so flows stay reproducible |
| **Scheduling** | Built-in cron scheduler with retries, catch-up, and auto-disable |
| **Projects & Runs** | Group work into projects; browse run history and per-node results |
| **Extensible** | Add custom transformation nodes on the backend |

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

# Install FlowFrame
pip install -e .

# Run the API + background scheduler in one process
flowframe serve
```

The backend starts on `http://localhost:8000` and **creates its database
automatically** on first start — there is no migration step to run. Open the
interactive API docs at `http://localhost:8000/docs`.

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
on port `8000`.

### 3. Try it out

1. Open `http://localhost:5173`
2. Upload a CSV, Excel, or Parquet file
3. Build a flow (e.g. drop nulls → rename columns → filter rows → group & aggregate)
4. Preview results as you go
5. Run the flow, then export the generated Python code

Prefer the API? Everything above is also available over REST — see the
[Quick Start guide](https://rodrigo-arenas.github.io/FlowFrame/guide/quick-start).

---

## 📚 Documentation

Full docs (guides, transformation reference, examples, API) are published at
**<https://rodrigo-arenas.github.io/FlowFrame>**.

- **[CONTRIBUTING.md](CONTRIBUTING.md)** — How to contribute, code standards, testing
- **[CLAUDE.md](CLAUDE.md)** — Product vision, tech stack, and development principles
- **[architecture.md](architecture.md)** — System design, entity models, and execution flow

---

## 🛠️ Transformation Nodes

FlowFrame ships with file input/output plus **23 transformation nodes**. The
authoritative list lives in [`backend/app/engine/registry.py`](backend/app/engine/registry.py).

### Input / Output

- CSV, Excel, Parquet (read and write)

### Cleaning & columns

- Drop / rename / select columns
- Change data types (cast)
- Drop nulls / fill nulls
- Remove duplicates
- Replace values, string operations
- Round numbers, remove outliers

### Rows

- Filter rows, sort, limit, sample

### Reshape & combine

- Calculated column, group by + aggregate
- Join / merge, union / concat
- Pivot, unpivot, extract date parts, bin a column

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

We welcome contributions! Whether you're fixing bugs, adding transformations,
improving docs, or building features — your work helps make FlowFrame better.

**First time?** See [CONTRIBUTING.md](CONTRIBUTING.md) for environment setup, code
style, testing expectations, and the PR process. Every new transformation must
include tests.

**Ideas?** Open a [GitHub Discussion](https://github.com/rodrigo-arenas/FlowFrame/discussions)
or [Issue](https://github.com/rodrigo-arenas/FlowFrame/issues).

---

## 📜 License

FlowFrame is licensed under the **Apache License 2.0**. You are free to use,
modify, distribute, and commercialize this software, provided you include the
required copyright notices and license text. See [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/), [React Flow](https://reactflow.dev/),
  [pandas](https://pandas.pydata.org/), [polars](https://pola.rs/), and [shadcn/ui](https://ui.shadcn.com/)
- Inspired by the simplicity of pandas and the visual design of node-based editors

---

## 📞 Support

- **Questions?** [GitHub Discussions](https://github.com/rodrigo-arenas/FlowFrame/discussions)
- **Found a bug?** [Open an Issue](https://github.com/rodrigo-arenas/FlowFrame/issues)
- **Security concern?** See [SECURITY.md](SECURITY.md)

---

**Made with ❤️ for data enthusiasts who value simplicity.**
