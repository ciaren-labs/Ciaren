---
title: One Row per Tag While Preserving Record IDs
description: Split a delimited tags column into one row per tag in Ciaren while repeating the source record ID and preserving null and empty values.
search: recipe split rows tags delimiter record id explode pandas polars null empty
---

# One Row per Tag While Preserving Record IDs

Turn a semicolon-delimited `tags` field into one row per tag without losing the
source record ID. This recipe uses **Split to Rows**, which creates rows; it is
different from [Split a Column](/recipes/split-a-column), which creates columns.

**You'll use:** [File Input](/transformations/file-input) →
[Split to Rows](/transformations/split-to-rows) →
[File Output](/transformations/file-output).

## Steps

1. Upload the CSV on **Datasets** and select it in **File Input**.
2. Add **Split to Rows** and set `column: tags` and `delimiter: ;`.
3. Preview the node. The `record_id` value is repeated for every expanded tag.
4. Check null and empty values before adding any cleaning step: a null cell stays
   null, and a trailing delimiter creates an empty-string row.
5. Connect **File Output**, choose CSV or Parquet, and run the flow.

## Before / after

The input has four records. The output has six rows because `r1` expands to two
tags and `r4` keeps the empty token after its trailing delimiter.

### Before

| record_id | tags |
| --- | --- |
| `r1` | `news;sports` |
| `r2` | `news` |
| `r3` | null |
| `r4` | `a;` |

### After

| record_id | tags |
| --- | --- |
| `r1` | `news` |
| `r1` | `sports` |
| `r2` | `news` |
| `r3` | null |
| `r4` | `a` |
| `r4` | `""` (empty string) |

The null row and the empty-string row are different values. If the downstream
workflow should remove either one, add an explicit [Filter by expression](/transformations/filter-expression)
step after splitting. For whitespace cleanup, see [Clean Messy Text](/recipes/clean-messy-text).

## Exported Python

These examples use the current Split to Rows exporters. Both produce the same
six records shown above.

### pandas

```python
import pandas as pd

df_1 = pd.DataFrame({'record_id': ['r1', 'r2', 'r3', 'r4'], 'tags': ['news;sports', 'news', None, 'a;']})
df_2 = df_1.assign(tags=lambda _d: _d['tags'].astype('string').str.split(';')).explode('tags').reset_index(drop=True)
print(df_2)
```

### Polars

```python
import polars as pl

df_1 = pl.DataFrame({'record_id': ['r1', 'r2', 'r3', 'r4'], 'tags': ['news;sports', 'news', None, 'a;']})
df_2 = df_1.with_columns(pl.col('tags').cast(pl.Utf8).str.split(';')).explode('tags')
print(df_2)
```

## See also

- [Split to Rows](/transformations/split-to-rows)
- [Split a Column](/recipes/split-a-column)
- [Filter by expression](/transformations/filter-expression)
- [Recipes](/recipes/overview)
