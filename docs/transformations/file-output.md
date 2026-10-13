---
title: Write Files with File Output in Both Engines
description: Write Ciaren results as CSV, TSV, Excel, Parquet, JSON, JSONL or text. Compare exact pandas and Polars exports, filenames and local output behavior.
search: output csv tsv excel parquet json jsonl text write save result dataset file
---

# File output

Write the upstream frame to a file. This is usually the last node in a pipeline —
the terminal step that produces a downloadable, versionable dataset.

The single **File Output** node replaces the old per-format output nodes: pick the
format from a dropdown and give it a name.

<FlowPipeline
  :nodes='[
    {"type":"input","label":"File Input"},
    {"type":"clean","label":"Fill Nulls"},
    {"type":"transform","label":"Calculated Column"},
    {"type":"output","label":"File Output","detail":"format + name → dataset"}
  ]'
/>

`type`: `fileOutput`.

## Use cases

- Save a cleaned dataset back out as CSV, TSV, Excel, Parquet, JSON, JSON Lines, or text.
- Produce a Parquet file for fast re-reads in a later flow.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `format` | enum | Yes | `csv` · `tsv` · `excel` · `parquet` · `json` · `jsonl` · `text` |
| `dataset_name` | string | Yes | Name for the produced dataset/file |

The result is written to the run's output location and registered as a dataset
you can preview, download, or feed into another flow.

::: tip Legacy outputs
Flows built before the consolidation may still contain the old `csvOutput` /
`excelOutput` / `parquetOutput` nodes. They keep working, but new flows use the
unified **File Output** node (the old ones are hidden from the palette).
:::

## Generated Python code

These separate flows read `source.csv` and write `result` with the selected format
extension (`dataset_name: result`). Put your original CSV beside the script and choose
one example. The seven examples use the same source, each with its own destination
format. The exported script creates a local file, not a registered Ciaren dataset or
run. JSON stores records and JSONL stores one record per line; indentation may differ
between engines. Text writes headerless, tab-separated rows without column types; use
Parquet to read a table back with its types. These are complete eager exports with
imports; use an environment with Ciaren and its file-format dependencies installed.

### pandas

#### CSV

```python
import pandas as pd

df_source = pd.read_csv('source.csv')
df_source.to_csv('result.csv', index=False)
```

#### TSV

```python
import pandas as pd

df_source = pd.read_csv('source.csv')
df_source.to_csv('result.tsv', index=False, sep='\t')
```

#### EXCEL

```python
import pandas as pd

df_source = pd.read_csv('source.csv')
df_source.to_excel('result.xlsx', index=False)
```

#### PARQUET

```python
import pandas as pd

df_source = pd.read_csv('source.csv')
df_source.to_parquet('result.parquet', index=False)
```

#### JSON

```python
import pandas as pd

df_source = pd.read_csv('source.csv')
df_source.to_json('result.json', orient='records', indent=2)
```

#### JSONL

```python
import pandas as pd

df_source = pd.read_csv('source.csv')
df_source.to_json('result.jsonl', orient='records', lines=True)
```

#### TEXT

```python
import pandas as pd

df_source = pd.read_csv('source.csv')
df_source.to_csv('result.txt', index=False, header=False, sep='\t')
```

### Polars

#### CSV

```python
import polars as pl

df_source = pl.read_csv('source.csv')
df_source.write_csv('result.csv')
```

#### TSV

```python
import polars as pl

df_source = pl.read_csv('source.csv')
df_source.write_csv('result.tsv', separator='\t')
```

#### EXCEL

```python
import polars as pl

df_source = pl.read_csv('source.csv')
df_source.write_excel('result.xlsx')
```

#### PARQUET

```python
import polars as pl

df_source = pl.read_csv('source.csv')
df_source.write_parquet('result.parquet')
```

#### JSON

```python
import polars as pl

df_source = pl.read_csv('source.csv')
df_source.write_json('result.json')
```

#### JSONL

```python
import polars as pl

df_source = pl.read_csv('source.csv')
df_source.write_ndjson('result.jsonl')
```

#### TEXT

```python
import polars as pl

df_source = pl.read_csv('source.csv')
df_source.write_csv('result.txt', include_header=False, separator='\t')
```

## Tips & common mistakes

- **One terminal node per branch.** Each output writes the frame reaching it;
  use multiple output nodes to materialize intermediate branches.
- **Parquet preserves dtypes.** Prefer it over CSV when types (datetimes,
  integers, categoricals) matter downstream.
- **Text output** writes headerless, tab-separated records with CSV-style
  quoting. Values containing tabs or newlines are escaped, so a record may span
  physical lines. Text Input reads raw lines and does not reverse this encoding;
  use TSV or Parquet when you need to read the table back.

## See also

- [SQL output](./sql-output.md) — write to a database table instead of a file
- [Storage output](./storage-output.md) — write to S3 / GCS / Azure Blob
- [Projects & Runs](/guide/projects-and-runs)
- Recipe: [Convert Excel to Parquet](/recipes/convert-excel-to-parquet)
