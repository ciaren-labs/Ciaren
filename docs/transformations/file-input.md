---
title: File input (CSV / Excel / Parquet / JSON / Text)
description: Read an uploaded dataset into a flow
search: input csv excel parquet json text read dataset version source
---

# File input

Load data from a dataset you've uploaded into the flow. This is usually the first
node in a pipeline. There is one node type per file format:

| Node type | Format | Reads |
|---|---|---|
| `csvInput` | CSV | Comma-separated values |
| `excelInput` | Excel | `.xlsx` / `.xls` workbooks |
| `parquetInput` | Parquet | Columnar binary format |
| `jsonInput` | JSON | JSON array or records |
| `textInput` | Text | Plain text, one row per line → single `text` column |

## Use cases

- Start a pipeline from a CSV, Excel, Parquet, JSON, or plain-text file you uploaded.
- Pin a flow to a **specific dataset version** so scheduled runs stay
  reproducible even after the file is re-uploaded.

## Configuration

| Config key | Type | Required | Description |
|---|---|---|---|
| `dataset_id` | string | Yes | The dataset to read |
| `dataset_version` | int | No | Pin a specific version (defaults to latest) |

The config form only offers datasets whose `source_type` matches the node — a
`csvInput` node lists CSV datasets, a `textInput` node lists text datasets, etc.

## Generated Python code

```python
# csvInput
df_1 = pd.read_csv("sales.csv")

# excelInput
df_1 = pd.read_excel("report.xlsx")

# parquetInput
df_1 = pd.read_parquet("data.parquet")

# jsonInput
df_1 = pd.read_json("records.json")

# textInput — one row per line, column named "text"
df_1 = pd.read_csv("log.txt", sep="\n", header=None, names=["text"], engine="python", dtype=str)
```

## Tips & common mistakes

- **Pin a version for repeatable runs.** Leaving `dataset_version` empty always
  reads the latest upload; pinning makes a flow deterministic. See
  [Dataset versioning](/guide/projects-and-runs#dataset-versioning).
- **No datasets listed?** Upload one first on the Datasets page — the form warns
  when no compatible dataset exists for the node's format.
- **JSON shape matters.** `pd.read_json` expects a JSON array (`[{...}, {...}]`)
  or a records-oriented object. Nested structures may require a downstream
  Calculated Column or custom step to flatten.
- **Text input produces one column.** The resulting dataframe has a single `text`
  column; use String Transform or Split Column to extract structure from each line.

## See also

- [SQL input](./sql-input.md) — read live from a database instead of a file
- [Database Connections](/guide/connections) — read files from S3, GCS, Azure Blob, or a local folder via a storage connection
- [Projects & Runs](/guide/projects-and-runs) — datasets, versions, and runs
- [Datasets API](/api/datasets)
