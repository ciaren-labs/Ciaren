---
title: Projects & Runs
description: Organize work into projects, version datasets, and monitor runs
search: projects runs dataset versioning history run detail node results lineage
---

# Projects & Runs

Beyond the editor, FlowFrame helps you **organize** work and **monitor** what
happened when a flow ran.

## Projects

A **project** is a lightweight workspace that groups related datasets and flows.

- A `Default` project always exists, and every dataset and flow belongs to a
  project.
- Deleting a project moves its items back to `Default` rather than destroying
  them.
- The project list shows dataset and flow counts at a glance.

Over the API:

```bash
curl http://localhost:8000/api/projects
curl -X POST http://localhost:8000/api/projects \
  -H "Content-Type: application/json" -d '{"name": "Marketing"}'
```

You can scope dataset and flow listings to a project with `?project_id=...`.

## Datasets

Upload CSV, Excel, or Parquet files on the **Datasets** page. FlowFrame infers a
column schema and stores a small sample for previews.

```bash
curl -F "file=@sales.csv" "http://localhost:8000/api/datasets/upload?project_id={id}"
```

### Dataset versioning

Datasets are **immutable and versioned**. Re-uploading a file under the same name
appends a **new version** rather than overwriting the old one.

- An input node pins a dataset (optionally a specific `dataset_version`).
- A run records the **resolved versions** it used, so re-running — or a scheduled
  run weeks later — reads exactly the same data and stays reproducible.
- `GET /api/datasets/{id}/versions` lists versions newest-first;
  `GET /api/datasets/{id}/schema` and `.../sample` accept an optional `?version=`.

### Lineage

`GET /api/datasets/{id}/flows` lists the flows that use a dataset, so you can see
what a file feeds into before changing or removing it.

## Runs

Every execution creates a **run** with its status, timestamps, logs, the engine
used, and the resolved dataset versions. Browse them on the **Runs** page.

```bash
# List, with optional filters
curl "http://localhost:8000/api/runs?flow_id={id}&status=failed"

# One run, with per-node results
curl http://localhost:8000/api/runs/{run_id}
```

`GET /api/runs` is filterable by `flow_id`, `project_id`, `dataset_id`, `status`,
`schedule_id`, and date range.

### Run detail & per-node results

Opening a run (`/runs/:runId`) shows the flow as a read-only DAG. For each node
it reports:

- **status** — `success`, `failed`, or `skipped`,
- **rows** and **columns** of that node's output,
- a small **sample** of the data, and
- **`duration_ms`** — wall-clock time for the node, so you can find the slow step.

If a node fails, its error is captured and downstream nodes are marked `skipped`.
Output files are only written when **every** node succeeds.

### Triggers

Runs carry a `trigger` (and a `schedule_id` when applicable), so you can tell
manual runs apart from scheduled ones. See [Scheduling](/guide/scheduling).

## See also

- [Interface Tour](/guide/interface) — where these pages live
- [Engines](/guide/engines) — what the recorded engine means
- [REST API](/api/rest-api) — projects, datasets, and runs endpoints
