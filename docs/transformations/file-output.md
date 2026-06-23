---
title: File output (CSV / Excel / Parquet)
description: Write the result of a flow to a file
search: output csv excel parquet write save result dataset
---

# File output

Write the upstream frame to a file. This is usually the last node in a pipeline.
`type`: `csvOutput`, `excelOutput`, `parquetOutput` — one per format.

## Use cases

- Save a cleaned dataset back out as CSV/Excel/Parquet.
- Produce a Parquet file for fast re-reads in a later flow.

## Configuration

| Config key | Type | Required | Description |
|---|---|---|---|
| `dataset_name` | string | Yes | Name for the produced dataset/file |

The result is written to the run's output location and registered as a dataset
you can preview, download, or feed into another flow.

## Generated Python code

```python
df_5.to_csv("output.csv", index=False)
```

Excel and Parquet emit `to_excel(...)` / `to_parquet(...)`.

## Tips & common mistakes

- **One terminal node per branch.** Each output writes the frame reaching it;
  use multiple output nodes to materialize intermediate branches.
- **Parquet preserves dtypes.** Prefer it over CSV when types (datetimes,
  integers, categoricals) matter downstream.

## See also

- [SQL output](./sql-output.md) — write to a database table instead of a file
- [Projects & Runs](/guide/projects-and-runs)
