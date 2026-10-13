---
title: Split Delimited Text or Lists into Rows
search: explode split rows delimited list one row per value unnest
description:
  Split Ciaren delimited text or list columns into rows while repeating other
  fields. Preserve empty and null values; compare pandas and Polars exports.
---

# Split to rows — `explodeRows`

Expand a column into multiple rows — one per value. The other columns are
repeated on each new row.

## Use cases

- Turn a `tags` cell like `"news;sports;tech"` into one row per tag.
- Unnest a list column produced upstream.
- Normalize multi-value fields before grouping or joining.

## What it does

With a **delimiter**, the text is split on it first and then exploded (`"a;b"` →
two rows). Without a delimiter, an existing list column is exploded directly.
Row count grows; all other columns are duplicated per value.

## Configuration

| Config key  | Type   | Required | Description                                                       |
| ----------- | ------ | -------- | ----------------------------------------------------------------- |
| `column`    | string | Yes      | The column to expand                                              |
| `delimiter` | string | No       | Split text on this delimiter first; empty = explode a list column |

## Generated Python code

These exports split `tags` on `;` and expand one row per token, repeating every
other field. Empty text and trailing delimiters produce empty tokens; null stays
null.

### pandas

```python
df_2 = df_1.assign(tags=lambda _d: _d['tags'].astype('string').str.split(';')).explode('tags').reset_index(drop=True)
```

### Polars

```python
df_2 = df_1.with_columns(pl.col('tags').cast(pl.Utf8).str.split(';')).explode('tags')
```

## Tips & common mistakes

- A cell with **no delimiter present** yields a single row (count unchanged for
  it).
- A **trailing delimiter** (`"a;"`) produces an empty-string row — clean up with
  [Filter by expression](./filter-expression.md) if needed.

## See also

- [Split column](./split-column.md) · [Unpivot](./unpivot.md)
