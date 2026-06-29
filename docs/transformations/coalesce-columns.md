---
title: Coalesce columns
search: coalesce first non null fallback combine consolidate columns
description: Take the first non-null value across several columns
---

# Coalesce columns — `coalesceColumns`

Take the first non-null value across several columns into a new column — a
fallback chain for consolidating redundant fields.

## Use cases

- Pick the first available phone number: `mobile` → `home` → `work`.
- Merge values from differently-named source systems into one column.
- Fall back to a default-bearing column when a primary is missing.

## What it does

For each row, the columns are checked left-to-right and the first non-null value
is written to the new column. If every column is null for a row, the result is
null.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `columns` | string[] | Yes | Columns in priority order (≥ 2) |
| `new_column` | string | Yes | Name of the result column |
| `keep_original` | boolean | No | Keep the source columns (default true) |

## Generated Python code

```python
df_2 = df_1.assign(**{"phone": df_1[["mobile", "home", "work"]].bfill(axis=1).iloc[:, 0]})
```

## Tips & common mistakes

- **Priority is the column order** — put the most-trusted source first.
- To *concatenate* values instead of picking one, use [Combine columns](./combine-columns.md).

## See also

- [Combine columns](./combine-columns.md) · [Fill nulls](./fill-nulls.md)
