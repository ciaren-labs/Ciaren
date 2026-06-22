# FlowFrame

> **Simple visual ETL for analysts and developers** — No Airflow complexity, no enterprise bloat. Just drag, drop, preview, and export.

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![React](https://img.shields.io/badge/React-18-blue)
![Status](https://img.shields.io/badge/Status-Active%20Development-green)

---

## What is FlowFrame?

FlowFrame is an open-source visual ETL (Extract, Transform, Load) builder designed for **small and medium datasets**. It lets you:

- **Upload** CSV, Excel, or Parquet files
- **Build** data transformation pipelines with a drag-and-drop interface
- **Preview** intermediate results before running
- **Execute** full flows with a single click
- **Export** the generated Python code to use anywhere

Perfect for analysts, data-curious business users, and Python learners who want to build repeatable ETL pipelines without wrestling with Airflow or Spark.

---

## 🎯 Key Features

| Feature | Details |
|---------|---------|
| **Visual Builder** | Drag-and-drop ETL nodes (filters, joins, aggregations, pivots) |
| **Live Preview** | See data changes before running the full pipeline |
| **Code Export** | Download readable, standalone Python scripts |
| **Local-First** | Run entirely on your machine — no SaaS, no cloud lock-in |
| **Pandas-Based** | Works with familiar pandas transformations |
| **Type-Safe** | Full TypeScript + Pydantic validation |
| **Extensible** | Easy to add custom transformation nodes |

---

## ⚡ Quick Start

### Requirements

- Python 3.11+
- Node.js 18+
- PostgreSQL (or configure SQLite for local development)

### 1. Clone and Setup Backend

```bash
git clone https://github.com/rodrigo-arenas/FlowFrame.git
cd FlowFrame/backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up database
alembic upgrade head

# Start server
uvicorn app.main:app --reload
```

Backend runs on `http://localhost:8000`

### 2. Setup Frontend

```bash
cd ../frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Frontend runs on `http://localhost:5173`

### 3. Try It Out

1. Open http://localhost:5173
2. Upload a CSV or Excel file
3. Build a simple flow (e.g., drop nulls → rename columns → filter rows)
4. Preview results
5. Export the generated Python code

---

## 📚 Documentation

- **[CONTRIBUTING.md](CONTRIBUTING.md)** — How to contribute, code standards, testing
- **[CLAUDE.md](CLAUDE.md)** — Detailed product vision, tech stack, and development principles
- **[architecture.md](architecture.md)** — System design, entity models, and execution flow

---

## 🛠️ Transformation Nodes (MVP)

### Input
- CSV / Excel / Parquet

### Cleaning
- Drop/Rename columns
- Filter rows
- Fill/Drop null values
- Remove duplicates
- Change data types
- Sort data
- Add calculated columns

### Transform
- Select columns
- Group by + Aggregate
- Join / Merge
- Union / Concat

### Output
- CSV / Excel / Parquet export

---

## 🏗️ Tech Stack

**Backend:** Python 3.11, FastAPI, SQLAlchemy, Pydantic, Pandas
**Frontend:** React, TypeScript, Vite, @xyflow/react, TanStack Query, Zustand, Tailwind CSS
**Database:** PostgreSQL (or SQLite for dev)

---

## 📋 Important Disclaimers

### ⚠️ AI-Generated Code

This project includes code generated or heavily assisted by AI tools (Claude). While every effort is made to ensure correctness and quality, **we cannot guarantee**:

- **Security** — Code may contain vulnerabilities. Please review before use in production.
- **Performance** — Generated code may not be optimal for large datasets or complex transformations.
- **Reliability** — Bugs may exist despite testing. Always verify output in development first.

**Best practices:**
- Test flows thoroughly before running on production data
- Review exported Python code before deploying
- Report bugs and security issues responsibly (see [SECURITY.md](SECURITY.md))
- Do not use for mission-critical pipelines without additional validation

---

## 🤝 Contributing

We welcome contributions! Whether you're fixing bugs, adding transformations, improving docs, or building features — your work helps make FlowFrame better for everyone.

**First time?** See [CONTRIBUTING.md](CONTRIBUTING.md) for:
- How to set up a development environment
- Code style and testing expectations
- The PR and review process
- Where to ask questions

**Ideas?** Open a [GitHub Discussion](https://github.com/rodrigo-arenas/FlowFrame/discussions) or [Issue](https://github.com/rodrigo-arenas/FlowFrame/issues).

---

## 📜 License

MIT License — See [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/), [React Flow](https://reactflow.dev/), and [shadcn/ui](https://ui.shadcn.com/)
- Inspired by the simplicity of pandas and the visual design of [n8n](https://n8n.io/) and [Zapier](https://zapier.com/)

---

## 📞 Support

- **Questions?** Open a [GitHub Discussion](https://github.com/rodrigo-arenas/FlowFrame/discussions)
- **Found a bug?** [Open an Issue](https://github.com/rodrigo-arenas/FlowFrame/issues)
- **Security concern?** See [SECURITY.md](SECURITY.md)

---

**Made with ❤️ for data enthusiasts who value simplicity.**
