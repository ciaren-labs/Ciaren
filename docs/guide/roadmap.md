---
title: Roadmap
description: Where Ciaren is today and the direction it's heading — toward a stable, local-first platform with plugins, connectors, exports, data quality, ML, and AI extension points.
search: roadmap direction future plugins marketplace ecosystem status alpha connectors exporters data quality machine learning ai scheduling security
---

# Roadmap

Ciaren is **alpha** (currently `0.1.x`). This page describes the direction, not
a dated release schedule. For exactly what's shipped, the code is authoritative and
releases are tracked on **[GitHub](https://github.com/ciaren-labs/Ciaren/releases)**.

::: warning Alpha software
The public API, data model, and generated code may change between releases, with no
backward-compatibility guarantee yet. Use Ciaren for experimentation,
prototypes, and controlled internal workflows before relying on it for critical
production jobs.
:::

## Where it is today

The core platform works end to end:

- **Visual builder** with 40+ transformation nodes plus file, SQL, and cloud-storage I/O
- **Multi-engine execution** — polars (default) and pandas, selectable per run
- **Python code export** — readable pandas, polars, or lazy-polars scripts
- **Data quality** contract nodes (assert not-null/unique/range/expression/row-count)
- **Machine Learning** (optional extension) — split, feature engineering, train,
  predict, evaluate, with MLflow tracking and a Models page
- **Scheduling** — built-in cron scheduler with retries, catch-up, and auto-disable
- **Plugin platform** — stable provider contracts, local + entry-point discovery,
  and signed `.ciarenplugin` packaging

## The direction

Ciaren is built to become a stable, **local-first** workflow platform with an
extensible ecosystem around it. The plugin
[provider contracts](/plugins/overview) are the foundation for growing the
platform from the outside — without bloating or forking the core.

These are roadmap themes, not promises of specific dated features.

### Stable foundation

- **Alpha hardening** — stabilize the public API, data model, generated code,
  and behavior of core nodes before moving beyond `0.1.x`.
- **Portable flow format** — formalize `.flow` files with schema versioning,
  JSON Schema, migrations, and required plugin/capability declarations.
- **Backend source of truth** — move node metadata into the backend catalog and
  have the frontend consume a complete `GET /api/catalog/nodes` response.

### Plugin ecosystem

- **Plugin lifecycle** — continue improving discovery, loading, permissions,
  signature verification, install, update, disable, and uninstall flows.
- **Community distribution** — prepare a lightweight index or marketplace for
  discovering nodes, connectors, templates, exporters, validators, and
  integrations.
- **Production plugin examples** — document richer plugin patterns beyond the
  hello-world node, including tests, packaging, permissions, and code export.

### Connectors and data access

- **More connectors** — expand database, file, API, and storage integrations
  while keeping credentials explicit and local-first.
- **Better browsing** — improve remote file and table discovery for SQL,
  object storage, and local-folder connections.
- **Connection diagnostics** — make test results, permission errors, and setup
  hints more actionable.

### Exporters and portability

- **More export targets** — explore notebooks, reusable job templates, and other
  portable artifacts beyond standalone Python scripts.
- **Export validation** — add checks that generated artifacts can run and match
  the visual flow behavior.
- **Reusable handoff** — make exported code easier to version, review, and run
  in another environment.

### Data quality

- **Reusable contracts** — strengthen validation nodes as first-class data
  contracts that can be reused across flows.
- **Quality reports** — surface which checks passed or failed per run, with
  samples of problematic rows when possible.
- **Validation exports** — explore exporting quality checks into external test
  or validation formats.

### Machine Learning

- **ML workflow maturity** — improve metrics, model comparison, lineage, and the
  Models page.
- **MLflow integration** — make registered model workflows, aliases, and
  tracking configuration clearer.
- **Guardrails** — add stronger warnings for data leakage, risky splits, missing
  evaluation, and fragile training configurations.
- **ML templates** — provide starter flows for common classification,
  regression, clustering, and feature-engineering tasks.

### AI capabilities

- **AI as an extension point** — introduce AI capabilities through providers,
  not as a required dependency of the core app.
- **Assistive workflows** — explore pipeline generation, flow debugging,
  optimization suggestions, and plain-language explanations of errors.
- **Data-control safeguards** — keep any AI integration explicit about what data
  is used, where it goes, and how users can opt in or out.

### Scheduling and automation

- **Schedule observability** — improve visibility into upcoming runs, missed
  runs, retries, failures, and auto-disabled schedules.
- **Automation triggers** — continue improving REST, CLI, and webhook-based ways
  to run flows outside the UI.
- **Lightweight orchestration** — keep scheduling simple enough for local and
  self-hosted workflows.

### User experience and documentation

- **Debuggability** — improve per-node errors, preview failures, and flow-level
  troubleshooting.
- **Onboarding** — add more demo projects, recipes, screenshots, and sample
  datasets for real workflows.
- **Contributor paths** — make it easier to add nodes, connectors, exporters,
  validators, docs, and tests.

### Security and trust

- **Plugin trust model** — harden permission prompts, signed packages, and
  manifest validation.
- **Operational guidance** — document recommended practices for sensitive data,
  self-hosting, backups, and access control.
- **Security review readiness** — keep security-sensitive areas testable and
  auditable as the project matures.

## What Ciaren won't become

By design, Ciaren stays focused. It is **not** aiming to become:

- **A real-time streaming engine** — batch-style data and ML workflows remain
  the product center.
- **A warehouse-scale orchestrator** — heavy production orchestration belongs in
  dedicated tools; Ciaren should export clean code and integrate with them.
- **A multi-tenant SaaS** — the core project stays local-first and self-hosted.
- **A black-box runtime** — users should be able to inspect, export, and own the
  code their flows represent.

See [How Ciaren Compares](/guide/comparison) for where it fits.

## Shape the roadmap

This is a community-driven project — the best way to influence direction is to get
involved:

- 💬 [Discussions](https://github.com/ciaren-labs/Ciaren/discussions) — propose features and ideas
- 🐛 [Issues](https://github.com/ciaren-labs/Ciaren/issues) — report bugs, request features
- 🧩 [Build a plugin](/plugins/overview) — extend the platform yourself
- 🤝 [Contribute](https://github.com/ciaren-labs/Ciaren/blob/main/CONTRIBUTING.md) — good first issues are labelled
