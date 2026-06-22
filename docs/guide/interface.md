---
title: Interface Tour
description: The planned FlowFrame visual editor
search: interface ui tour navigation editor
---

# Interface Tour

:::warning In development
The visual editor (`frontend/`) is not shipped yet. This page describes the
intended interface. To use FlowFrame today, drive the backend through the
[REST API](/api/rest-api).
:::

## Planned layout

The visual editor will follow the [design system](/guide/design-system) and is
expected to include:

- **Canvas** — a node-based editor where each node maps to one pandas operation.
- **Node palette** — input, cleaning, transform, and output nodes grouped by
  category (see the [Transformations Reference](/transformations/overview)).
- **Config panel** — per-node settings (column selection, operators, target
  types, aggregations).
- **Live preview** — sample output that updates as you edit, backed by
  `POST /api/flows/{id}/preview`.
- **Code export** — readable pandas code from
  `POST /api/flows/{id}/export/python`.

## Use it today

Until the editor lands, the same capabilities are available over HTTP:

- Build the flow graph as JSON and save it with the flows endpoints.
- Preview and run it, then export Python.

See the [Quick Start](/guide/quick-start) for an end-to-end API walkthrough.
