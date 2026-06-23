---
title: File input (CSV / Excel / Parquet)
description: Read an uploaded dataset into a flow
search: input csv excel parquet read dataset version source
---

# File input

Load data from a dataset you've uploaded into the flow. This is usually the first
node in a pipeline. `type`: `csvInput`, `excelInput`, `parquetInput` — one per
file format, each reading the matching dataset kind.

## Use cases

- Start a pipeline from a CSV, Excel, or Parquet file you uploaded.
- Pin a flow to a **specific dataset version** so scheduled runs stay
  reproducible even after the file is re-uploaded.

## Configuration

| Config key | Type | Required | Description |
|---|---|---|---|
| `dataset_id` | string | Yes | The dataset to read |
| `dataset_version` | int | No | Pin a specific version (defaults to latest) |

The config form only offers datasets whose `source_type` matches the node — a
`csvInput` node lists CSV datasets, etc.

## Generated Python code

```python
df_1 = pd.read_csv("sales.csv")
```

Excel and Parquet emit `pd.read_excel(...)` / `pd.read_parquet(...)`.

## Tips & common mistakes

- **Pin a version for repeatable runs.** Leaving `dataset_version` empty always
  reads the latest upload; pinning makes a flow deterministic. See
  [Dataset versioning](/guide/projects-and-runs#dataset-versioning).
- **No datasets listed?** Upload one first on the Datasets page — the form warns
  when no compatible dataset exists for the node's format.

## See also

- [SQL input](./sql-input.md) — read live from a database instead of a file
- [Projects & Runs](/guide/projects-and-runs) — datasets, versions, and runs
- [Datasets API](/api/datasets)
