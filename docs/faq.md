---
title: Frequently Asked Questions
description: Common questions about FlowFrame
search: faq help questions answers
---

# Frequently Asked Questions

## General Questions

### What is FlowFrame?

FlowFrame is a **visual ETL builder** for pandas. It lets you build data transformation pipelines by dragging and dropping nodes instead of writing code.

### Who created FlowFrame?

FlowFrame is open-source and created by [Rodrigo Arenas](https://github.com/rodrigo-arenas). [Contributions welcome!](https://github.com/rodrigo-arenas/FlowFrame/blob/main/CONTRIBUTING.md)

### How much does FlowFrame cost?

FlowFrame is **free and open-source** under the MIT License. You can use it for personal and commercial projects.

### Is FlowFrame production-ready?

FlowFrame is in **active development**. It's suitable for learning, exploration, and personal use. For mission-critical pipelines, we recommend Airflow or dbt.

### Can I use FlowFrame at work?

Yes! The MIT license allows commercial use. However, note the [security disclaimers](https://github.com/rodrigo-arenas/FlowFrame/blob/main/SECURITY.md) about AI-generated code.

## Installation & Setup

### What are the system requirements?

- Python 3.11+
- Node.js 18+
- PostgreSQL, MySQL, or SQLite (SQLite is default)
- 500MB free disk space

### Can I run FlowFrame on Windows?

Yes! FlowFrame works on Windows, macOS, and Linux.

### Can I deploy FlowFrame to the cloud?

FlowFrame is designed for local use. Cloud deployment is not officially supported.

### How do I uninstall FlowFrame?

```bash
rm -rf FlowFrame
```

That's it! FlowFrame stores data in a local database and doesn't require system-level installation.

## Using FlowFrame

### Do I need to know Python?

No! FlowFrame is designed for non-programmers. The visual editor guides you through each step.

### Can I load data from a database?

FlowFrame currently supports CSV, Excel, and Parquet files. Loading from a database is not supported.

### What's the maximum dataset size?

FlowFrame is designed for **small-to-medium datasets** (up to a few GB). Exact limits depend on your available RAM. For 100GB+ datasets, use Spark or DuckDB.

### Can I schedule flows to run automatically?

Not from within FlowFrame. For scheduled production workflows, export the Python code and run it with your own scheduler, or use [Airflow](https://airflow.apache.org/).

### Can I run flows via command line?

You can export flows as Python code and run them with Python:

```bash
python my_flow.py
```

There is no dedicated FlowFrame CLI.

## Data & Privacy

### Is my data secure?

FlowFrame runs **entirely locally on your machine**. No data is sent anywhere. There's no SaaS, no cloud uploads, no tracking.

### Can I see what FlowFrame does with my data?

Yes! Export the Python code and read it. You'll see exactly what operations run on your data.

### Can I use FlowFrame offline?

Yes! FlowFrame works completely offline once installed.

### Where is my data stored?

By default, in a local SQLite database (`flowframe.db`). You can configure PostgreSQL or MySQL if you prefer.

## Features & Limitations

### What transformations are available?

16 transformation nodes plus file input/output, including:

- Cleaning: drop/rename/select columns, fill/drop nulls, remove duplicates, filter rows, change types, replace values, string ops, sort, limit
- Transform: calculated columns, group by + aggregate, join, union/concat

[See full list →](/transformations/overview)

### Can I create custom transformations?

Not yet in the UI, but you can extend the backend code by adding a transformation to the engine.

### Can I join data from multiple sources?

A join node combines two datasets at a time. Chain multiple join nodes for more.

### Can I export as formats other than Python?

FlowFrame exports Python (pandas) code.

### Does FlowFrame support streaming data?

No. FlowFrame is for batch ETL on files. Real-time streaming is not planned.

## Troubleshooting

### My changes aren't showing up

Try:

1. Hard refresh your browser: **Ctrl+Shift+R** (Windows/Linux) or **Cmd+Shift+R** (macOS)
2. Restart the frontend dev server
3. Restart the backend server

### Database connection fails

Check:

1. `DATABASE_URL` in your `.env` file
2. PostgreSQL is running (if using it)
3. Migrations ran: `alembic upgrade head`

See [Installation Guide](/guide/installation#troubleshooting) for more.

### "Port already in use" error

FlowFrame uses ports 8000 (backend) and 5173 (frontend). If occupied:

```bash
# Backend on different port
uvicorn app.main:app --reload --port 8001

# Frontend on different port
npm run dev -- --port 3000
```

### Preview isn't working

1. Ensure all nodes are connected
2. Check each node's configuration (look for red icons)
3. Verify your input data has headers

### Export doesn't work

1. Save the flow first
2. Check that the flow completes without errors
3. See generated Python code in browser console (`F12`)

## Contributing

### How do I report a bug?

[Open an issue on GitHub](https://github.com/rodrigo-arenas/FlowFrame/issues) with:

- What you expected to happen
- What actually happened
- Steps to reproduce
- Your system (OS, Python version, etc.)

### How do I suggest a feature?

[Open a discussion on GitHub](https://github.com/rodrigo-arenas/FlowFrame/discussions) or [an issue](https://github.com/rodrigo-arenas/FlowFrame/issues).

### Can I contribute code?

Yes! See [Contributing Guide](../CONTRIBUTING.md) for:

- How to set up development environment
- Code standards
- Testing expectations
- PR process

### Is FlowFrame community-driven?

Yes! We welcome contributions, feedback, and ideas from the community.

## Comparison with Other Tools

### FlowFrame vs Airflow

- **FlowFrame:** Simple, local, visual, no code needed
- **Airflow:** Complex, distributed, production-grade orchestration

Use Airflow if you need enterprise scheduling. Use FlowFrame if you want simplicity.

### FlowFrame vs dbt

- **FlowFrame:** Visual, SQL-agnostic, local-first
- **dbt:** SQL-focused, version control, data warehouse transformation

Use dbt if you're transforming warehouse data. Use FlowFrame if you're cleaning files.

### FlowFrame vs Zapier

- **FlowFrame:** Data transformation, no cost, open-source, no integrations
- **Zapier:** SaaS automation, 5000+ integrations, cloud-hosted

Use Zapier for SaaS automation. Use FlowFrame for data cleaning.

## More Questions?

- **[GitHub Discussions](https://github.com/rodrigo-arenas/FlowFrame/discussions)** — Ask the community
- **[GitHub Issues](https://github.com/rodrigo-arenas/FlowFrame/issues)** — Report bugs
- **[Troubleshooting Guide](/guide/troubleshooting)** — Common issues

---

Can't find your answer? [Open a discussion →](https://github.com/rodrigo-arenas/FlowFrame/discussions)
