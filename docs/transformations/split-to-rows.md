---
title: Split to rows
search: explode split rows delimited list one row per value unnest
description: Expand a delimited or list column into one row per value
---

# Split to rows — `explodeRows`

Expand a column into multiple rows — one per value. The other columns are
repeated on each new row.

## Use cases

- Turn a `tags` cell like `"news;sports;tech"` into one row per tag.
- Unnest a list column produced upstream.
- Normalize multi-value fields before grouping or joining.

## What it does

With a **delimiter**, the text is split on it first and then exploded
(`"a;b"` → two rows). Without a delimiter, an existing list column is exploded
directly. Row count grows; all other columns are duplicated per value.

## Configuration

| Config key | Type | Required | Description |
| --- | --- | --- | --- |
| `column` | string | Yes | The column to expand |
| `delimiter` | string | No | Split text on this delimiter first; empty = explode a list column |

## Generated Python code

```python
df_2 = df_1.assign(**{"tags": df_1["tags"].astype("string").str.split(";")}).explode("tags").reset_index(drop=True)
```

## Tips & common mistakes

- A cell with **no delimiter present** yields a single row (count unchanged for it).
- A **trailing delimiter** (`"a;"`) produces an empty-string row — clean up with
  [Filter by expression](./filter-expression.md) if needed.

## See also

- [Split column](./split-column.md) · [Unpivot](./unpivot.md)
