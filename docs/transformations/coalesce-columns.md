---
title: Coalesce Columns with Ordered Fallbacks
search: coalesce first non null fallback combine consolidate columns
description: Choose the first non-null Ciaren value across columns in priority order. Preserve or drop source fields and compare pandas and Polars exports.
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

These exports choose `mobile`, then `home`, then `work`, writing `phone` and keeping the source columns. An empty string is a value; a row with all three null stays null.

### pandas

```python
df_2 = df_1.assign(phone=lambda _d: _d['mobile'].where(pd.notna, _d['home']).where(pd.notna, _d['work']))
```

### Polars

```python
df_2 = df_1.with_columns(pl.coalesce([pl.col('mobile'), pl.col('home'), pl.col('work')]).alias('phone'))
```

## Tips & common mistakes

- **Priority is the column order** — put the most-trusted source first.
- To *concatenate* values instead of picking one, use [Combine columns](./combine-columns.md).

## See also

- [Combine columns](./combine-columns.md) · [Fill nulls](./fill-nulls.md)
