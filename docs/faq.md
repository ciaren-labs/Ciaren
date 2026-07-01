---
title: Frequently Asked Questions
description: Common questions about FlowFrame
search: faq help questions answers
---

# Frequently Asked Questions

## General Questions

### What is FlowFrame?

FlowFrame is a **local-first visual ETL builder**. It lets you build data
transformation pipelines by dragging and dropping nodes instead of writing code,
then run them on **polars** (default) or **pandas** and export the equivalent
Python.

### Who created FlowFrame?

FlowFrame was created and is maintained by **Rodrigo Arenas** —
[personal site](https://www.rodrigo-arenas.com/) ·
[GitHub](https://github.com/rodrigo-arenas). It is open-core and
[contributions are welcome](https://github.com/rodrigo-arenas/FlowFrame/blob/main/CONTRIBUTING.md).

### How much does FlowFrame cost?

FlowFrame Core is **free and open** under AGPL-3.0-only. The public
Plugin API/SDK at `backend/app/plugin_api/` is Apache-2.0 so plugin authors can
choose their own plugin licenses.

### Is FlowFrame production-ready?

FlowFrame is in **active development**. It's suitable for learning, exploration, and personal use. Always test flows thoroughly before running on production data.

### Can I use FlowFrame at work?

Yes, subject to the AGPL-3.0-only terms for FlowFrame Core and the separate
Apache-2.0 terms for the public Plugin API/SDK. Review the
[security disclaimers](https://github.com/rodrigo-arenas/FlowFrame/blob/main/SECURITY.md)
before using FlowFrame with important data.

## Installation & Setup

### What are the system requirements?

- Python 3.12+ (backend)
- Node.js 18+ (frontend / visual editor)
- SQLite (default, no setup) — or PostgreSQL / MySQL via an async driver
- ~500MB free disk space

You can run the backend on its own and drive it through the
[REST API](/api/rest-api); Node.js is only needed for the visual editor.

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

Yes — via the **SQL input** node and a reusable [Connection](/guide/connections).
PostgreSQL, MySQL, SQLite, and MongoDB are supported. S3, Azure Blob, and GCS are
also available as storage input/output nodes. Plain file formats (CSV, Excel, Parquet,
JSON, text) are supported via file input nodes.

### What's the maximum dataset size?

FlowFrame is designed for **small-to-medium datasets** (up to a few GB). Exact limits depend on your available RAM.

### Can I schedule flows to run automatically?

Yes. FlowFrame has a built-in cron scheduler: attach a `Schedule` (cron
expression + timezone, optional engine) to a flow and it runs automatically. The
scheduler handles retries, catch-up for missed slots, overlap protection, and
auto-disable on repeated failures. See [Scheduling](/guide/scheduling). (For
heavier orchestration, you can still export the Python and run it with your own
scheduler.)

### Can I run flows via command line?

FlowFrame ships a `flowframe` CLI for running the server and managing config
(`flowframe serve | init | info | check`) — see the [CLI reference](/guide/cli).
There isn't a "run this flow id" subcommand; to run a flow headlessly, either
call the REST API (`POST /api/flows/{id}/runs`) or export it as Python and run
that script:

```bash
python my_flow.py
```

## Data & Privacy

### Is my data secure?

FlowFrame runs **entirely locally on your machine**. No data is sent anywhere. There's no SaaS, no cloud uploads, no tracking.

### Can I see what FlowFrame does with my data?

Yes! Export the Python code and read it. You'll see exactly what operations run on your data.

### Can I use FlowFrame offline?

Yes! FlowFrame works completely offline once installed.

### Where is my data stored?

By default, in a local SQLite database (`flowframe.db`). Uploaded files,
outputs, and previews are written under the data directory (`.data` by default).
You can configure PostgreSQL or MySQL via `FLOWFRAME_DATABASE_URL` (use an async
driver).

## Features & Limitations

### What transformations are available?

42 transformation nodes plus file, SQL, and storage input/output, including:

- Cleaning: drop/rename/select columns, fill/drop nulls, remove duplicates, filter rows, cast types, replace values, string ops, round, remove outliers
- Rows: sort, limit, sample
- Reshape, analytics & quality: calculated columns, group by + aggregate, join, union/concat, pivot, unpivot, rolling/window operations, date differences, and assertion nodes

[See full list →](/transformations/overview)

### Can I create custom transformations?

Not yet in the UI, but you can extend the backend code by adding a transformation to the engine.

### Can I join data from multiple sources?

A join node combines two datasets at a time. Chain multiple join nodes for more.

### Can I export as formats other than Python?

FlowFrame exports Python — and for each flow it generates **both** the pandas and
the polars version, so you can use whichever library you prefer.

### Does FlowFrame support streaming data?

No. FlowFrame is for batch ETL on files. Real-time streaming is not planned.

## Troubleshooting

:::info
Run `flowframe check` for a quick environment diagnostic. For API-level
debugging, the interactive docs at `http://localhost:8055/docs` let you inspect
requests and responses directly.
:::

### My changes aren't taking effect

Try:

1. Re-save the flow (`PUT /api/flows/{id}`) before running it
2. Restart the backend server if you changed code (or use `--reload`)

### Database connection fails

Check:

1. `FLOWFRAME_DATABASE_URL` uses an **async** driver
   (`sqlite+aiosqlite://`, `postgresql+asyncpg://`, `mysql+aiomysql://`)
2. The database server is running (if using PostgreSQL or MySQL)
3. The matching async driver is installed (`asyncpg`, `aiomysql`)

The schema is created automatically on startup — there is no migration step to run.

See [Installation Guide](/guide/installation#troubleshooting) for more.

### "Port already in use" error

The backend uses port 8055. If it is occupied:

```bash
flowframe serve --port 8001
```

### Preview isn't working

1. Ensure every node is connected (each transform needs an input edge)
2. Check each node's `config` is valid for its type
3. Verify your input file has headers

### Export doesn't work

1. Save the flow first (`POST`/`PUT /api/flows`)
2. Make sure the graph has a valid input node and connected edges
3. Call `POST /api/flows/{id}/export/python` and read the returned code

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

## More Questions?

- **[GitHub Discussions](https://github.com/rodrigo-arenas/FlowFrame/discussions)** — Ask the community
- **[GitHub Issues](https://github.com/rodrigo-arenas/FlowFrame/issues)** — Report bugs
- **[Troubleshooting Guide](/guide/troubleshooting)** — Common issues

---

Can't find your answer? [Open a discussion →](https://github.com/rodrigo-arenas/FlowFrame/discussions)
