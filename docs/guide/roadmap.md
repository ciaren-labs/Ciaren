---
title: Roadmap
description: Where Ciaren is today and the direction it's heading — toward a community ecosystem of plugins, connectors, engines, and AI capabilities.
search: roadmap direction future plugins marketplace ecosystem status alpha
---

# Roadmap

Ciaren is **alpha** (currently `0.1.x`). This page describes the direction, not
a dated release schedule. For exactly what's shipped, the code is authoritative and
releases are tracked on **[GitHub](https://github.com/rodrigo-arenas/FlowFrame/releases)**.

::: warning Alpha software
The public API, data model, and generated code may change between releases, with no
backward-compatibility guarantee yet. Use Ciaren for experimentation,
prototypes, and controlled internal workflows before relying on it for critical
production jobs.
:::

## Where it is today

The core platform works end to end:

- **Visual builder** with 42 transformation nodes plus file, SQL, and cloud-storage I/O
- **Multi-engine execution** — polars (default) and pandas, selectable per run
- **Python code export** — readable pandas, polars, or lazy-polars scripts
- **Data quality** contract nodes (assert not-null/unique/range/expression/row-count)
- **Machine Learning** (optional extension) — split, feature engineering, train,
  predict, evaluate, with MLflow tracking and a Models page
- **Scheduling** — built-in cron scheduler with retries, catch-up, and auto-disable
- **Plugin platform** — stable provider contracts, local + entry-point discovery,
  and signed `.ciarenplugin` packaging

## The direction

Ciaren is built to become an **extensible ecosystem**. The plugin
[provider contracts](/plugins/overview) are the foundation for growing the platform
from the outside — without bloating or forking the core:

- **A richer plugin ecosystem** — community nodes, connectors, templates, and integrations
- **More execution engines** via the `ExecutionProvider` contract
- **Custom exporters and validators** via their provider contracts
- **AI capabilities** (pipeline builders, debuggers, optimizers) via the `AIProvider` contract
- **Plugin distribution** — discovery and trusted, signed installation

These are designed extension points, not promises of specific dated features. The
core stays open and useful on its own.

## What Ciaren won't become

By design, Ciaren stays focused. It is **not** aiming to be a distributed/streaming
engine, a warehouse-scale orchestrator, or a multi-tenant SaaS. See
[How Ciaren Compares](/guide/comparison) for where it fits.

## Shape the roadmap

This is a community-driven project — the best way to influence direction is to get
involved:

- 💬 [Discussions](https://github.com/rodrigo-arenas/FlowFrame/discussions) — propose features and ideas
- 🐛 [Issues](https://github.com/rodrigo-arenas/FlowFrame/issues) — report bugs, request features
- 🧩 [Build a plugin](/plugins/overview) — extend the platform yourself
- 🤝 [Contribute](https://github.com/rodrigo-arenas/FlowFrame/blob/main/CONTRIBUTING.md) — good first issues are labelled
