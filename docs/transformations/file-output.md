---
title: File output (CSV / TSV / Excel / Parquet / JSON / JSONL / text)
description: Write the result of a flow to a file
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

```python
df_5.to_csv("result.csv", index=False)   # format: csv
df_5.to_json("result.json", orient="records", indent=2)   # format: json
```

Excel/Parquet/text emit `to_excel(...)` / `to_parquet(...)` / a tab-separated
`to_csv(..., header=False)`.

## Tips & common mistakes

- **One terminal node per branch.** Each output writes the frame reaching it;
  use multiple output nodes to materialize intermediate branches.
- **Parquet preserves dtypes.** Prefer it over CSV when types (datetimes,
  integers, categoricals) matter downstream.
- **Text output** writes one row per line (tab-separated for multiple columns) —
  the mirror of the text input reader.

## See also

- [SQL output](./sql-output.md) — write to a database table instead of a file
- [Storage output](./storage-output.md) — write to S3 / GCS / Azure Blob
- [Projects & Runs](/guide/projects-and-runs)
