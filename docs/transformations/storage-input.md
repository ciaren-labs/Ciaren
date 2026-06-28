---
title: Storage input (S3 / GCS / Azure Blob / Local)
search: storage input s3 gcs azure blob local folder read file bucket object cloud
description: Read a file from object storage or a local folder into a flow
---

# Storage input — `storageInput`

Read a file from a cloud object store (AWS S3, Google Cloud Storage, Azure Blob
Storage) or a local folder via a reusable
[Storage Connection](/guide/connections). On every run the file is downloaded
once and materialized to a parquet snapshot so credentials never cross the
process boundary.

<FlowPipeline
  :nodes='[
    {"type":"input","label":"Storage Input","detail":"s3://my-bucket/sales/2024-06.csv"},
    {"type":"clean","label":"Cast Types","detail":"amount→float · date→datetime"},
    {"type":"transform","label":"Group By + Aggregate","detail":"revenue by region"},
    {"type":"output","label":"Storage Output","detail":"s3://my-bucket/reports/summary.parquet"}
  ]'
/>

## Use cases

- Read a daily export file from S3 in a scheduled flow so every run picks up the latest data.
- Process a shared file stored in a company Azure Blob container.
- Point at a local folder for development or self-hosted setups.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `connection_id` | string | Yes | The storage connection to read from |
| `path` | string | Yes | File path inside the bucket/container/folder (e.g. `data/sales.csv`) |
| `format` | string | No | `csv` (default), `tsv`, `excel`, `parquet`, `json`, `jsonl`, or `text` |

The connection defines the provider, bucket/container, and how credentials are
resolved from environment variables. The node only needs the relative path
within that bucket.

## Generated Python code

```python
import boto3, io, pandas as pd, os

s3 = boto3.client("s3", aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
                  aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"])
obj = s3.get_object(Bucket="my-bucket", Key="data/sales.csv")
df_1 = pd.read_csv(io.BytesIO(obj["Body"].read()))
```

## Tips & common mistakes

- **Create the connection first.** Go to **Connections → Add connection** and
  pick the storage provider. Set `secret_env` to the environment-variable name
  holding your key — FlowFrame never stores the secret itself.
- **Path is relative to the bucket/container root.** Do not include the
  `s3://bucket-name/` prefix — that comes from the connection.
- **Preview uses a bounded sample.** Preview and profile read the first N rows
  to stay fast; the full run reads the whole file.

## See also

- [Storage output](./storage-output.md) — write back to the same or a different bucket
- [Database Connections](/guide/connections) — create and manage storage connections
- [File input](./file-input.md) — read an uploaded dataset instead of a remote file
