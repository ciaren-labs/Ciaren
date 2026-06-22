---
layout: home
title: FlowFrame
description: Visual ETL builder — Simple, local-first data pipelines on polars or pandas
search: flowframe etl visual polars pandas data pipeline

hero:
  name: FlowFrame
  text: The simplest visual ETL builder
  tagline: Upload data, build a visual cleaning pipeline, preview, run it, and export readable Python — local-first, on polars or pandas.
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
  - icon: 📊
    title: Visual Builder
    details: Drag-and-drop nodes for cleaning, filtering, joining, aggregating, and more. No code required.

  - icon: 👀
    title: Live Preview
    details: See your data transform on real rows before running the full pipeline.

  - icon: 🐍
    title: Export Python
    details: Every flow exports to readable, standalone code — both polars and pandas.

  - icon: ⚡
    title: polars or pandas
    details: Runs on polars by default for speed; switch to pandas per run any time.

  - icon: 🚀
    title: Local-First
    details: Runs entirely on your machine. No SaaS, no cloud lock-in, no subscriptions.

  - icon: ⏰
    title: Scheduling
    details: A built-in cron scheduler runs flows automatically, with retries and catch-up.
---

:::warning Alpha software
FlowFrame is in early development. APIs, the data model, and generated code may
change between releases. Use it for experimentation — not production pipelines.
:::

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

FlowFrame supports 23 transformation nodes plus file input/output out of the box:

- **Cleaning:** Drop/fill nulls, remove duplicates, rename/select columns, cast types
- **Transform:** Filter, aggregate, join, calculated columns, replace/round values
- **Reshape:** Group by, union, pivot, unpivot, bin, extract date parts, sort, sample
- **I/O:** CSV, Excel, Parquet input and output

[See all transformations →](/transformations/overview)

## Get Started Now

<div class="grid grid-cols-1 md:grid-cols-2 gap-4 my-8">

### Installation (2 minutes)

```bash
git clone https://github.com/rodrigo-arenas/FlowFrame
cd FlowFrame/backend
pip install -e .
flowframe serve
```

The backend starts on `http://localhost:8000` and creates its database
automatically. To use the visual editor, also run the frontend (`cd frontend
&& npm install && npm run dev`).

[Full installation guide →](/guide/installation)

### Explore the API (5 minutes)

1. Open the interactive docs at <http://localhost:8000/docs>
2. Upload a CSV with `POST /api/datasets/upload`
3. Create a flow with `POST /api/flows`
4. Export Python with `POST /api/flows/{id}/export/python`

[API reference →](/api/rest-api)

</div>

## Real-World Examples

- [Sales Data Analysis](/examples/sales-analysis) — Clean sales data, aggregate by region
- [Customer Segmentation](/examples/customer-segmentation) — Group customers by behavior
- [Time Series](/examples/time-series) — Resample and smooth time-based data
- [Data Quality](/examples/data-quality) — Validate and clean messy datasets

## Why FlowFrame?

| Feature | Details |
|---------|---------|
| **Visual Editor** | Build pipelines by connecting nodes — no code required |
| **Code Export** | Every flow generates a readable, standalone Python script |
| **Local-First** | Runs entirely on your machine — no accounts, no cloud |
| **Live Preview** | See data changes at each step before executing the full flow |
| **polars or pandas** | Runs on polars by default; switch to pandas per run |
| **Open Source** | Apache 2.0 licensed — inspect, modify, and self-host freely |

## Community

- **Questions?** [GitHub Discussions](https://github.com/rodrigo-arenas/FlowFrame/discussions)
- **Found a bug?** [GitHub Issues](https://github.com/rodrigo-arenas/FlowFrame/issues)
- **Want to contribute?** [Contributing Guide](https://github.com/rodrigo-arenas/FlowFrame/blob/main/CONTRIBUTING.md)

## License

Apache License 2.0 — Free for personal and commercial use.

---

**Ready to build your first ETL flow?** [Get Started →](/guide/getting-started)
