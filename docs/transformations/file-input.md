---
title: Read Files with File Input in Both Engines
description: Read Ciaren datasets in CSV, TSV, Excel, Parquet, JSON, JSONL or text format. Compare exact pandas and Polars exports and original-file handling.
search: input csv excel parquet json text read dataset version source
---

# File input

Load data from a dataset you've uploaded into the flow. This is usually the first
node in a pipeline — the entry point for a file-based ETL flow.

<FlowPipeline
  :nodes='[
    {"type":"input","label":"File Input","detail":"uploaded dataset + format"},
    {"type":"clean","label":"Drop Nulls","detail":"remove bad rows"},
    {"type":"transform","label":"Group By","detail":"aggregate"},
    {"type":"output","label":"File Output","detail":"efficient export"}
  ]'
/>

Ciaren now uses one uploaded-file input node with a format selector:

| Node type | Format setting | Reads |
| --- | --- | --- |
| `fileInput` | `csv` / `tsv` | Delimited values |
| `fileInput` | `excel` | `.xlsx` / `.xls` workbooks |
| `fileInput` | `parquet` | Columnar binary format |
| `fileInput` | `json` / `jsonl` | JSON array/records or JSON Lines |
| `fileInput` | `text` | Plain text, one row per line → single `text` column |

Legacy `csvInput`, `excelInput`, `parquetInput`, `jsonInput`, and `textInput`
nodes still run in existing flows, but new flows should use **File Input**.

## Use cases

- Start a pipeline from a CSV, Excel, Parquet, JSON, or plain-text file you uploaded.
- Pin a flow to a **specific dataset version** so scheduled runs stay
  reproducible even after the file is re-uploaded.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `dataset_id` | string | Yes | The dataset to read |
| `dataset_version` | int | No | Pin a specific version (defaults to latest) |
| `format` | string | Yes | How to read the file: `csv`, `tsv`, `excel`, `parquet`, `json`, `jsonl`, or `text` |

The config form only offers datasets compatible with the selected format. Changing
the file type clears the selected dataset so you cannot accidentally run a CSV
dataset as Parquet, for example.

## CSV dialect (delimiter, encoding, decimal mark)

You don't need to set the dialect of an uploaded CSV or TSV before previewing it.
When you upload the file, Ciaren detects the delimiter (`,` `;` tab `|`), the
encoding (UTF-8, UTF-8 with BOM, UTF-16, or Windows-1252), and a decimal comma
(`1,50`). It then stores a normalized copy (UTF-8, comma-separated). This node
reads that copy, so previews and runs on both engines see correctly split
columns.

- **Override:** if detection guesses wrong, expand **Import options** on the
  Datasets page and choose the separator, encoding, or decimal mark before you
  upload. An explicit choice always wins over detection, and re-uploading adds a
  new version.
- **Fallback:** when the sample has no evidence (an empty file, a single
  column), Ciaren uses the defaults: comma, UTF-8, and `.` as the decimal mark.
- **Exported code:** the script reads your original file, so it includes the
  detected or chosen dialect, such as `pd.read_csv('ventas.csv', sep=';',
  encoding='cp1252', decimal=',')`. For polars, the script decodes the file to
  UTF-8 first.

For CSV files that you read directly from S3, GCS, Azure Blob, or a local folder,
use [Storage input](./storage-input.md#csv-dialect-detection). It detects the
dialect when you pick the file and has its own override fields.

## Generated Python code

Each example is a separate File Input → File Output flow. Put the original named file
beside the script; exporting code does not download a dataset version or create a Ciaren
run. The output `readback.parquet` makes the loaded rows inspectable. The seven examples
use each listed input format and its named local file. Text is UTF-8, one row per line:
spaces and empty lines are retained. These are complete current exports, with imports
and actual input variable names. Use an environment with Ciaren and its file-format
dependencies installed; Polars examples are eager.

### pandas

#### CSV

```python
import pandas as pd

df_sales = pd.read_csv('sales.csv')
df_sales.to_parquet('readback.parquet', index=False)
```

#### TSV

```python
import pandas as pd

df_sales = pd.read_csv('sales.tsv', sep='\t')
df_sales.to_parquet('readback.parquet', index=False)
```

#### EXCEL

```python
import pandas as pd

df_report = pd.read_excel('report.xlsx')
df_report.to_parquet('readback.parquet', index=False)
```

#### PARQUET

```python
import pandas as pd

df_data = pd.read_parquet('data.parquet')
df_data.to_parquet('readback.parquet', index=False)
```

#### JSON

```python
import pandas as pd

df_records = pd.read_json('records.json')
df_records.to_parquet('readback.parquet', index=False)
```

#### JSONL

```python
import pandas as pd

df_records = pd.read_json('records.jsonl', lines=True)
df_records.to_parquet('readback.parquet', index=False)
```

#### TEXT

```python
import pandas as pd

with open('log.txt', encoding='utf-8') as _f:
    df_log = pd.DataFrame({"text": _f.read().splitlines()})
df_log.to_parquet('readback.parquet', index=False)
```

### Polars

#### CSV

```python
import polars as pl

df_sales = pl.read_csv('sales.csv')
df_sales.write_parquet('readback.parquet')
```

#### TSV

```python
import polars as pl

df_sales = pl.read_csv('sales.tsv', separator="\t")
df_sales.write_parquet('readback.parquet')
```

#### EXCEL

```python
import polars as pl

df_report = pl.read_excel('report.xlsx', engine="openpyxl")
df_report.write_parquet('readback.parquet')
```

#### PARQUET

```python
import polars as pl

df_data = pl.read_parquet('data.parquet')
df_data.write_parquet('readback.parquet')
```

#### JSON

```python
import polars as pl

df_records = pl.read_json('records.json')
df_records.write_parquet('readback.parquet')
```

#### JSONL

```python
import polars as pl

df_records = pl.read_ndjson('records.jsonl')
df_records.write_parquet('readback.parquet')
```

#### TEXT

```python
import polars as pl

with open('log.txt', encoding='utf-8') as _f:
    df_log = pl.DataFrame({"text": _f.read().splitlines()})
df_log.write_parquet('readback.parquet')
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
- Recipe: [Convert Excel to Parquet](/recipes/convert-excel-to-parquet)
