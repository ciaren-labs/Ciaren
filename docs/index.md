---
layout: home
title: FlowFrame
description: Visual ETL builder for pandas — Simple, local-first data pipelines
search: flowframe etl visual pandas data pipeline

hero:
  name: FlowFrame
  text: Visual ETL for Everyone
  tagline: Build data pipelines with drag-and-drop. No code knowledge required.
  image:
    src: /logo.svg
    alt: FlowFrame
  actions:
    - theme: brand
      text: Get Started
      link: /guide/getting-started
    - theme: alt
      text: View on GitHub
      link: https://github.com/rodrigo-arenas/FlowFrame
    - theme: alt
      text: Transformations
      link: /transformations/overview

features:
  - icon: 👀
    title: Live Preview
    details: See your data transform in real-time before running the full pipeline.

  - icon: 📊
    title: Visual Builder
    details: Drag-and-drop nodes for filtering, joining, aggregating, and more. No code required.

  - icon: 🐍
    title: Export Python
    details: Generate readable, standalone Python code you can use anywhere.

  - icon: 🚀
    title: Local-First
    details: Runs entirely on your machine. No SaaS, no cloud lock-in, no subscriptions.

  - icon: 📁
    title: Many Formats
    details: Work with CSV, Excel, Parquet, and other formats seamlessly.

  - icon: ♾️
    title: Extensible
    details: Add custom transformation nodes to extend FlowFrame for your needs.
---

## Learn in 5 Minutes

1. **Upload** a CSV or Excel file
2. **Build** a flow with visual nodes
3. **Preview** results as you go
4. **Run** the full pipeline
5. **Export** as Python code

## Who Uses FlowFrame?

- **Data Analysts** — Clean and explore data visually
- **Business Users** — Build repeatable data workflows
- **Python Learners** — Learn pandas through visual examples
- **Educators** — Teach data cleaning interactively
- **Developers** — Quick-start pandas pipelines

## No Code, All Power

FlowFrame supports 25+ transformation nodes out of the box:

- **Cleaning:** Drop nulls, fill values, remove duplicates, rename columns
- **Transform:** Filter, aggregate, join, calculate columns
- **Reshape:** Group by, pivot, union, select
- **I/O:** CSV, Excel, Parquet input and output

[See all transformations →](/transformations/overview)

## Get Started Now

<div class="grid grid-cols-1 md:grid-cols-2 gap-4 my-8">

### Installation (2 minutes)
```bash
git clone https://github.com/rodrigo-arenas/FlowFrame
cd FlowFrame/backend
pip install -e .
uvicorn app.main:app --reload
```

[Full installation guide →](/guide/installation)

### Your First Flow (5 minutes)
1. Open http://localhost:5173
2. Upload `sample.csv`
3. Add 3 transformation nodes
4. Export Python code

[Quick start tutorial →](/guide/quick-start)

</div>

## Real-World Examples

- [Sales Data Analysis](/examples/sales-analysis) — Clean sales data, aggregate by region
- [Customer Segmentation](/examples/customer-segmentation) — Group customers by behavior
- [Time Series](/examples/time-series) — Resample and smooth time-based data
- [Data Quality](/examples/data-quality) — Validate and clean messy datasets

## Why FlowFrame?

| Feature | FlowFrame | Airflow | dbt | Spark |
|---------|-----------|---------|-----|-------|
| **Visual Editor** | ✓ | ✗ | ✗ | ✗ |
| **Code Export** | ✓ | ✗ | ✓ | ✗ |
| **Local-First** | ✓ | ✗ | ✓ | ✗ |
| **No Setup** | ✓ | ✗ | ✗ | ✗ |
| **Pandas** | ✓ | ✓ | ✗ | ✗ |
| **100+ nodes** | ✗ | ✓ | ✗ | ✓ |

FlowFrame doesn't compete with Airflow or Spark. It's designed for the 80% of ETL work: simple, repeatable pandas transformations on small-to-medium datasets.

## Community

- **Questions?** [GitHub Discussions](https://github.com/rodrigo-arenas/FlowFrame/discussions)
- **Found a bug?** [GitHub Issues](https://github.com/rodrigo-arenas/FlowFrame/issues)
- **Want to contribute?** [Contributing Guide](/guide/../CONTRIBUTING.md)

## License

MIT License — Free for personal and commercial use.

---

**Ready to build your first ETL flow?** [Get Started →](/guide/getting-started)
