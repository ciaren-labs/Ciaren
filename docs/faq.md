---
title: Frequently Asked Questions
description: Common questions about Ciaren
search: faq help questions answers
---

# Frequently Asked Questions

## General Questions

### What is Ciaren?

Ciaren is a **local-first visual builder for data and ML workflows**. You build
data transformation and machine-learning pipelines by connecting nodes on a
canvas, preview real data at every step, run them on **polars** (default) or
**pandas**, and export the equivalent Python — readable code with no
proprietary runtime. In Ciaren, a saved pipeline is called a **flow**.

### Who created Ciaren?

Ciaren was created and is maintained by **Rodrigo Arenas**, a
machine-learning engineer and open-source creator —
[personal site](https://www.rodrigo-arenas.com/) ·
[GitHub](https://github.com/rodrigo-arenas) ·
[LinkedIn](https://www.linkedin.com/in/rodrigo-arenas-gomez/). It is open-core and
[contributions are welcome](https://github.com/ciaren-labs/Ciaren/blob/main/CONTRIBUTING.md).

### How much does Ciaren cost?

Nothing. Ciaren Core is **free and open source** under AGPL-3.0-only — the full
product, not a trial or a feature-limited tier. There are no paid features
today. If commercial offerings (official premium plugins, enterprise support)
ever ship, they will add things on top; **capabilities that exist in the open
core stay in the open core**.

### What does the AGPL license mean for me?

In plain language:

- **Using Ciaren** — locally or self-hosted inside your company — does not
  obligate you to open-source anything. AGPL source obligations apply when you
  *distribute Ciaren*, or *modify it and offer it to others over a network*.
- **Your flows, your data, and the Python code Ciaren exports are yours.**
  The exported code is ordinary pandas/polars with no Ciaren dependency, so
  the license doesn't follow it.
- **Plugins are not core.** The public Plugin API/SDK at
  `backend/app/plugin_api/` is Apache-2.0 precisely so plugin authors can pick
  their own license — open source, internal, or commercial.

This is a summary, not legal advice — see the [licensing section](https://github.com/ciaren-labs/Ciaren#licensing)
and the license texts for the exact terms.

### Can I build and sell a commercial plugin?

Yes. The Plugin SDK is Apache-2.0 and plugins choose their own license.
The packaging format supports free community plugins and signed commercial
plugins alike — see [Packaging & Distribution](/plugins/packaging-and-distribution).

### Why doesn't Ciaren include every connector in core?

Ciaren is open-core by design, and the core stays intentionally lightweight.
Built-in connectors focus on broadly useful databases, files, storage, and APIs.
Niche databases, SaaS products, internal APIs, and organization-specific systems
belong in plugins built with the public Plugin API/SDK. If the SDK is missing
something you need to build one, open an SDK issue or start a design discussion.

### Is Ciaren production-ready?

Not yet — Ciaren is **alpha software** (0.x). It's well suited for
exploration, prototyping, and controlled internal workflows, but flow formats,
APIs, and plugin interfaces may still change before 1.0.0, and there is no
backward-compatibility guarantee yet. Always test flows thoroughly before
running them on data you care about, and keep backups.

### Can I use Ciaren at work?

Yes, subject to the AGPL-3.0-only terms for Ciaren Core and the separate
Apache-2.0 terms for the public Plugin API/SDK. Review the
[security disclaimers](https://github.com/ciaren-labs/Ciaren/blob/main/SECURITY.md)
before using Ciaren with important data.

## Installation & Setup

### What are the system requirements?

- Python 3.12+ (backend)
- Node.js 18+ — only if you run the frontend from source; the PyPI install
  bundles the visual editor
- SQLite (default, no setup) — or PostgreSQL / MySQL via an async driver
- ~500MB free disk space

You can run the backend on its own and drive it through the
[REST API](/api/rest-api); Node.js is only needed for the visual editor.

### Can I run Ciaren on Windows?

Yes! Ciaren works on Windows, macOS, and Linux.

### Can I deploy Ciaren to the cloud?

Ciaren is local-first by design, and single-user: there are no accounts, roles,
or multi-tenancy. Running it on your own server or VM for yourself or a small
trusted group works (see [Docker](/guide/docker) and
[Advanced Setup](/guide/advanced-setup) for API tokens and reverse-proxy
guidance), but never expose it directly to the internet without an
authentication layer in front. A managed/hosted Ciaren service does not exist.

### How do I uninstall Ciaren?

If you installed from PyPI:

```bash
pip uninstall ciaren
```

Then remove the data directory (`.data` by default, or wherever
`CIAREN_DATA_DIR` points) if you also want to delete your uploaded files, run
outputs, and the SQLite database. If you instead cloned the repository, just
delete that folder. Either way, Ciaren doesn't touch anything outside its own
data directory, so there's no system-level uninstall step.

## Using Ciaren

### Do I need to know Python?

Not to build and run flows — the visual editor guides you through each step,
and previews show you the result of every node. But Ciaren is **Python-native
by design**: it gets most valuable when you (or a teammate) read, review, and
reuse the exported pandas/polars code. If you know some Python, you'll feel at
home; if you don't, the exported code is a good way to learn what your
pipeline actually does.

### Can I load data from a database?

Yes — via the **SQL input** node and a reusable [Connection](/guide/connections).
PostgreSQL, MySQL, SQLite, DuckDB, SQL Server, Snowflake, and MongoDB are
supported. S3, Azure Blob, and GCS are
also available as storage input/output nodes. Plain file formats (CSV, TSV,
Excel, Parquet, JSON/JSONL, text) are supported via file input nodes.
For other systems, use or build a connector plugin rather than expecting every
integration to become part of the open core.

### What's the maximum dataset size?

Ciaren is designed for **small-to-medium datasets** (up to a few GB). Exact limits depend on your available RAM.

### Can I schedule flows to run automatically?

Yes. Ciaren has a built-in cron scheduler: attach a `Schedule` (cron
expression + timezone, optional engine) to a flow and it runs automatically. The
scheduler handles retries, catch-up for missed slots, overlap protection, and
auto-disable on repeated failures. See [Scheduling](/guide/scheduling). (For
heavier orchestration, you can still export the Python and run it with your own
scheduler.)

### Can I run flows via command line?

Ciaren ships a `ciaren` CLI for running the server and managing config
(`ciaren serve | init | info | check`, among others) — see the
[CLI reference](/guide/cli).
There isn't a "run this flow id" subcommand; to run a flow headlessly, either
call the REST API (`POST /api/flows/{id}/runs`) or export it as Python and run
that script:

```bash
python my_flow.py
```

## Data & Privacy

### Is my data secure?

Ciaren runs **locally on your machine** — there's no SaaS, no cloud uploads,
and no telemetry. Data only leaves your machine when *you* configure it to:
a SQL/Mongo connection talks to your database, and S3/Azure/GCS nodes talk to
your storage, using credentials you control.

Two honest caveats: Ciaren is alpha software, it stores data unencrypted at
rest, and it assumes a trusted local environment (no authentication by
default). Read the [security policy](https://github.com/ciaren-labs/Ciaren/blob/main/SECURITY.md)
and the [local-first trust model](/security/local-first-trust-model) before
using it with sensitive data.

### Can I see what Ciaren does with my data?

Yes! Export the Python code and read it. You'll see exactly what operations run on your data.

### Can I use Ciaren offline?

Yes! Ciaren works completely offline once installed.

### Where is my data stored?

By default, in a local SQLite database (`ciaren.db`). Uploaded files,
outputs, and previews are written under the data directory (`.data` by default).
You can configure PostgreSQL or MySQL via `CIAREN_DATABASE_URL` (use an async
driver).

## Features & Limitations

### What transformations are available?

Ciaren ships **80 built-in nodes**: 66 transformation nodes plus file, SQL, and
storage input/output, including:

- Cleaning: drop/rename/select columns, fill/drop nulls, remove duplicates, filter rows, cast types, replace values, string ops, round, remove outliers
- Rows: sort, limit, sample
- Reshape, analytics & quality: calculated columns, group by + aggregate, join, union/concat, pivot, unpivot, rolling/window operations, date differences, and assertion nodes
- Charts: bar, line, area, scatter, pie, histogram, box plot, correlation heatmap — computed over full run data and stored on the run
- ML: train/test split, preprocessing, model training and evaluation nodes with optional MLflow tracking

[See full list →](/transformations/overview)

### Can I create custom transformations?

Yes, through plugins. A plugin can add a custom node to the editor palette,
execute it in previews/runs, and optionally export Python for it. Start with
[Build Your First Plugin](/plugins/first-plugin). For core contributions, you
can still add a built-in transformation to the backend engine.

### Can I join data from multiple sources?

A join node combines two datasets at a time. Chain multiple join nodes for more.

### Can I export as formats other than Python?

Ciaren exports Python — and for each flow it can generate the **pandas**,
**polars**, or **lazy polars** version, so you can use whichever library and
execution style you prefer.

### Does Ciaren support streaming data?

No. Ciaren is for local batch data workflows on files and databases.
Real-time streaming is not planned.

## Troubleshooting

:::info
Run `ciaren check` for a quick environment diagnostic. For API-level
debugging, the interactive docs at `http://localhost:8055/docs` let you inspect
requests and responses directly.
:::

### My changes aren't taking effect

Try:

1. Re-save the flow (`PUT /api/flows/{id}`) before running it
2. Restart the backend server if you changed code (or use `--reload`)

### Database connection fails

Check:

1. `CIAREN_DATABASE_URL` uses an **async** driver
   (`sqlite+aiosqlite://`, `postgresql+asyncpg://`, `mysql+aiomysql://`)
2. The database server is running (if using PostgreSQL or MySQL)
3. The matching async driver is installed (`asyncpg`, `aiomysql`)

The schema is created automatically on startup — there is no migration step to run.

See [Installation Guide](/guide/installation#troubleshooting) for more.

### "Port already in use" error

The backend uses port 8055. If it is occupied:

```bash
ciaren serve --port 8001
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

[Open an issue on GitHub](https://github.com/ciaren-labs/Ciaren/issues) with:

- What you expected to happen
- What actually happened
- Steps to reproduce
- Your system (OS, Python version, etc.)

### How do I suggest a feature?

[Open a discussion on GitHub](https://github.com/ciaren-labs/Ciaren/discussions) or [an issue](https://github.com/ciaren-labs/Ciaren/issues). For new connectors or product-specific integrations, start in Discussions and frame the idea as a plugin unless it exposes a core SDK gap.

### Can I contribute code?

Yes! See the [Contributing Guide](https://github.com/ciaren-labs/Ciaren/blob/main/CONTRIBUTING.md) for:

- How to set up development environment
- Code standards
- Testing expectations
- PR process

### Is Ciaren community-driven?

Ciaren is **built in the open** by a single maintainer today, and the goal is
for it to grow into a community project. Contributions, feedback, bug reports,
and plugins are all genuinely welcome — the direction is discussed publicly in
GitHub Discussions and Issues.

## More Questions?

- **[GitHub Discussions](https://github.com/ciaren-labs/Ciaren/discussions)** — Ask the community
- **[GitHub Issues](https://github.com/ciaren-labs/Ciaren/issues)** — Report bugs
- **[Troubleshooting Guide](/guide/troubleshooting)** — Common issues

---

Can't find your answer? [Open a discussion →](https://github.com/ciaren-labs/Ciaren/discussions)
