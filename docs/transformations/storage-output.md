---
title: Storage output (S3 / GCS / Azure Blob / Local)
search: storage output s3 gcs azure blob local folder write file bucket object cloud
description: Write the result of a flow to object storage or a local folder
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

```python
import boto3, io, pandas as pd, os

buf = io.BytesIO()
df_4.to_parquet(buf, index=False)
buf.seek(0)
s3 = boto3.client("s3", aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
                  aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"])
s3.put_object(Bucket="reports", Key="summary.parquet", Body=buf.read())
```

## Tips & common mistakes

- **Parquet is the default format** and the best choice for downstream data
  pipelines — it preserves types and compresses well. Use `csv` if the
  destination requires it.
- **`overwrite` replaces the object silently.** Set `if_exists: error` to abort
  rather than overwrite an existing file, which is useful in append-style
  workflows where you'd rather fail loud than silently clobber old data.
- **The run is marked failed if the upload fails.** No partial writes are left
  behind — FlowFrame pushes the output only after every upstream node succeeds.

## See also

- [Storage input](./storage-input.md) — read from the same bucket in the same or another flow
- [Database Connections](/guide/connections) — create and manage storage connections
- [File output](./file-output.md) — download the result as a local file instead
