---
title: Write Storage Results and Understand Export Markers
search: storage output s3 gcs azure blob local folder write file bucket object cloud
description: Write Ciaren results through storage connections and understand exported script markers. Compare pandas and Polars examples and runtime write behavior.
---

# Storage output — `storageOutput`

Write the result of a flow to a cloud object store (AWS S3, Google Cloud
Storage, Azure Blob Storage) or a local folder via a reusable
[Storage Connection](/guide/connections). The result is serialized and uploaded
after the rest of the flow succeeds — a write failure marks the run failed.

<FlowPipeline
  :nodes='[
    {"type":"input","label":"Storage Input","detail":"s3://raw-data/orders.csv"},
    {"type":"clean","label":"Drop Nulls"},
    {"type":"transform","label":"Group By + Aggregate","detail":"revenue by region"},
    {"type":"output","label":"Storage Output","detail":"s3://reports/summary.parquet · overwrite"}
  ]'
/>

## Use cases

- Land a cleaned or aggregated result in a company bucket for downstream consumers.
- Write a daily report parquet to GCS on a schedule.
- Archive processed outputs to Azure Blob alongside raw files.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `connection_id` | string | Yes | The storage connection to write to |
| `path` | string | Yes | Destination path inside the bucket/container/folder (e.g. `reports/summary.parquet`) |
| `format` | string | No | `parquet` (default), `csv`, `tsv`, `excel`, `json`, `jsonl`, or `text` |
| `if_exists` | string | No | `overwrite` (default) or `error` |

## Generated Python code

This complete File Input → Storage Output flow reads local `source.csv`. The storage
node can have `connection_id: storage`, `path: reports/summary.parquet`, `format:
parquet` and `if_exists: overwrite`; those settings do not turn the exported comment
into an upload. Both current generators leave only a marker after reading the input. The
script creates no output file, serializes no storage artifact and does not enforce the
destination overwrite policy. To write from an exported script, add an explicit writer
suited to your destination; use the Ciaren run when you want the configured storage
connection to perform the write. No credentials or provider SDK calls are embedded.

### pandas

#### MARKER

```python
import pandas as pd

df_source = pd.read_csv('source.csv')
# storageOutput: write df_source to your configured storage target
```

### Polars

#### MARKER

```python
import polars as pl

df_source = pl.read_csv('source.csv')
# storageOutput: write df_source to your configured storage target
```

## Tips & common mistakes

- **Parquet is the default format** and the best choice for downstream data
  pipelines — it preserves types and compresses well. Use `csv` if the
  destination requires it.
- **`overwrite` replaces the object silently.** Set `if_exists: error` to abort
  rather than overwrite an existing file, which is useful in append-style
  workflows where you'd rather fail loud than silently clobber old data.
- **The run is marked failed if the write fails.** Storage providers do not
  share an atomic-write guarantee. Inspect the destination before retrying a
  failed write; a local file or remote object may already exist.

## See also

- [Storage input](./storage-input.md) — read from the same bucket in the same or another flow
- [Database Connections](/guide/connections) — create and manage storage connections
- [File output](./file-output.md) — download the result as a local file instead
