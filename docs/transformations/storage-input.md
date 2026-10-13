---
title: Read Storage Files and Export Local Scripts
search: storage input s3 gcs azure blob local folder read file bucket object cloud
description: Read Ciaren storage files and understand portable local-file exports. Compare pandas and Polars CSV reads, explicit dialects and credential handling.
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
    {"type":"clean","label":"Change Types","detail":"amount→float · date→datetime"},
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
| `delimiter` | string | No | CSV only: `,` `;` `\t` or `\|`. Unset means auto-detect |
| `encoding` | string | No | CSV/TSV: `utf-8`, `utf-8-sig`, `latin-1`, `cp1252`, `utf-16`, `utf-16-le`, or `utf-16-be`. Unset means auto-detect |
| `decimal` | string | No | CSV/TSV: `.` or `,`. Unset means auto-detect |

The connection defines the provider, bucket/container, and how credentials are
resolved from environment variables. The node only needs the relative path
within that bucket.

## CSV dialect detection

When you pick a CSV or TSV file, the config panel reads the first 64 KB of the
file and shows what it found, for example
**Detected: Semicolon (;) · cp1252 · decimal comma**. The **Separator**,
**Encoding**, and **Decimal mark** fields stay on **Auto-detect** and show the
detected value, so the preview splits columns correctly without any manual setup.
Opening the node never changes its configuration.

- **Auto-detect:** a field left on **Auto-detect** is detected again on every
  preview and run. This helps when an upstream system may change the file's
  format.
- **Override:** pick a value in any of the three fields, or click
  **Use detected values** to pin the current detection. A value you set always
  wins over detection, on both engines and in exported code.
- **Exported code** only carries the dialect you set. A field left on
  Auto-detect uses the pandas/polars default (comma, UTF-8, `.`) in the export,
  so pin the values before exporting a non-default file.
- **Fallback:** if the sample shows no clear dialect (an empty file, a single
  column, binary data, or bytes that are neither UTF-8 nor Windows-1252), the
  panel doesn't show a "Detected" value. Reads then use the defaults: comma,
  UTF-8, and `.` as the decimal mark.
- **Changing the file or format** clears the three fields, and Ciaren detects
  the new file.
- **Where it applies:** the built-in S3, GCS, Azure Blob, and Local Storage
  connectors. Plugin storage connectors don't support dialect options. A node
  that sets them on a plugin connection fails with a clear error.

Detection reads only a bounded sample, through the same path checks as the read
itself. For a local folder, paths can't escape the connection root or the
directories in `CIAREN_STORAGE_ALLOWED_ROOTS`.

## Generated Python code

These are two separate Storage Input → File Output flows. The default example reads
`data/sales.csv`; the explicit dialect example reads `data/ventas.csv` with `delimiter:
;`, `encoding: cp1252` and `decimal: ,`. Download the original object first and put its
basename beside the script. Both exports read that local file and write
`readback.parquet`; they do not contact the provider, resolve credentials or create a
Ciaren snapshot. Unlike runtime auto-detection, the script only carries pinned dialect
settings. The Polars dialect example decodes Windows-1252 text and parses its decimal
comma explicitly. These complete exports use eager Polars and the file-format
dependencies installed with Ciaren.

### pandas

#### CSV

```python
import pandas as pd

# storageInput: download 'data/sales.csv' from your storage connection first
df_sales = pd.read_csv('sales.csv')
df_sales.to_parquet('readback.parquet', index=False)
```

#### Pinned CSV dialect

```python
import pandas as pd

# storageInput: download 'data/ventas.csv' from your storage connection first
df_ventas = pd.read_csv('ventas.csv', sep=';', encoding='cp1252', decimal=',')
df_ventas.to_parquet('readback.parquet', index=False)
```

### Polars

#### CSV

```python
import polars as pl

# storageInput: download 'data/sales.csv' from your storage connection first
df_sales = pl.read_csv('sales.csv')
df_sales.write_parquet('readback.parquet')
```

#### Pinned CSV dialect

```python
import polars as pl

# storageInput: download 'data/ventas.csv' from your storage connection first
with open('ventas.csv', encoding='cp1252') as _f:
    df_ventas = pl.read_csv(_f.read().encode(), separator=';', decimal_comma=True)
df_ventas.write_parquet('readback.parquet')
```

## Tips & common mistakes

- **Create the connection first.** Go to **Connections → Add connection** and
  pick the storage provider. Set the key's secret reference — a bare name or
  `env:NAME` for an environment variable, `keyring:NAME` for the OS keychain
  (recommended on desktop), or `file:/path` for a mounted secret file. Ciaren
  never stores the secret itself; see [Connections](/guide/connections).
- **Path is relative to the bucket/container root.** Do not include the
  `s3://bucket-name/` prefix — that comes from the connection.
- **Preview uses a bounded sample.** Preview and profile read the first N rows
  to stay fast; the full run reads the whole file.

## See also

- [Storage output](./storage-output.md) — write back to the same or a different bucket
- [Database Connections](/guide/connections) — create and manage storage connections
- [File input](./file-input.md) — read an uploaded dataset instead of a remote file
