---
title: Datasets API
description: Upload and inspect versioned source files
search: api datasets upload versions schema sample lineage flows
---

# Datasets API

Upload and inspect source files (CSV, Excel, Parquet). Datasets are **versioned**:
re-uploading a file under the same name appends a new immutable version, so flows
pinned to an earlier version stay reproducible.

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/datasets/upload` | Upload a file (optionally `?project_id=`); creates a dataset or a new version |
| `GET` | `/api/datasets` | List datasets (optionally `?project_id=`) |
| `GET` | `/api/datasets/{dataset_id}` | Get one dataset |
| `GET` | `/api/datasets/{dataset_id}/versions` | List all versions, newest first |
| `GET` | `/api/datasets/{dataset_id}/flows` | Flows that use this dataset (lineage) |
| `GET` | `/api/datasets/{dataset_id}/schema` | Inferred column schema (optionally `?version=`) |
| `GET` | `/api/datasets/{dataset_id}/sample` | Sample rows (optionally `?version=`) |

`POST /api/datasets/upload` uses multipart form data. Re-uploading under an
existing name appends a version rather than replacing the file.

## See also

- [Projects API](./projects.md) · [Runs API](./runs.md)
- [Projects & Runs → Dataset versioning](/guide/projects-and-runs#dataset-versioning)
