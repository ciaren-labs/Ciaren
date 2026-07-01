---
title: Datasets API
description: Upload and inspect versioned source files
search: api datasets upload versions schema sample lineage flows
---

# Datasets API

Upload and inspect source files (CSV, TSV, Excel, Parquet, JSON/JSONL, and text).
Datasets are **versioned**: re-uploading a file under the same name appends a
new immutable version, so flows pinned to an earlier version stay reproducible.

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/datasets/upload` | Upload a file (optionally `?project_id=`); creates a dataset or a new version |
| `GET` | `/api/datasets` | List datasets (optionally `?project_id=` and `?include_deleted=true`) |
| `GET` | `/api/datasets/{dataset_id}` | Get one dataset |
| `PATCH` | `/api/datasets/{dataset_id}` | Update dataset metadata/state; disabling cascades to flows that use it |
| `DELETE` | `/api/datasets/{dataset_id}` | Soft-delete a dataset; `?purge=true` deletes files immediately |
| `POST` | `/api/datasets/{dataset_id}/restore` | Restore a soft-deleted dataset |
| `POST` | `/api/datasets/purge-expired` | Permanently delete soft-deleted datasets past the retention window |
| `GET` | `/api/datasets/{dataset_id}/versions` | List all versions, newest first |
| `GET` | `/api/datasets/{dataset_id}/versions/{version_number}/download` | Download a specific dataset version file |
| `GET` | `/api/datasets/{dataset_id}/flows` | Flows that use this dataset (lineage) |
| `GET` | `/api/datasets/{dataset_id}/schema` | Inferred column schema (optionally `?version=`) |
| `GET` | `/api/datasets/{dataset_id}/sample` | Sample rows (optionally `?version=`) |
| `GET` | `/api/datasets/{dataset_id}/profile` | Column profile/statistics (optionally `?version=`) |

`POST /api/datasets/upload` uses multipart form data. Accepted extensions are
`.csv`, `.tsv`, `.xlsx`, `.xls`, `.parquet`, `.json`, `.jsonl`, and `.txt`.
Re-uploading under an existing name appends a version rather than replacing the
file.

Soft deletes retain files for `CIAREN_DATASET_RETENTION_DAYS` days by default.
Immediate purge refuses if a Production model was trained from the dataset unless
`?force=true` is supplied.

## See also

- [Projects API](./projects.md) · [Runs API](./runs.md)
- [Projects & Runs → Dataset versioning](/guide/projects-and-runs#dataset-versioning)
