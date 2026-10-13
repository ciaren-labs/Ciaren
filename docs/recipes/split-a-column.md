---
title: Split a Column by a Delimiter
description: Split a delimited CSV field into separate columns in Ciaren, preview missing parts, and export the same Split Column node as pandas or Polars.
search: recipe split column delimiter csv text separate columns pandas polars
---

# Split a Column by a Delimiter

Turn a field such as `EU|Paris` into separate `region` and `city` columns.
Choose a delimiter that belongs to the data format; splitting people's names
on spaces is unreliable when names contain several words.

**You'll use:** [File Input](/transformations/file-input) →
[Split Column](/transformations/split-column) →
[File Output](/transformations/file-output).

## Steps

1. Upload your CSV on **Datasets** and select it in **File Input**.
2. Add **Split Column** and set `column: location`, `mode: delimiter`,
   `delimiter: |`, and `into: ["region", "city"]`.
3. Leave `keep_original: true` while checking the split.
4. Preview the node. A missing second part should produce a null `city`.
5. Connect **File Output**, choose CSV or Parquet, and run the flow.

## Before / after

| location | region | city |
| --- | --- | --- |
| `EU\|Paris` | `EU` | `Paris` |
| `US\|Boston` | `US` | `Boston` |
| `EU` | `EU` | null |
| null | null | null |

## Exported Python

Both examples use the same configuration and keep the source column. The
transformation lines come from Ciaren's code generators.

### pandas

```python
import pandas as pd

df_1 = pd.DataFrame({'location': ['EU|Paris', 'US|Boston', 'EU', None]})
_parts = df_1['location'].astype('string').str.split('|', expand=True)
df_2 = df_1.assign(region=(_parts[0] if 0 in _parts.columns else pd.NA), city=(_parts[1] if 1 in _parts.columns else pd.NA))
print(df_2)
```

### Polars

```python
import polars as pl

df_1 = pl.DataFrame({'location': ['EU|Paris', 'US|Boston', 'EU', None]})
df_2 = df_1.with_columns([pl.col('location').cast(pl.Utf8).str.split('|').list.get(0, null_on_oob=True).alias('region'), pl.col('location').cast(pl.Utf8).str.split('|').list.get(1, null_on_oob=True).alias('city')])
print(df_2)
```

## Tips

- The order of `into` sets which part fills each output column.
- Extra parts beyond the named columns are not retained in those outputs.
  Keep the original field if you need to inspect malformed records.
- Use [String Transform](/transformations/string-transform) after splitting
  if the pieces contain leading or trailing spaces.
- To create one row per item instead, use
  [Split to Rows](/transformations/split-to-rows).

## See also

- [Split Column](/transformations/split-column)
- [Clean Messy Text](/recipes/clean-messy-text)
- [Recipes](/recipes/overview)
