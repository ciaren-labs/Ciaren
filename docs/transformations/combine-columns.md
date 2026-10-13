---
title: Combine Columns into Text with Separators
search: combine concatenate columns join merge text separator full name
description: Join Ciaren columns into text with an ordered separator, keeping or dropping source fields. Compare generated pandas and Polars exports.
---

# Combine columns — `combineColumns`

Join several columns into one text column, separated by a separator. The inverse
of [Split column](./split-column.md).

## Use cases

- Build a full name from `first` + `last`.
- Make a composite key like `region-year`.
- Assemble an address from street / city / zip.

## What it does

Each selected column is cast to text and joined left-to-right with the separator.
Null cells become empty strings, so the separator's position is preserved
(`"a" + null + "c"` → `"a||c"` with separator `|`).

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `columns` | string[] | Yes | Columns to combine (≥ 2), in order |
| `new_column` | string | Yes | Name of the combined column |
| `separator` | string | No | Text between values (default a single space) |
| `keep_original` | boolean | No | Keep the source columns (default true) |

## Generated Python code

These exports combine `first` and `last` into `full_name`, with the default space separator and `keep_original: true`. Null parts become empty text without removing the separator.

### pandas

```python
df_2 = df_1.assign(full_name=lambda _d: _d['first'].astype('string').fillna('') + ' ' + _d['last'].astype('string').fillna(''))
```

### Polars

```python
df_2 = df_1.with_columns(pl.concat_str([pl.col('first').cast(pl.Utf8).fill_null(''), pl.col('last').cast(pl.Utf8).fill_null('')], separator=' ').alias('full_name'))
```

## Tips & common mistakes

- **Order matters** — columns are joined in the order you pick them.
- Turn off **keep original** to drop the source columns once combined.

## See also

- [Split column](./split-column.md) · [Coalesce columns](./coalesce-columns.md)
