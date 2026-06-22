---
title: Quick Start (5 Minutes)
description: Build and run your first ETL flow with the FlowFrame API
search: quick start tutorial first flow api
---

# Quick Start (5 Minutes)

This walkthrough builds your first pipeline end to end. The visual editor is in
progress, so for now you drive FlowFrame through its REST API. The fastest way
to follow along is the interactive docs at `http://localhost:8000/docs`.

## Prerequisites

- The backend running locally (see [Installation](/guide/installation))
- A small CSV file to upload (any file with a header row works)

## 1. Start the backend

```bash
cd backend
uvicorn app.main:app --reload
```

It serves on `http://localhost:8000` and creates its database automatically.

## 2. Upload a dataset

```bash
curl -F "file=@sales.csv" http://localhost:8000/api/datasets/upload
```

The response includes the dataset `id`. Inspect it with:

```bash
curl http://localhost:8000/api/datasets/{dataset_id}/schema
curl http://localhost:8000/api/datasets/{dataset_id}/sample
```

## 3. Create a flow

A flow is a React Flow-compatible graph: an input node that reads the dataset,
one or more transformation nodes, and edges connecting them. Post it to:

```bash
curl -X POST http://localhost:8000/api/flows \
  -H "Content-Type: application/json" \
  -d @flow.json
```

See the [Transformations Reference](/transformations/overview) for the available
node types and their configuration.

## 4. Preview, then run

```bash
# Preview the output without recording a run
curl -X POST http://localhost:8000/api/flows/{flow_id}/preview

# Execute the full pipeline
curl -X POST http://localhost:8000/api/flows/{flow_id}/runs \
  -H "Content-Type: application/json" -d '{}'

# Check status, output location, and logs
curl http://localhost:8000/api/runs/{run_id}
```

## 5. Export Python

```bash
curl -X POST http://localhost:8000/api/flows/{flow_id}/export/python
```

You get standalone, readable pandas code you can run anywhere — in a script or a
Jupyter notebook.

## Next Steps

- [Transformations Reference](/transformations/overview) — all node types
- [REST API Reference](/api/rest-api) — every endpoint
- [Getting Started](/guide/getting-started) — concepts and FAQ
